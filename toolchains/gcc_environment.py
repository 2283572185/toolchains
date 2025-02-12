from collections.abc import Callable
from enum import StrEnum
from pathlib import Path

from . import common

lib_list = ("expat", "gcc", "binutils", "gmp", "mpfr", "linux", "mingw", "pexports", "python-embed", "glibc", "newlib")
dll_target_list = (
    "install-target-libgcc",
    "install-target-libstdc++-v3",
    "install-target-libatomic",
    "install-target-libquadmath",
    "install-target-libgomp",
)

# NOTE：添加平台后需要在此处注册dll_name_list
dll_name_list: dict[str, list[str]] = {
    "linux": [
        "libgcc_s.so.1",
        "libstdc++.so",
        "libatomic.so",
        "libquadmath.so",
        "libgomp.so",
    ],
    "w64": [
        "libgcc_s_seh-1.dll",
        "libgcc_s_dw2-1.dll",
        "libstdc++-6.dll",
        "libatomic-1.dll",
        "libquadmath-0.dll",
    ],
    "unknown": [],
}

# 带newlib的独立环境需禁用的特性列表
disable_hosted_option = (
    "--disable-threads",
    "--disable-libstdcxx-verbose",
    "--disable-shared",
    "--with-headers",
    "--disable-libsanitizer",
    "--disable-libssp",
    "--disable-libquadmath",
    "--disable-libgomp",
    "--with-newlib",
)
# 无newlib的独立环境需禁用的特性列表
disable_hosted_option_pure = (
    "--disable-threads",
    "--disable-hosted-libstdcxx",
    "--disable-libstdcxx-verbose",
    "--disable-shared",
    "--without-headers",
    "--disable-libvtv",
    "--disable-libsanitizer",
    "--disable-libssp",
    "--disable-libquadmath",
    "--disable-libgomp",
)

# 32位架构，其他32位架构需自行添加
arch_32_bit_list = ("arm", "armeb", "i486", "i686", "risc32", "risc32be")


def _get_specific_environment(self: "environment", host: str | None = None, target: str | None = None) -> "environment":
    return environment(self.build, host, target, str(self.home), self.jobs, str(self.prefix_dir), self.compress_level)


class toolchain_type(StrEnum):
    """工具链类型枚举

    Attributes:
        native        : 本地工具链，build == host == target
        cross         : 交叉工具链，build == host != target
        canadian      : 加拿大工具链，build != host == target
        canadian_cross: 加拿大交叉工具链，build != host != target
    """

    native = "native"
    cross = "cross"
    canadian = "canadian"
    canadian_cross = "canadian cross"


