from collections.abc import Callable
from pathlib import Path

from . import common

lib_list = ("expat", "gcc", "binutils", "gmp", "mpfr", "linux", "mingw", "pexports", "python-embed", "glibc", "newlib")

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


def get_specific_environment(self: common.basic_environment, host: str | None = None, target: str | None = None) -> "environment":
    """在一个basic_environment的配置基础上获取指定配置的gcc环境

    Args:
        self (common.basic_environment): 基环境
        host (str | None, optional): 指定的host平台. 默认使用self中的配置.
        target (str | None, optional): 指定的target平台. 默认使用self中的配置.

    Returns:
        environment: 指定配置的gcc环境
    """

    return environment(self.build, host, target, self.home, self.jobs, self.prefix_dir, self.compress_level, True)


class environment(common.basic_environment):
    """gcc构建环境"""

    build: str  # build平台
    host: str  # host平台
    target: str  # target平台
    toolchain_type: common.toolchain_type  # 工具链类别
    cross_compiler: bool  # 是否是交叉编译器
    prefix: Path  # 工具链安装位置
    lib_prefix: Path  # 安装后库目录的前缀]
    share_dir: Path  # 安装后share目录
    gdbinit_path: Path  # 安装后.gdbinit文件所在路径
    lib_dir_list: dict[str, Path]  # 所有库所在目录
    tool_prefix: str  # 工具的前缀，如x86_64-w64-mingw32-
    python_config_path: Path  # python_config.sh所在路径
    host_32_bit: bool  # host平台是否是32位的
    target_32_bit: bool  # target平台是否是32位的
    rpath_option: str  # 设置rpath的链接选项
    rpath_dir: Path  # rpath所在目录
    freestanding: bool  # 是否为独立工具链
    host_field: common.triplet_field  # host平台各个域
    target_field: common.triplet_field  # target平台各个域

    def __init__(
        self,
        build: str,
        host: None | str,
        target: None | str,
        home: Path,
        jobs: int,
        prefix_dir: Path,
        compress_level: int,
        simple: bool = False,
    ) -> None:
        self.build = build
        self.host = host or build
        self.target = target or self.host
        # 鉴别工具链类别
        self.toolchain_type = common.toolchain_type.classify_toolchain(self.build, self.host, self.target)
        self.freestanding = self.toolchain_type.contain(common.toolchain_type.freestanding)
        self.cross_compiler = self.toolchain_type.contain(common.toolchain_type.cross | common.toolchain_type.canadian_cross)

        name_without_version = (f"{self.host}-host-{self.target}-target" if self.cross_compiler else f"{self.host}-native") + "-gcc"
        super().__init__(build, "15.0.1", name_without_version, home, jobs, prefix_dir, compress_level)

        self.prefix = self.prefix_dir / self.name
        self.lib_prefix = self.prefix / self.target if not self.toolchain_type.contain(common.toolchain_type.canadian) else self.prefix
        self.share_dir = self.prefix / "share"
        self.gdbinit_path = self.share_dir / ".gdbinit"
        self.host_32_bit = self.host.startswith(arch_32_bit_list)
        self.target_32_bit = self.target.startswith(arch_32_bit_list)
        lib_name = f'lib{"32" if self.host_32_bit else "64"}'
        self.rpath_dir = self.prefix / lib_name
        lib_path = Path("'$ORIGIN'") / ".." / lib_name
        self.rpath_option = f"-Wl,-rpath={lib_path}"

        if simple:
            return

        self.lib_dir_list = {}
        self.host_field = common.triplet_field(self.host, True)
        self.target_field = common.triplet_field(self.target, True)
        for lib in lib_list:
            lib_dir = self.home / lib
            match lib:
                # 支持使用厂商修改过的源代码
                case "glibc" | "linux" if self.target_field.vendor != "unknown":
                    vendor = self.target_field.vendor
                    custom_lib_dir = self.home / f"{lib}-{vendor}"
                    if common.check_lib_dir(lib, custom_lib_dir, False):
                        lib_dir = custom_lib_dir
                    else:
                        common.toolchains_print(
                            common.toolchains_warning(f'Can\'t find custom lib "{lib}" in "{custom_lib_dir}", fallback to use common lib.')
                        )
                        common.check_lib_dir(lib, lib_dir)
                case _:
                    common.check_lib_dir(lib, lib_dir)
            self.lib_dir_list[lib] = lib_dir
        self.tool_prefix = f"{self.target}-" if self.cross_compiler else ""

        self.python_config_path = self.root_dir.parent / "script" / "python_config.sh"
        # 加载工具链
        if self.toolchain_type.contain(common.toolchain_type.cross | common.toolchain_type.canadian | common.toolchain_type.canadian_cross):
            get_specific_environment(self).register_in_env()
        if self.toolchain_type.contain(common.toolchain_type.canadian | common.toolchain_type.canadian_cross):
            get_specific_environment(self, target=self.host).register_in_env()
        if self.toolchain_type.contain(common.toolchain_type.canadian_cross):
            get_specific_environment(self, target=self.target).register_in_env()
        # 将自身注册到环境变量中
        self.register_in_env()

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

        common.chdir(build_dir)
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
        common.run_command(f"../configure {common.command_quiet.get_option()} {options} LD_LIBRARY_PATH=")

    def make(self, *target: str, ignore_error: bool = False) -> None:
        """自动对库进行编译

        Args:
            target (tuple[str, ...]): 要编译的目标
        """

        targets = " ".join(("", *target))
        common.run_command(f"make {common.command_quiet.get_option()} {targets} -j {self.jobs}", ignore_error)

    def install(self, *target: str, ignore_error: bool = False) -> None:
        """自动对库进行安装

        Args:
            target (tuple[str, ...]): 要安装的目标
        """

        if target != ():
            targets = " ".join(("", *target))
        else:
            targets = "install-strip"
        common.run_command(f"make {common.command_quiet.get_option()} {targets} -j {self.jobs}", ignore_error)

    def copy_gdbinit(self) -> None:
        """复制.gdbinit文件"""

        gdbinit_src_path = self.root_dir.parent / "script" / ".gdbinit"
        common.copy(gdbinit_src_path, self.gdbinit_path)

    def build_libpython(self) -> None:
        """创建libpython.a"""

        lib_dir = self.lib_dir_list["python-embed"]
        lib_path = lib_dir / "libpython.a"
        def_path = lib_dir / "libpython.def"
        if not lib_path.exists():
            dll_list = list(filter(lambda dll: dll.name.startswith("python") and dll.name.endswith(".dll"), lib_dir.iterdir()))
            assert dll_list != [], common.toolchains_error(f'Cannot find python*.dll in "{lib_dir}" directory.')
            assert len(dll_list) == 1, common.toolchains_error(f'Find too many python*.dll in "{lib_dir}" directory.')
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
            common.symlink(Path("gcc"), self.bin_dir / "cc")
        if need_gdbinit:
            self.copy_gdbinit()
        if need_python_embed_package:
            self.copy_python_embed_package()
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
        common.run_command(f"{strip} {self.lib_prefix / 'lib' / '*.so.*'}", True)

    def change_glibc_ldscript(self, arch: str | None = None) -> None:
        """替换带有绝对路径的链接器脚本

        Args:
            arch (str | None, optional): glibc链接器脚本的arch字段，若为None则从target中推导. 默认为 None.
                                  手动设置arch可以用于需要额外字段来区分链接器脚本的情况
        """

        arch = arch or self.target_field.arch
        dst_dir = self.lib_prefix / "lib"
        for file in filter(lambda file: file.name.startswith(f"{arch}-lib"), self.script_dir.iterdir()):
            if file.suffix == ".py":
                with common.dynamic_import_module(file) as module:
                    generate_ldscript: Callable[[Path], None] = common.dynamic_import_function("main", module)
                    generate_ldscript(dst_dir)
            else:
                common.copy(file, dst_dir / file.name[len(f"{arch}-") :])

    def adjust_glibc(self, arch: str | None = None) -> None:
        """调整glibc
        Args:
            arch (str | None, optional): glibc链接器脚本的arch字段，若为None则自动推导. 默认为 None.
        """

        self.remove_unused_glibc_file()
        self.strip_glibc_file()
        self.change_glibc_ldscript(arch)
        symlink_path = self.lib_prefix / "lib" / "libmvec_nonshared.a"
        if not symlink_path.exists():
            common.symlink_if_exist(Path("libmvec.a"), symlink_path)

    def solve_libgcc_limits(self) -> None:
        """解决libgcc的limits.h中提供错误MB_LEN_MAX的问题"""

        libgcc_prefix = self.prefix / "lib" / "gcc" / self.target
        include_path = next(libgcc_prefix.iterdir()) / "include" / "limits.h"
        with include_path.open("a") as file:
            file.writelines(("#undef MB_LEN_MAX\n", "#define MB_LEN_MAX 16\n"))

    def copy_from_other_toolchain(self, need_gdbserver: bool) -> bool:
        """从交叉工具链或本地工具链中复制libc、libstdc++、libgcc、linux头文件、gdbserver等到本工具链中

        Args:
            need_gdbserver (bool): 是否需要复制gdbserver

        Returns:
            bool: gdbserver是否成功复制
        """

        # 复制libc、libstdc++、linux头文件等到本工具链中
        toolchain = get_specific_environment(self, target=self.target)
        for dir in filter(lambda x: x.name != "bin", toolchain.lib_prefix.iterdir()):
            common.copy(dir, self.lib_prefix / dir.name)

        # 复制libgcc到本工具链中
        common.copy(toolchain.prefix / "lib" / "gcc", self.prefix / "lib" / "gcc")

        # 复制gdbserver
        if need_gdbserver:
            gdbserver = "gdbserver" if self.target_field.os == "linux" else "gdbserver.exe"
            return bool(common.copy_if_exist(toolchain.bin_dir / gdbserver, self.bin_dir / gdbserver))
        else:
            return False


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
        host_file = prefix / ".host"
        try:
            host = host_file.read_text()
        except:
            host = ""
        if host == env.host:
            continue  # 已经存在则跳过构建
        env.enter_build_dir(lib)
        env.configure(
            f"--host={env.host} --disable-shared --enable-static",
            f"--prefix={prefix}",
            f"--with-gmp={lib_prefix_list['gmp']}" if lib == "mpfr" else "",
            'CFLAGS="-O3 -std=c11"',
            'CXXFLAGS="-O3"',
        )
        env.make()
        env.install()
        host_file.write_text(env.host)


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

    native_gcc = get_specific_environment(env)
    for src_dir in native_gcc.share_dir.iterdir():
        if src_dir.name.startswith("gcc") and src_dir.is_dir():
            common.copy(src_dir, env.share_dir / src_dir.name)
            return


