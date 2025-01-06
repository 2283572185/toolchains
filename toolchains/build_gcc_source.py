import typing
from typing import Callable

from .gcc_environment import cross_environment as environment


class modifier_list:
    @staticmethod
    def arm_linux_gnueabi(env: environment) -> None:
        env.adjust_glibc_arch = "arm-sf"

    @staticmethod
    def arm_linux_gnueabihf(env: environment) -> None:
        env.adjust_glibc_arch = "arm-hf"

    @staticmethod
    def loongarch64_loongnix_linux_gnu(env: environment) -> None:
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
    def get_modifier(target: str) -> Callable[[environment], None] | None:
        # 特殊处理x86_64
        target.replace("x86-64", "x86_64")
        return typing.cast(Callable[[environment], None] | None, getattr(modifier_list, target, None))


# 列表不包含vendor字段


class support_platform_list:
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


__all__ = ["modifier_list", "support_platform_list"]