class environment(common.basic_environment):
    """gcc构建环境"""

    build: str  # build平台
    host: str  # host平台
    target: str  # target平台
    toolchain_type: "toolchain_type"  # 工具链类别
    cross_compiler: bool  # 是否是交叉编译器
    prefix: Path  # 工具链安装位置
    lib_prefix: Path  # 安装后库目录的前缀
    symlink_list: list[str]  # 构建过程中创建的软链接表
    share_dir: Path  # 安装后share目录
    gdbinit_path: Path  # 安装后.gdbinit文件所在路径
    lib_dir_list: dict[str, Path]  # 所有库所在目录
    tool_prefix: str  # 工具的前缀，如x86_64-w64-mingw32-
    dll_name_list: list[str]  # 该平台上需要保留调试符号的dll列表
    python_config_path: Path  # python_config.sh所在路径
    host_32_bit: bool  # 宿主环境是否是32位的
    rpath_option: str  # 设置rpath的链接选项
    rpath_dir: Path  # rpath所在目录
    freestanding: bool  # 是否为独立工具链
    host_field: common.triplet_field  # host平台各个域
    target_field: common.triplet_field  # target平台各个域

    def __init__(
        self, build: str, host: None | str, target: None | str, home: str, jobs: int, prefix_dir: str, compress_level: int
    ) -> None:
        self.build = build
        self.host = host or build
        self.target = target or self.host
        # 鉴别工具链类别
        if self.build == self.host == self.target:
            self.toolchain_type = toolchain_type.native
        elif self.build == self.host != self.target:
            self.toolchain_type = toolchain_type.cross
        elif self.build != self.host == self.target:
            self.toolchain_type = toolchain_type.canadian
        else:
            self.toolchain_type = toolchain_type.canadian_cross
        self.cross_compiler = self.host != self.target

        name_without_version = (f"{self.host}-host-{self.target}-target" if self.cross_compiler else f"{self.host}-native") + "-gcc"
        super().__init__(build, "15.0.0", name_without_version, home, jobs, prefix_dir, compress_level)

        self.prefix = self.prefix_dir / self.name
        self.lib_prefix = self.prefix / self.target if self.cross_compiler else self.prefix
        self.symlink_list = []
        self.share_dir = self.prefix / "share"
        self.gdbinit_path = self.share_dir / ".gdbinit"

        self.lib_dir_list = {}
        self.host_field = common.triplet_field(self.host)
        self.target_field = common.triplet_field(self.target)
        for lib in lib_list:
            lib_dir = self.home / lib
            match lib:
                # 支持使用厂商修改过的源代码
                case "glibc" | "linux" if self.target_field.vendor != "unknown":
                    vendor = self.target_field.vendor[1]
                    custom_lib_dir = self.home / f"{lib}-{vendor}"
                    if common.check_lib_dir(lib, custom_lib_dir, False):
                        lib_dir = custom_lib_dir
                    else:
                        print(f'Don\'t find custom lib "{lib}" in "{custom_lib_dir}", fallback to use common lib.')
                        common.check_lib_dir(lib, lib_dir)
                case _:
                    common.check_lib_dir(lib, lib_dir)
            self.lib_dir_list[lib] = lib_dir
        self.tool_prefix = f"{self.target}-" if self.cross_compiler else ""
        self.dll_name_list = dll_name_list[self.target_field.os]

        self.python_config_path = self.root_dir.parent / "script" / "python_config.sh"
        self.host_32_bit = self.host.startswith(arch_32_bit_list)
        lib_name = f'lib{"32" if self.host_32_bit else "64"}'
        self.rpath_dir = self.prefix / lib_name
        lib_path = Path("'$ORIGIN'") / ".." / lib_name
        self.rpath_option = f'"-Wl,-rpath={lib_path}"'
        # 加载工具链
        if self.toolchain_type in (toolchain_type.cross, toolchain_type.canadian, toolchain_type.canadian_cross):
            _get_specific_environment(self).register_in_env()
        if self.toolchain_type in (toolchain_type.canadian, toolchain_type.canadian_cross):
            _get_specific_environment(self, target=self.host).register_in_env()
        if self.toolchain_type == toolchain_type.canadian_cross:
            _get_specific_environment(self, target=self.target).register_in_env()
        # 将自身注册到环境变量中
        self.register_in_env()
        self.freestanding = self.target_field.abi in ("elf", "eabi")

    def enter_build_dir(self, lib: str, remove_files: bool = True) -> None:
        """进入构建目录

        Args:
            lib (str): 要构建的库
        """

        assert lib in lib_list
        build_dir = self.lib_dir_list[lib]
        need_make_build_dir = True  # 是否需要建立build目录
        match lib:
            case "python-embed" | "linux":
                need_make_build_dir = False  # 跳过python-embed和linux，python-embed仅需要生成静态库，linux有独立的编译方式
            case "expat":
                build_dir = build_dir / "expat" / "build"  # expat项目内嵌套了一层目录
            case _:
                build_dir = build_dir / "build"

        if need_make_build_dir:
            common.mkdir(build_dir, remove_files)

        _ = common.chdir_guard(build_dir)
        # 添加构建gdb所需的环境变量
        if lib == "binutils":
            common.add_environ("ORIGIN", "$$ORIGIN")
            common.add_environ("PYTHON_EMBED_PACKAGE", self.lib_dir_list["python-embed"])  # mingw下编译带python支持的gdb需要

    def configure(self, *option: str) -> None:
        """自动对库进行配置

        Args:
            option (tuple[str, ...]): 配置选项
        """

        options = " ".join(("", *option))
        # 编译glibc时LD_LIBRARY_PATH中不能包含当前路径，此处直接清空LD_LIBRARY_PATH环境变量
        common.run_command(f"../configure {options} LD_LIBRARY_PATH=")

    def make(self, *target: str, ignore_error: bool = False) -> None:
        """自动对库进行编译

        Args:
            target (tuple[str, ...]): 要编译的目标
        """

        targets = " ".join(("", *target))
        common.run_command(f"make {targets} -j {self.jobs}", ignore_error)

    def install(self, *target: str, ignore_error: bool = False) -> None:
        """自动对库进行安装

        Args:
            target (tuple[str, ...]): 要安装的目标
        """

        if target != ():
            targets = " ".join(("", *target))
        elif Path.cwd() == self.lib_dir_list["gcc"] / "build":
            common.run_command(f"make install-strip -j {self.jobs}", ignore_error)
            targets = " ".join(dll_target_list)
        else:
            targets = "install-strip"
        common.run_command(f"make {targets} -j {self.jobs}", ignore_error)

    def strip_debug_symbol(self) -> None:
        """剥离动态库的调试符号到独立的符号文件"""

        for lib_dir in filter(lambda dir: dir.name.startswith("lib"), self.lib_prefix.iterdir()):
            for dll_path in filter(lambda file: file.name in self.dll_name_list, lib_dir.iterdir()):
                symbol_path = dll_path.with_suffix(dll_path.suffix + ".debug")
                common.run_command(f"{self.tool_prefix}objcopy --only-keep-debug {dll_path} {symbol_path}")
                common.run_command(f"{self.tool_prefix}strip {dll_path}")
                common.run_command(f"{self.tool_prefix}objcopy --add-gnu-debuglink={symbol_path} {dll_path}")

    def copy_gdbinit(self) -> None:
        """复制.gdbinit文件"""

        gdbinit_src_path = self.root_dir / ".gdbinit"
        common.copy(gdbinit_src_path, self.gdbinit_path)

    def build_libpython(self) -> None:
        """创建libpython.a"""

        lib_dir = self.lib_dir_list["python-embed"]
        lib_path = lib_dir / "libpython.a"
        def_path = lib_dir / "libpython.def"
        if not lib_path.exists():
            dll_list = list(filter(lambda dll: dll.name.startswith("python") and dll.name.endswith(".dll"), lib_dir.iterdir()))
            assert dll_list != [], f'Cannot find python*.dll in "{lib_dir}" directory.'
            assert len(dll_list) == 1, f'Find too many python*.dll in "{lib_dir}" directory.'
            dll_path = lib_dir / dll_list[0]
            # 工具链最后运行在宿主平台上，故而应该使用宿主平台的工具链从.lib文件制作.a文件
            common.run_command(f"{self.host}-pexports {dll_path} > {def_path}")
            common.run_command(f"{self.host}-dlltool -D {dll_path} -d {def_path} -l {lib_path}")

    def copy_python_embed_package(self) -> None:
        """复制python embed package到安装目录"""

        for file in filter(lambda x: x.name.startswith("python"), self.lib_dir_list["python-embed"].iterdir()):
            common.copy(
                file,
                self.bin_dir / file.name,
            )

    def package(self, need_gdbinit: bool = True, need_python_embed_package: bool = False) -> None:
        """打包工具链

        Args:
            need_gdbinit (bool, optional): 是否需要打包.gdbinit文件. 默认需要.
            need_python_embed_package (bool, optional): 是否需要打包python embed package. 默认不需要.
        """

        if self.toolchain_type == "native":
            # 本地工具链需要添加cc以代替系统提供的cc
            common.symlink(self.bin_dir / "gcc", self.bin_dir / "cc")
        if need_gdbinit:
            self.copy_gdbinit()
        if need_python_embed_package:
            self.copy_python_embed_package()
        self.copy_readme()
        self.compress()

    def remove_unused_glibc_file(self) -> None:
        """移除不需要的glibc文件"""

        for dir in (
            "etc",
            "libexec",
            "sbin",
            "share",
            "var",
            "lib/gconv",
            "lib/audit",
        ):
            common.remove_if_exists(self.lib_prefix / dir)

    def strip_glibc_file(self) -> None:
        """剥离调试符号"""

        strip = f"{self.tool_prefix}strip"
        common.run_command(f"{strip} {self.lib_prefix / 'lib' / '*.so'}", True)

    def change_glibc_ldscript(self, arch: str | None = None) -> None:
        """替换带有绝对路径的链接器脚本

        Args:
            arch (str | None, optional): glibc链接器脚本的arch字段，若为None则从target中推导. 默认为 None.
                                  手动设置arch可以用于需要额外字段来区分链接器脚本的情况
        """

        arch = arch or self.target_field.arch
        dst_dir = self.lib_prefix / "lib"
        for file in filter(lambda file: file.name.startswith(f"{arch}-lib"), self.script_dir.iterdir()):
            common.copy(file, dst_dir / file.name[len(f"{arch}-") :])

    def adjust_glibc(self, arch: str | None = None) -> None:
        """调整glibc
        Args:
            arch (str | None, optional): glibc链接器脚本的arch字段，若为None则自动推导. 默认为 None.
        """

        self.remove_unused_glibc_file()
        self.strip_glibc_file()
        self.change_glibc_ldscript(arch)

    def solve_libgcc_limits(self) -> None:
        """解决libgcc的limits.h中提供错误MB_LEN_MAX的问题"""

        libgcc_prefix = self.prefix / "lib" / "gcc" / self.target
        include_path = next(libgcc_prefix.iterdir()) / "include" / "limits.h"
        with include_path.open("a") as file:
            file.writelines(("#undef MB_LEN_MAX\n", "#define MB_LEN_MAX 16\n"))

    def copy_from_cross_toolchain(self) -> None:
        """从交叉工具链中复制libc、libstdc++、libgcc、linux头文件、gdbserver等到本工具链中"""

        # 从交叉工具链中复制libc、libstdc++、linux头文件等到本工具链中
        cross_toolchain = _get_specific_environment(self, target=self.target)
        for dir in filter(lambda x: x.name != "bin", cross_toolchain.lib_prefix.iterdir()):
            common.copy(dir, self.lib_prefix / dir.name)

        # 从交叉工具链中复制libgcc到本工具链中
        common.copy(cross_toolchain.prefix / "lib" / "gcc", self.prefix / "lib" / "gcc")

        # 复制gdbserver
        common.copy_if_exist(cross_toolchain.bin_dir / "gdbserver", self.bin_dir / "gdbserver")