class build_environment:
    """gcc工具链构建环境"""

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
    native_or_canadian = common.toolchain_type.native | common.toolchain_type.canadian  # host == target

    def __init__(
        self,
        build: str,
        host: str,
        target: str,
        gdb: bool,
        gdbserver: bool,
        newlib: bool,
        home: Path,
        jobs: int,
        prefix_dir: Path,
        nls: bool,
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
            home (Path): 源代码树搜索主目录
            jobs (int): 并发构建数
            prefix_dir (Path): 安装根目录
            nls (bool): 是否启用nls
            compress_level (int): zstd压缩等级
        """

        self.env = environment(build, host, target, home, jobs, prefix_dir, compress_level)
        self.host_os = self.env.host_field.os
        self.target_os = self.env.target_field.os
        self.target_arch = self.env.target_field.arch
        self.basic_option = [
            "--disable-werror",
            " --enable-nls" if nls else "--disable-nls",
            f"--build={self.env.build}",
            f"--target={self.env.target}",
            f"--prefix={self.env.prefix}",
            f"--host={self.env.host}",
            "CFLAGS=-O3",
            "CXXFLAGS=-O3",
        ]
        self.need_gdb, self.need_gdbserver, self.need_newlib = gdb, gdbserver, newlib
        assert not self.env.freestanding or not self.need_gdbserver, common.toolchains_error(
            "Cannot build gdbserver for freestanding platform.\n" "You should use other server implementing the gdb protocol like OpenOCD."
        )

        libc_option_list = {
            "linux": [f"--prefix={self.env.lib_prefix}", f"--host={self.env.target}", f"--build={self.env.build}", "--disable-werror"],
            "w64": [
                f"--host={self.env.target}",
                f"--prefix={self.env.lib_prefix}",
                "--with-default-msvcrt=ucrt",
                "--disable-werror",
            ],
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

        w64_gdbsupport_option = 'CXXFLAGS="-O3 -D_WIN32_WINNT=0x0600"'
        gdb_option_list = {
            "linux": [f'LDFLAGS="{self.env.rpath_option}"', "--with-python=/usr/bin/python3"],
            "w64": [
                f"--with-python={self.env.python_config_path}",
                w64_gdbsupport_option,
                "--with-expat",
                *get_mingw_gdb_lib_options(self.env),
            ],
        }
        enable_gdbserver_when_build_gdb = gdbserver and self.env.toolchain_type.contain(self.native_or_canadian)
        gdbserver_option = "--enable-gdbserver" if enable_gdbserver_when_build_gdb else "--disable-gdbserver"
        self.gdb_option = (
            [
                *gdb_option_list[self.host_os],
                f"--with-system-gdbinit={self.env.gdbinit_path}",
                gdbserver_option,
                "--enable-gdb",
                "--disable-unit-tests",
            ]
            if gdb
            else [gdbserver_option, "--disable-gdb"]
        )
        # 创建libpython.a
        if gdb and self.host_os == "w64":
            self.env.build_libpython()

        linux_arch_list = {
            "i686": "x86",
            "x86_64": "x86",
            "arm": "arm",
            "aarch64": "arm64",
            "loongarch64": "loongarch",
            "riscv64": "riscv",
            "mips64el": "mips",
        }
        self.linux_option = [f"ARCH={linux_arch_list[self.target_arch]}", f"INSTALL_HDR_PATH={self.env.lib_prefix}", "headers_install"]

        self.gdbserver_option = ["--disable-gdb", f"--host={self.env.target}", "--enable-gdbserver", "--disable-binutils"]
        if self.target_os == "w64":
            self.gdbserver_option.append(w64_gdbsupport_option)

        # 本地工具链和交叉工具链需要完整编译
        self.full_build = self.env.toolchain_type.contain(common.toolchain_type.native | common.toolchain_type.cross)
        # 编译不完整libgcc时所需的stubs.h所在路径
        self.glibc_phony_stubs_path = self.env.lib_prefix / "include" / "gnu" / "stubs.h"
        # 由相关函数自动推动架构名
        self.adjust_glibc_arch = ""

    def after_build_gcc(self, skip_gdbserver: bool = False) -> None:
        """在编译完gcc后完成收尾工作

        Args:
            skip_gdbserver (bool, optional): 跳过gdbserver构建. 默认为False.
        """

        self.need_gdbserver = self.need_gdbserver and not skip_gdbserver
        # 从完整工具链复制文件
        if not self.full_build:
            copy_success = self.env.copy_from_other_toolchain(self.need_gdbserver)
            self.need_gdbserver = self.need_gdbserver and not copy_success
        if self.need_gdb and self.env.freestanding and not self.need_newlib:
            copy_pretty_printer(self.env)

        # 编译gdbserver
        if self.need_gdbserver:
            self.env.solve_libgcc_limits()
            self.env.enter_build_dir("binutils")
            self.env.configure(*self.basic_option, *self.gdbserver_option)
            self.env.make()
            self.env.install("install-strip-gdbserver")

        # 复制gdb所需运行库
        if self.need_gdb and not self.env.toolchain_type.contain(self.native_or_canadian):
            gcc = get_specific_environment(self.env, target=self.env.host)
            if self.host_os == "linux":
                for dll in ("libstdc++.so.6", "libgcc_s.so.1"):
                    common.copy(gcc.rpath_dir / dll, self.env.rpath_dir / dll, follow_symlinks=True)
            else:
                for dll in ("libstdc++-6.dll", "libgcc_s_seh-1.dll"):
                    common.copy(gcc.lib_prefix / "lib" / dll, self.env.bin_dir / dll)

        # 打包工具链
        self.env.package(self.need_gdb, self.need_gdb and self.host_os == "w64")

    @staticmethod
    def native_build_linux(build_env: "build_environment") -> None:
        """编译linux本地工具链

        Args:
            build_env (build_environment): gcc构建环境
        """

        env = build_env.env
        # 编译gcc
        env.enter_build_dir("gcc")
        env.configure(*build_env.basic_option, *build_env.gcc_option)
        env.make()
        env.install()

        # 安装Linux头文件
        env.enter_build_dir("linux")
        env.make(*build_env.linux_option)

        # 编译安装glibc
        env.enter_build_dir("glibc")
        env.configure(*build_env.libc_option)
        env.make()
        env.install("install")
        env.adjust_glibc(build_env.adjust_glibc_arch)

        # 编译binutils，如果启用gdb和gdbserver则一并编译
        env.enter_build_dir("binutils")
        env.configure(*build_env.basic_option, *build_env.gdb_option)
        env.make()
        env.install()
        # 完成后续工作
        build_env.after_build_gcc(True)

    @staticmethod
    def full_build_linux(build_env: "build_environment") -> None:
        """完整自举target为linux的gcc

        Args:
            build_env (build_environment): gcc构建环境
        """

        env = build_env.env
        # 编译binutils，如果启用gdb则一并编译
        env.enter_build_dir("binutils")
        env.configure(*build_env.basic_option, *build_env.gdb_option)
        env.make()
        env.install()

        # 编译gcc
        env.enter_build_dir("gcc")
        env.configure(*build_env.basic_option, *build_env.gcc_option, "--disable-shared")
        env.make("all-gcc")
        env.install("install-strip-gcc")

        # 安装Linux头文件
        env.enter_build_dir("linux")
        env.make(*build_env.linux_option)

        # 安装glibc头文件
        env.enter_build_dir("glibc")
        env.configure(*build_env.libc_option, "libc_cv_forced_unwind=yes")
        env.make("install-headers")
        # 为了跨平台，不能使用mknod
        with open(build_env.glibc_phony_stubs_path, "w"):
            pass

        # 编译安装libgcc
        env.enter_build_dir("gcc", False)
        env.make("all-target-libgcc")
        env.install("install-target-libgcc")

        # 编译安装glibc
        env.enter_build_dir("glibc")
        env.configure(*build_env.libc_option)
        env.make()
        env.install("install")
        env.adjust_glibc(build_env.adjust_glibc_arch)

        # 编译完整gcc
        env.enter_build_dir("gcc")
        env.configure(*build_env.basic_option, *build_env.gcc_option)
        env.make()
        env.install()

        # 完成后续工作
        build_env.after_build_gcc()

    def build_pexports(self) -> None:
        # 编译pexports
        self.env.enter_build_dir("pexports")
        self.env.configure(
            f"--prefix={self.env.prefix} --host={self.env.host}",
            "CFLAGS=-O3",
            "CXXFLAGS=-O3",
        )
        self.env.make()
        self.env.install()
        # 为交叉工具链添加target前缀
        if not self.env.toolchain_type.contain(self.native_or_canadian):
            pexports = "pexports.exe" if self.host_os == "w64" else "pexports"
            common.rename(self.env.bin_dir / pexports, self.env.bin_dir / f"{self.env.target}-{pexports}")

    @staticmethod
    def full_build_mingw(build_env: "build_environment") -> None:
        """完整自举target为mingw的gcc

        Args:
            build_env (build_environment): gcc构建环境
        """

        env = build_env.env
        # 编译binutils，如果启用gdb则一并编译
        env.enter_build_dir("binutils")
        env.configure(*build_env.basic_option, *build_env.gdb_option)
        env.make()
        env.install()

        # 编译安装mingw-w64头文件
        env.enter_build_dir("mingw")
        env.configure(*build_env.libc_option, "--without-crt")
        env.make()
        env.install()

        # 编译gcc和libgcc
        env.enter_build_dir("gcc")
        env.configure(*build_env.basic_option, *build_env.gcc_option, "--disable-shared")
        env.make("all-gcc all-target-libgcc")
        env.install("install-strip-gcc install-target-libgcc")

        # 编译完整mingw-w64
        env.enter_build_dir("mingw")
        env.configure(*build_env.libc_option)
        env.make()
        env.install()

        # 编译完整的gcc
        env.enter_build_dir("gcc")
        env.configure(*build_env.basic_option, *build_env.gcc_option)
        env.make()
        env.install()

        build_env.build_pexports()
        # 完成后续工作
        build_env.after_build_gcc()

    @staticmethod
    def full_build_freestanding(build_env: "build_environment") -> None:
        """完整自举target为独立平台的gcc

        Args:
            build_env (build_environment): gcc构建环境
        """

        env = build_env.env
        # 编译binutils，如果启用gdb则一并编译
        env.enter_build_dir("binutils")
        env.configure(*build_env.basic_option, *build_env.gdb_option)
        env.make()
        env.install()

        if build_env.need_newlib:
            # 编译安装gcc
            env.enter_build_dir("gcc")
            env.configure(*build_env.basic_option, *build_env.gcc_option)
            env.make("all-gcc")
            env.install("install-strip-gcc")

            # 编译安装newlib
            env.enter_build_dir("newlib")
            env.configure(*build_env.libc_option)
            env.make()
            env.install()

            # 编译安装完整gcc
            env.enter_build_dir("gcc", False)
            env.make()
            env.install()
        else:
            # 编译安装完整gcc
            env.enter_build_dir("gcc")
            env.configure(*build_env.basic_option, *build_env.gcc_option)
            env.make()
            env.install("install-strip")

        # 完成后续工作
        build_env.after_build_gcc()

    @staticmethod
    def partial_build(build_env: "build_environment") -> None:
        """编译gcc而无需自举

        Args:
            build_env (build_environment): gcc构建环境
        """

        env = build_env.env
        # 编译binutils，如果启用gdb则一并编译
        env.enter_build_dir("binutils")
        env.configure(*build_env.basic_option, *build_env.gdb_option)
        env.make()
        env.install()

        # 编译安装gcc
        env.enter_build_dir("gcc")
        env.configure(*build_env.basic_option, *build_env.gcc_option)
        env.make("all-gcc")
        env.install("install-strip-gcc")

        # 有需要则编译安装pexports
        if build_env.target_os == "w64":
            build_env.build_pexports()

        # 完成后续工作
        build_env.after_build_gcc()

    def build(self) -> None:
        """构建gcc工具链"""

        # 编译gdb依赖库
        if self.need_gdb and self.host_os == "w64":
            build_mingw_gdb_requirements(self.env)
        if self.env.toolchain_type.contain(common.toolchain_type.native):
            self.native_build_linux(self)
        elif self.full_build:
            assert self.target_os in ("linux", "w64", "unknown")
            match (self.target_os):
                case "linux":
                    self.full_build_linux(self)
                case "w64":
                    self.full_build_mingw(self)
                case "unknown":
                    self.full_build_freestanding(self)
        else:
            self.partial_build(self)


assert __name__ != "__main__", "Import this file instead of running it directly."
