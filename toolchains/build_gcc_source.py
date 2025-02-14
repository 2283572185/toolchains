import typing

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


class configure(common.basic_build_configure):
    """gcc构建配置"""

    gdb: bool
    gdbserver: bool
    newlib: bool
    nls: bool

    def __init__(
        self,
        gdb: bool = True,
        gdbserver: bool = True,
        newlib: bool = True,
        nls: bool = True,
    ) -> None:
        """设置gcc构建配置

        Args:
            gdb (bool, optional): 是否构建gdb. 默认为构建.
            gdbserver (bool, optional): 是否构建gdbserver. 默认为构建.
            newlib (bool, optional): 是否为独立工具链构建newlib. 默认为构建.
            nls (bool, optional): 是否启用nls. 默认为启用.
        """

        super().__init__()
        self.gdb = gdb
        self.gdbserver = gdbserver
        self.newlib = newlib
        self.nls = nls


__all__ = ["modifier_list", "support_platform_list", "configure", "environment"]