def get_mingw_lib_prefix_list(env: environment) -> dict[str, Path]:
    """获取mingw平台下gdb所需包的安装路径

    Args:
        env (environment): gcc环境

    Returns:
        dict[str,Path]: {包名:安装路径}
    """

    return {lib: env.home / lib / "install" for lib in ("gmp", "expat", "mpfr")}


def build_mingw_gdb_requirements(env: environment) -> None:
    """编译安装libgmp, libexpat, libmpfr"""

    lib_prefix_list = get_mingw_lib_prefix_list(env)
    for lib, prefix in lib_prefix_list.items():
        env.enter_build_dir(lib)
        env.configure(
            f"--host={env.host} --disable-shared",
            f"--prefix={prefix}",
            f"--with-gmp={lib_prefix_list['gmp']}" if lib == "mpfr" else "",
        )
        env.make()
        env.install()


def get_mingw_gdb_lib_options(env: environment) -> list[str]:
    """获取mingw平台下gdb所需包配置选项

    Args:
        env (environment): gcc环境
    """

    lib_prefix_list = get_mingw_lib_prefix_list(env)
    prefix_selector: Callable[[str], str] = lambda lib: f"--with-{lib}=" if lib in ("gmp", "mpfr") else f"--with-lib{lib}-prefix="
    return [prefix_selector(lib) + f"{lib_prefix_list[lib]}" for lib in ("gmp", "mpfr", "expat")]


