import os
import shutil
from . import common
import sys

lib_list = ("zlib", "libxml2")
subproject_list = ("llvm", "runtimes")


def get_cmake_option(**kwargs: dict[str, str]) -> list[str]:
    """将字典转化为cmake选项列表

    Returns:
        list[str]: cmake选项列表
    """
    option_list: list[str] = []
    for key, value in kwargs.items():
        option_list.append(f"-D{key}={value}")
    return option_list


def gnu_to_llvm(target: str) -> str:
    """将gnu风格triplet转化为llvm风格

    Args:
        target (str): 目标平台

    Returns:
        str: llvm风格triplet
    """
    if target.count("-") == 2:
        index = target.find("-")
        result = target[:index]
        result += "-unknown"
        result += target[index:]
        return result
    else:
        return target


class environment(common.basic_environment):
    host: str  # host平台
    build: str  # build平台
    bootstrap: bool = False  # 是否进行自举以便不依赖gnu相关库，需要多次编译
    prefix: dict[str, str] = {}  # 工具链安装位置
    lib_dir_list: dict[str, str]  # 所有库所在目录
    bin_dir: str  # 安装后可执行文件所在目录
    source_dir: dict[str, str] = {}  # 源代码所在目录
    build_dir: dict[str, str] = {}  # 构建时所在目录
    stage: int = 1  # 自举阶段
    compiler_list = ("C", "CXX", "ASM")  # 编译器列表
    sysroot_dir: str  # sysroot所在路径
    system_list: dict[str, str] = {}
    dylib_option_list: dict[str, str] = {  # llvm动态链接选项
        "LLVM_LINK_LLVM_DYLIB": "ON",
        "LLVM_BUILD_LLVM_DYLIB": "ON",
        "CLANG_LINK_CLANG_DYLIB": "ON",
    }
    # 如果符号过多则Windows下需要改用该选项
    # dylib_option_list_windows: dict[str, str] = {"BUILD_SHARED_LIBS": "ON"}
    llvm_option_list_1: dict[str, str] = {  # 第1阶段编译选项，同时构建工具链和运行库
        "CMAKE_BUILD_TYPE": "Release",  # 设置构建类型
        "LLVM_BUILD_DOCS": "OFF",  # 禁用llvm文档构建
        "LLVM_BUILD_EXAMPLES": "OFF",  # 禁用llvm示例构建
        "LLVM_INCLUDE_BENCHMARKS": "OFF",  # 禁用llvm基准测试构建
        "LLVM_INCLUDE_EXAMPLES": "OFF",  # llvm不包含示例
        "LLVM_INCLUDE_TESTS": "OFF",  # llvm不包含单元测试
        "LLVM_TARGETS_TO_BUILD": '"X86;AArch64;RISCV;ARM;LoongArch"',  # 设置需要构建的目标
        "LLVM_ENABLE_PROJECTS": '"clang;lld"',  # 设置一同构建的子项目
        "LLVM_ENABLE_RUNTIMES": '"libcxx;libcxxabi;libunwind;compiler-rt"',  # 设置一同构建的运行时项目
        "LLVM_ENABLE_WARNINGS": "OFF",  # 禁用警告
        "LLVM_INCLUDE_TESTS": "OFF",  # llvm不包含单元测试
        "CLANG_INCLUDE_TESTS": "OFF",  # clang不包含单元测试
        "BENCHMARK_INSTALL_DOCS": "OFF",  # 基准测试不包含文档
        "LLVM_INCLUDE_BENCHMARKS": "OFF",  # llvm不包含基准测试
        "CLANG_DEFAULT_LINKER": "lld",  # 使用lld作为clang默认的链接器
        "LLVM_ENABLE_LLD": "ON",  # 使用lld链接llvm以加速链接
        "CMAKE_BUILD_WITH_INSTALL_RPATH": "ON",  # 在linux系统上设置rpath以避免动态库环境混乱
        "LIBCXX_INCLUDE_BENCHMARKS": "OFF",  # libcxx不包含测试
        "LIBCXX_USE_COMPILER_RT": "ON",  # 使用compiler-rt构建libcxx
        "LIBCXX_CXX_ABI": "libcxxabi",  # 使用libcxxabi构建libcxx
        "LIBCXXABI_USE_LLVM_UNWINDER": "ON",  # 使用libunwind构建libcxxabi
        "LIBCXXABI_USE_COMPILER_RT": "ON",  # 使用compiler-rt构建libcxxabi
        "COMPILER_RT_DEFAULT_TARGET_ONLY": "ON",  # compiler-rt只需构建默认目标即可，禁止自动构建multilib
        "COMPILER_RT_USE_LIBCXX": "ON",  # 使用libcxx构建compiler-rt
    }
    llvm_option_list_w32_1: dict[str, str] = {  # win32运行时第1阶段编译选项
        **llvm_option_list_1,
        "LIBCXXABI_HAS_WIN32_THREAD_API": "ON",
        "LIBCXXABI_ENABLE_SHARED": "OFF",
        "LIBCXX_ENABLE_STATIC_ABI_LIBRARY": "ON",
    }
    llvm_option_list_2: dict[str, str] = {  # 第2阶段编译选项，该阶段不编译运行库
        **llvm_option_list_1,
        "LLVM_ENABLE_PROJECTS": '"clang;clang-tools-extra;lld"',
        "LLVM_ENABLE_LTO": "Thin",
        "CLANG_DEFAULT_CXX_STDLIB": "libc++",
        "CLANG_DEFAULT_RTLIB": "compiler-rt",
        "CLANG_DEFAULT_UNWINDLIB": "libunwind",
    }
    llvm_option_list_3: dict[str, str] = {
        **llvm_option_list_2,
        "LIBUNWIND_USE_COMPILER_RT": "ON",  # 使用compiler-rt构建libunwind
    }  # 第3阶段编译选项，编译运行库
    llvm_option_list_w32_3: dict[str, str] = {}  # win32运行时第3阶段编译选项
    lib_option: dict[str, str] = {  # llvm依赖库编译选项
        "BUILD_SHARED_LIBS": "ON",
        "LIBXML2_WITH_ICONV": "OFF",
        "LIBXML2_WITH_LZMA": "OFF",
        "LIBXML2_WITH_PYTHON": "OFF",
        "LIBXML2_WITH_ZLIB": "OFF",
        "LIBXML2_WITH_THREADS": "OFF",
        "LIBXML2_WITH_CATALOG": "OFF",
        "CMAKE_RC_COMPILER": "llvm-windres",
        "CMAKE_BUILD_WITH_INSTALL_RPATH": "ON",
    }
    llvm_cross_option: dict[str, str] = {}  # llvm交叉编译选项
    compiler_rt_dir: str  # compiler-rt所在路径

    def _set_prefix(self) -> None:
        """设置安装路径"""
        self.prefix["llvm"] = (
            os.path.join(self.prefix_dir, self.name) if self.stage == 1 else os.path.join(self.prefix_dir, f"{self.name}-new")
        )
        self.prefix["runtimes"] = os.path.join(self.prefix["llvm"], "install")
        self.compiler_rt_dir = os.path.join(self.prefix["llvm"], "lib", "clang", self.major_version, "lib")

    def __init__(self, build: str, host: str | None, home: str, jobs: int, prefix_dir: str) -> None:
        self.build = build
        self.host = host or self.build
        name_without_version = f"{self.host}-clang"
        super().__init__(build, "20.0.0", name_without_version, home, jobs, prefix_dir)
        # 设置prefix
        self._set_prefix()
        for i in sys.argv[1:]:
            if i == "--bootstrap":
                self.bootstrap = True
            elif i.startswith("--stage="):
                self.stage = int(i[8:])
            else:
                assert False, f'Unknown option: "{i}"'
        self.llvm_option_list_1["LLVM_PARALLEL_LINK_JOBS"] = str(self.jobs // 5)
        # 非自举在第1阶段就编译clang-tools-extra
        if not self.bootstrap:
            self.llvm_option_list_1["LLVM_ENABLE_PROJECTS"] = '"clang;clang-tools-extra;lld"'
            self.llvm_option_list_1["LLVM_ENABLE_LTO"] = "Thin"
        for target, _ in filter(lambda x: x[1], scripts.host_target_list):
            target_field = target.split("-")
            self.system_list[target] = "Linux" if "linux" in target_field else "Windows"
        for lib in lib_list:
            self.prefix[lib] = os.path.join(self.home, lib, "install")
        # 设置源目录和构建目录
        for project in subproject_list:
            self.source_dir[project] = os.path.join(self.home, "llvm", project)
            self.build_dir[project] = os.path.join(self.home, "llvm", f"build-{self.host}-{project}")
            common.check_lib_dir(project, self.source_dir[project])
        for lib in lib_list:
            self.source_dir[lib] = os.path.join(self.home, lib)
            self.build_dir[lib] = os.path.join(self.source_dir[lib], "build")
            common.check_lib_dir(lib, self.source_dir[lib])
        # 设置sysroot目录
        self.sysroot_dir = os.path.join(self.home, "sysroot")
        # 第2阶段不编译运行库
        if "LLVM_ENABLE_RUNTIMES" in self.llvm_option_list_2:
            del self.llvm_option_list_2["LLVM_ENABLE_RUNTIMES"]
        self.llvm_option_list_w32_3 = {**self.llvm_option_list_3, **self.llvm_option_list_w32_1}
        if self.build != self.host:
            # 交叉编译时runtimes已经编译过了
            del self.llvm_option_list_1["LLVM_ENABLE_RUNTIMES"]
            # 设置llvm依赖库编译选项
            zlib = f'"{os.path.join(self.prefix["zlib"], "lib", "libzlibstatic.a")}"'
            self.llvm_cross_option = {
                "LIBXML2_INCLUDE_DIR": f'"{os.path.join(self.prefix["libxml2"], "include", "libxml2")}"',
                "LIBXML2_LIBRARY": f'"{os.path.join(self.prefix["libxml2"], "lib", "libxml2.dll.a")}"',
                "CLANG_ENABLE_LIBXML2": "ON",
                "ZLIB_INCLUDE_DIR": f'"{os.path.join(self.prefix["zlib"], "include")}"',
                "ZLIB_LIBRARY": zlib,
                "ZLIB_LIBRARY_RELEASE": zlib,
                "LLVM_NATIVE_TOOL_DIR": f'"{os.path.join(self.home, f'{self.build}-clang{self.major_version}', "bin")}"',
            }
        # 将自身注册到环境变量中
        self.register_in_env()

    def next_stage(self) -> None:
        """进入下一阶段"""
        self.stage += 1
        self._set_prefix()

    def get_compiler(self, target: str, *command_list_in: str) -> list[str]:
        """获取编译器选项

        Args:
            target (str): 目标平台

        Returns:
            list[str]: 编译选项
        """
        assert target in self.system_list
        gcc = f"--gcc-toolchain={self.sysroot_dir}"
        command_list: list[str] = []
        compiler_path = {"C": "clang", "CXX": "clang++", "ASM": "clang"}
        no_warning = "-Wno-unused-command-line-argument"
        for compiler in self.compiler_list:
            command_list.append(f'-DCMAKE_{compiler}_COMPILER="{compiler_path[compiler]}"')
            command_list.append(f"-DCMAKE_{compiler}_COMPILER_TARGET={target}")
            command_list.append(f'-DCMAKE_{compiler}_FLAGS="{no_warning} {gcc} {" ".join(command_list_in)}"')
            command_list.append(f"-DCMAKE_{compiler}_COMPILER_WORKS=ON")
        if target != self.build:
            command_list.append(f"-DCMAKE_SYSTEM_NAME={self.system_list[target]}")
            command_list.append(f"-DCMAKE_SYSTEM_PROCESSOR={target[: target.find('-')]}")
            command_list.append(f'-DCMAKE_SYSROOT="{self.sysroot_dir}"')
            command_list.append("-DCMAKE_CROSSCOMPILING=TRUE")
        command_list.append(f"-DLLVM_RUNTIMES_TARGET={target}")
        command_list.append(f"-DLLVM_DEFAULT_TARGET_TRIPLE={gnu_to_llvm(target)}")
        command_list.append(f"-DLLVM_HOST_TRIPLE={gnu_to_llvm(self.host)}")
        command_list.append(f'-DCMAKE_LINK_FLAGS="{" ".join(command_list_in)}"')
        return command_list

    def config(self, project: str, target: str, *command_list: str, **cmake_option_list: dict[str, str]) -> None:
        """配置项目

        Args:
            project (str): 子项目
            target (str): 目标平台
            command_list: 附加编译选项
            cmake_option_list: 附加cmake配置选项
        """
        common.remove_if_exists(self.build_dir[project])
        assert project in (*subproject_list, *lib_list)
        command = f"cmake -G Ninja --install-prefix {self.prefix[project]} -B {self.build_dir[project]} -S {self.source_dir[project]} "
        command += " ".join(self.get_compiler(target, *command_list) + get_cmake_option(**cmake_option_list))
        common.run_command(command)

    def make(self, project: str) -> None:
        """构建项目

        Args:
            project (str): 目标项目
        """
        assert project in (*subproject_list, *lib_list)
        common.run_command(f"ninja -C {self.build_dir[project]} -j{self.jobs}")

    def install(self, project: str) -> None:
        """安装项目

        Args:
            project (str): 目标项目
        """
        assert project in (*subproject_list, *lib_list)
        common.run_command(f"ninja -C {self.build_dir[project]} install/strip -j{self.jobs}")

    def remove_build_dir(self, project: str) -> None:
        """移除构建目录

        Args:
            project (str): 目标项目
        """
        assert project in subproject_list
        dir = self.build_dir[project]
        if os.path.exists(dir):
            shutil.rmtree(dir)
        if project == "runtimes":
            dir = self.prefix[project]
            if os.path.exists(dir):
                shutil.rmtree(dir)

    def build_sysroot(self, target: str) -> None:
        """构建sysroot

        Args:
            target (str): 目标平台
        """
        prefix = self.prefix["runtimes"]
        for dir in os.listdir(prefix):
            src_dir = os.path.join(prefix, dir)
            match dir:
                case "bin":
                    # 复制dll
                    dst_dir = os.path.join(self.sysroot_dir, target, "lib")
                    for file in os.listdir(src_dir):
                        if file.endswith("dll"):
                            common.copy(os.path.join(src_dir, file), os.path.join(dst_dir, file))
                case "lib":
                    dst_dir = os.path.join(self.sysroot_dir, target, "lib")
                    common.mkdir(self.compiler_rt_dir, False)
                    for item in os.listdir(src_dir):
                        # 复制compiler-rt
                        if item == self.system_list[target].lower():
                            rt_dir = os.path.join(self.compiler_rt_dir, item)
                            common.mkdir(rt_dir, False)
                            for file in os.listdir(os.path.join(src_dir, item)):
                                common.copy(os.path.join(src_dir, item, file), os.path.join(rt_dir, file))
                            continue
                        # 复制其他库
                        common.copy(os.path.join(src_dir, item), os.path.join(dst_dir, item))
                case "include":
                    # 复制__config_site
                    dst_dir = os.path.join(self.sysroot_dir, target, "include")
                    common.copy(os.path.join(src_dir, "c++", "v1", "__config_site"), os.path.join(dst_dir, "__config_site"))
                    # 对于Windows目标，需要在sysroot/include下准备一份头文件
                    dst_dir = os.path.join(self.sysroot_dir, "include", "c++")
                    common.copy(os.path.join(self.prefix["llvm"], "include", "c++"), dst_dir, False)

    def copy_llvm_libs(self) -> None:
        """复制工具链所需库"""
        src_prefix = os.path.join(self.sysroot_dir, self.host, "lib")
        dst_prefix = os.path.join(self.prefix["llvm"], "bin" if self.system_list[self.host] == "Windows" else "lib")
        native_dir = os.path.join(self.home, f"{self.build}-clang{self.major_version}")
        native_bin_dir = os.path.join(native_dir, "bin")
        native_compiler_rt_dir = os.path.join(native_dir, "lib", "clang", self.major_version, "lib")
        # 复制libc++和libunwind运行库
        for file in filter(
            lambda file: file.startswith(("libc++", "libunwind")) and not file.endswith((".a", ".json")), os.listdir(src_prefix)
        ):
            common.copy(os.path.join(src_prefix, file), os.path.join(dst_prefix, file))
        # 复制公用libc++和libunwind头文件
        src_prefix = os.path.join(native_bin_dir, "..", "include")
        dst_prefix = os.path.join(self.prefix["llvm"], "include")
        for item in filter(lambda item: "unwind" in item or item == "c++", os.listdir(src_prefix)):
            common.copy(os.path.join(src_prefix, item), os.path.join(dst_prefix, item))

        if self.build != self.host:
            # 从build下的本地工具链复制compiler-rt
            # 其他库在sysroot中，无需复制
            src_prefix = native_compiler_rt_dir
            dst_prefix = self.compiler_rt_dir
            common.copy(src_prefix, dst_prefix, True)
            # 复制libxml2
            src_path = os.path.join(self.prefix["libxml2"], "bin", "libxml2.dll")
            dst_path = os.path.join(self.prefix["llvm"], "lib", "libxml2.dll")
            common.copy(src_path, dst_path)

    def change_name(self) -> None:
        """修改多阶段自举时的安装目录名"""
        name = os.path.join(self.home, self.name)
        # clang->clang-old
        # clang-new->clang
        if not os.path.exists(f"{name}-old") and self.bootstrap:
            os.rename(name, f"{name}-old")
            os.rename(self.prefix["llvm"], name)

    def package(self) -> None:
        """打包工具链"""
        self.copy_readme()
        self.compress()
        # 编译本地工具链时才需要打包sysroot
        if self.build == self.host:
            self.compress("sysroot")
