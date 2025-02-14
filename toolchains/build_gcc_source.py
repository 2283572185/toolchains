import os
import pathlib
import typing
from subprocess import CompletedProcess

from . import common
from .gcc_environment import build_environment as environment


class modifier_list:
    """针对特定平台修改gcc构建环境的回调函数"""

    @staticmethod
    def arm_linux_gnueabi(env: environment) -> None:
        """针对arm-linux-gnueabi平台使用arm-sf的链接器脚本

        Args:
            env (environment): 当前gcc构建平台
        """

        env.adjust_glibc_arch = "arm-sf"

    @staticmethod
    def arm_linux_gnueabihf(env: environment) -> None:
        """针对arm-linux-gnueabihf平台使用arm-hf的链接器脚本

        Args:
            env (environment): 当前gcc构建平台
        """

        env.adjust_glibc_arch = "arm-hf"

    @staticmethod
    def loongarch64_loongnix_linux_gnu(env: environment) -> None:
        """针对loongarch64-loongnix-linux-gnu平台
        1. 使用loongarch64-loongnix的链接器脚本
        2. glibc添加--enable-obsolete-rpc选项
        3. gcc添加--disable-libsanitizer选项

        Args:
            env (environment): 当前gcc构建平台
        """

        env.adjust_glibc_arch = "loongarch64-loongnix"
        env.libc_option.append("--enable-obsolete-rpc")
        env.gcc_option.append("--disable-libsanitizer")

    @staticmethod
    def x86_64_w64_mingw32(env: environment) -> None:
        env.libc_option += ["--disable-lib32", "--enable-lib64"]

    @staticmethod
    def i686_w64_mingw32(env: environment) -> None:
        env.libc_option += ["--disable-lib64", "--enable-lib32"]

    @staticmethod
    def modify(env: environment, target: str) -> None:
        target = target.replace("-", "_")
        if modifier := getattr(modifier_list, target, None):
            modifier(env)


class support_platform_list:
    """受支持的平台列表，不包含vendor字段

    Attributes:
        host_list  : 支持的GCC工具链宿主平台
        target_list: 支持的GCC工具链目标平台
    """

    host_list: typing.Final[list[str]] = ["x86_64-linux-gnu", "x86_64-w64-mingw32"]
    target_list: typing.Final[list[str]] = [
        "x86_64-linux-gnu",
        "i686-linux-gnu",
        "aarch64-linux-gnu",
        "arm-linux-gnueabi",
        "arm-linux-gnueabihf",
        "loongarch64-linux-gnu",
        "riscv64-linux-gnu",
        "x86_64-w64-mingw32",
        "i686-w64-mingw32",
        "arm-none-eabi",
        "x86_64-elf",
    ]


def get_default_build_platform() -> str | None:
    result: CompletedProcess[str] | None = common.run_command("gcc -dumpmachine", True, True, False, False)
    return result.stdout.strip() if result else None


class configure(common.basic_configure):
    """gcc构建配置"""

    build: str | None
    gdb: bool
    gdbserver: bool
    newlib: bool
    jobs: int
    prefix_dir: pathlib.Path
    nls: bool
    compress_level: int

    def __init__(
        self,
        build: str | None = None,
        gdb: bool = True,
        gdbserver: bool = True,
        newlib: bool = True,
        jobs: int | None = None,
        prefix_dir: str | None = None,
        nls: bool = True,
        compress_level: int = 19,
    ) -> None:
        """设置gcc构建配置

        Args:
            build (str | None, optional): 构建平台. 默认为gcc -dumpmachine输出的结果，即当前平台.
            gdb (bool, optional): 是否构建gdb. 默认为构建.
            gdbserver (bool, optional): 是否构建gdbserver. 默认为构建.
            newlib (bool, optional): 是否为独立工具链构建newlib. 默认为构建.
            jobs (int | None, optional): 构建时的并发数. 默认为当前平台cpu核心数的1.5倍.
            prefix_dir (str | None, optional): 工具链安装根目录. 默认为用户主目录.
            nls (bool, optional): 是否启用nls. 默认为启用.
            compress_level (int, optional): zstd压缩等级(1~19). 默认为19级
        """

        self.build = build or get_default_build_platform()
        self.gdb = gdb
        self.gdbserver = gdbserver
        self.newlib = newlib
        self.jobs = jobs or (os.cpu_count() or 1) + 2
        self.prefix_dir = pathlib.Path(prefix_dir) if prefix_dir else pathlib.Path.home()
        self.nls = nls
        self.compress_level = compress_level

    def check(self) -> None:
        """检查gcc构建配置是否合法"""

        common.check_home(self.home)
        assert self.build and common.triplet_field.check(self.build), f"Invalid build platform: {self.build}."
        assert self.jobs > 0, f"Invalid jobs: {self.jobs}."
        assert 1 <= self.compress_level <= 19, f"Invalid compress level: {self.compress_level}"


__all__ = ["modifier_list", "support_platform_list", "configure", "environment"]