def copy_pretty_printer(env: environment) -> None:
    """从x86_64-linux-gnu本地工具链中复制pretty-printer到不带newlib的独立工具链"""

    native_gcc = _get_specific_environment(env)
    for src_dir in native_gcc.share_dir.iterdir():
        if src_dir.name.startswith("gcc") and src_dir.is_dir():
            common.copy(src_dir, env.share_dir / src_dir.name)
            return


class cross_environment:
    """gcc交叉工具链配置环境"""

    env: environment  # gcc构建环境
    host_os: str  # gcc环境的host操作系统
    target_os: str  # gcc环境的target操作系统
    target_arch: str  # gcc环境的target架构
    basic_option: list[str]  # 基本选项
    libc_option: list[str]  # libc相关选项
    gcc_option: list[str]  # gcc相关选项
    gdb_option: list[str]  # gdb相关选项
    linux_option: list[str]  # linux相关选项
    gdbserver_option: list[str]  # gdbserver相关选项
    full_build: bool  # 是否进行完整自举流程
    glibc_phony_stubs_path: Path  # glibc占位文件所在路径
    adjust_glibc_arch: str  # 调整glibc链接器脚本时使用的架构名
    need_gdb: bool  # 是否需要编译gdb
    need_gdbserver: bool  # 是否需要编译gdbserver
    need_newlib: bool  # 是否需要编译newlib，仅对独立工具链有效

    def __init__(
        self,
        build: str,
        host: str,
        target: str,
        gdb: bool,
        gdbserver: bool,
        newlib: bool,
        home: str,
        jobs: int,
        prefix_dir: str,
        compress_level: int,
    ) -> None:
        """gcc交叉工具链对象

        Args:
            build (str): 构建平台
            host (str): 宿主平台
            target (str): 目标平台
            gdb (bool): 是否启用gdb
            gdbserver (bool): 是否启用gdbserver
            newlib (bool): 是否启用newlib, 仅对独立工具链有效
            home (str): 源代码树搜索主目录
            jobs (int): 并发构建数
            compress_level (int): zstd压缩等级
        """

        self.env = environment(build, host, target, home, jobs, prefix_dir, compress_level)
        self.host_os = self.env.host_field.os
        self.target_os = self.env.target_field.os
        self.target_arch = self.env.target_field.arch
        self.basic_option = [
            "--disable-werror",
            " --enable-nls",
            f"--target={self.env.target}",
            f"--prefix={self.env.prefix}",
            f"--host={self.env.host}",
        ]
        self.need_gdb, self.need_gdbserver, self.need_newlib = gdb, gdbserver, newlib

        libc_option_list = {
            "linux": [f"--prefix={self.env.lib_prefix}", f"--host={self.env.target}", f"--build={self.env.build}", "--disable-werror"],
            "w64": [f"--host={self.env.target}", f"--prefix={self.env.lib_prefix}", "--with-default-msvcrt=ucrt", "--disable-werror"],
            # newlib会自动设置安装路径的子目录
            "unknown": [f"--prefix={self.env.prefix}", f"--target={self.env.target}", f"--build={self.env.build}", "--disable-werror"],
        }
        self.libc_option = libc_option_list[self.target_os]

        gcc_option_list = {
            "linux": ["--disable-bootstrap"],
            "w64": ["--disable-sjlj-exceptions", "--enable-threads=win32"],
            "unknown": [*disable_hosted_option] if self.need_newlib else [*disable_hosted_option_pure],
        }
        self.gcc_option = [
            *gcc_option_list[self.target_os],
            "--enable-languages=c,c++",
            "--disable-multilib",
        ]

        gdb_option_list = {
            "linux": [f"LDFLAGS={self.env.rpath_option}"],
            "w64": [
                f"--with-python={self.env.python_config_path}",
                "CXXFLAGS=-D_WIN32_WINNT=0x0600",
                "--with-expat",
                *get_mingw_gdb_lib_options(self.env),
            ],
        }
        self.gdb_option = (
            [
                *gdb_option_list[self.host_os],
                f"--with-system-gdbinit={self.env.gdbinit_path}",
                "--disable-gdbserver",
                "--enable-gdb",
            ]
            if gdb
            else ["--disable-gdbserver", "--disable-gdb"]
        )
        # 创建libpython.a
        if gdb and self.host_os == "w64":
            self.env.build_libpython()

        linux_arch_list = {"i686": "x86", "x86_64": "x86", "arm": "arm", "aarch64": "arm64", "loongarch64": "loongarch", "riscv64": "riscv"}
        self.linux_option = [f"ARCH={linux_arch_list[self.target_arch]}", f"INSTALL_HDR_PATH={self.env.lib_prefix}", "headers_install"]

        self.gdbserver_option = (
            ["--disable-gdb", f"--host={self.env.target}", "--enable-gdbserver", "--disable-binutils"] if gdbserver else []
        )

        # Linux到其他平台交叉和Windows到Linux交叉需要完整编译
        self.full_build = self.host_os == "linux" or self.target_os == "linux" and self.target_arch in ("i686", "x86_64")
        # 编译不完整libgcc时所需的stubs.h所在路径
        self.glibc_phony_stubs_path = self.env.lib_prefix / "include" / "gnu" / "stubs.h"
        # 由相关函数自动推动架构名
        self.adjust_glibc_arch = ""

    def _after_build_gcc(self) -> None:
        """在编译完gcc后完成收尾工作"""

        # 从完整工具链复制文件
        if not self.full_build:
            self.env.copy_from_cross_toolchain()
        if self.need_gdb and not self.need_newlib:
            copy_pretty_printer(self.env)

        # 编译gdbserver
        if self.need_gdbserver:
            self.env.solve_libgcc_limits()
            self.env.enter_build_dir("binutils")
            self.env.configure(*self.basic_option, *self.gdbserver_option)
            self.env.make()
            self.env.install("install-strip-gdbserver")

        # 复制gdb所需运行库
        if self.need_gdb:
            gcc = _get_specific_environment(self.env, target=self.env.host)
            if self.host_os == "linux":
                for dll in ("libstdc++.so.6", "libgcc_s.so.1"):
                    common.copy(gcc.rpath_dir / dll, self.env.rpath_dir)
            else:
                for dll in ("libstdc++-6.dll", "libgcc_s_seh-1.dll"):
                    common.copy(gcc.lib_prefix / "lib" / dll, self.env.bin_dir)

        # 打包工具链
        self.env.package(self.need_gdb, self.need_gdb and self.host_os == "w64")

    def _full_build_linux(self) -> None:
        """完整自举target为linux的gcc"""

        # 编译binutils，如果启用gdb则一并编译
        self.env.enter_build_dir("binutils")
        self.env.configure(*self.basic_option, *self.gdb_option)
        self.env.make()
        self.env.install()

        # 编译gcc
        self.env.enter_build_dir("gcc")
        self.env.configure(*self.basic_option, *self.gcc_option, "--disable-shared")
        self.env.make("all-gcc")
        self.env.install("install-strip-gcc")

        # 安装Linux头文件
        self.env.enter_build_dir("linux")
        self.env.make(*self.linux_option)

        # 安装glibc头文件
        self.env.enter_build_dir("glibc")
        self.env.configure(*self.libc_option, "libc_cv_forced_unwind=yes")
        self.env.make("install-headers")
        # 为了跨平台，不能使用mknod
        with open(self.glibc_phony_stubs_path, "w"):
            pass

        # 编译安装libgcc
        self.env.enter_build_dir("gcc", False)
        self.env.make("all-target-libgcc")
        self.env.install("install-target-libgcc")

        # 编译安装glibc
        self.env.enter_build_dir("glibc")
        self.env.configure(*self.libc_option)
        self.env.make()
        self.env.install("install")
        self.env.adjust_glibc("arm-sf")

        # 编译完整gcc
        self.env.enter_build_dir("gcc")
        self.env.configure(*self.basic_option, *self.gcc_option)
        self.env.make()
        self.env.install()
        self.env.strip_debug_symbol()

        # 完成后续工作
        self._after_build_gcc()

    def _full_build_mingw(self) -> None:
        """完整自举target为mingw的gcc"""

        # 编译binutils，如果启用gdb则一并编译
        self.env.enter_build_dir("binutils")
        self.env.configure(*self.basic_option, *self.gdb_option)
        self.env.make()
        self.env.install()

        # 编译gcc和libgcc
        self.env.enter_build_dir("gcc")
        self.env.configure(*self.basic_option, *self.gcc_option, "--disable-shared")
        self.env.make("all-gcc all-target-libgcc")
        self.env.install("install-strip-gcc install-target-libgcc")

        # 编译完整mingw-w64
        self.env.enter_build_dir("mingw")
        self.env.configure(*self.libc_option)
        self.env.make()
        self.env.install()

        # 编译完整的gcc
        self.env.enter_build_dir("gcc")
        self.env.configure(*self.basic_option, *self.gcc_option)
        self.env.make()
        self.env.install()
        self.env.strip_debug_symbol()

        # 编译pexports
        self.env.enter_build_dir("pexports")
        self.env.configure(f"--prefix={self.env.prefix}")
        self.env.make()
        self.env.install()
        # 添加target前缀
        common.rename(self.env.bin_dir / "pexports", self.env.bin_dir / f"{self.env.target}-pexports")
        # 完成后续工作
        self._after_build_gcc()

    def _full_build_freestanding(self) -> None:
        """完整自举target为独立平台的gcc"""

        # 编译binutils，如果启用gdb则一并编译
        self.env.enter_build_dir("binutils")
        self.env.configure(*self.basic_option, *self.gdb_option)
        self.env.make()
        self.env.install()

        if self.need_newlib:
            # 编译安装gcc
            self.env.enter_build_dir("gcc")
            self.env.configure(*self.basic_option, *self.gcc_option)
            self.env.make("all-gcc")
            self.env.install("install-strip-gcc")

            # 编译安装newlib
            self.env.enter_build_dir("newlib")
            self.env.configure(*self.libc_option)
            self.env.make()
            self.env.install()

            # 编译安装完整gcc
            self.env.enter_build_dir("gcc", False)
            self.env.make()
            self.env.install()
            self.env.strip_debug_symbol()
        else:
            # 编译安装完整gcc
            self.env.enter_build_dir("gcc")
            self.env.configure(*self.basic_option, *self.gcc_option)
            self.env.make()
            self.env.install("install-strip")

        # 完成后续工作
        self._after_build_gcc()

    def _partial_build(self) -> None:
        """编译gcc而无需自举"""

        # 编译binutils，如果启用gdb则一并编译
        self.env.enter_build_dir("binutils")
        self.env.configure(*self.basic_option, *self.gdb_option)
        self.env.make()
        self.env.install()

        # 编译安装gcc
        self.env.enter_build_dir("gcc")
        self.env.configure(*self.basic_option, *self.gcc_option)
        self.env.make("all-gcc")
        self.env.install("install-strip-gcc")

        # 完成后续工作
        self._after_build_gcc()

    def build(self) -> None:
        """构建gcc工具链"""

        # 编译gdb依赖库
        if self.need_gdb and self.host_os == "w64":
            build_mingw_gdb_requirements(self.env)
        if self.full_build:
            assert self.target_os in ("linux", "w64", "unknown")
            match (self.target_os):
                case "linux":
                    self._full_build_linux()
                case "w64":
                    self._full_build_mingw()
                case "unknown":
                    self._full_build_freestanding()
        else:
            self._partial_build()


assert __name__ != "__main__", "Import this file instead of running it directly."
