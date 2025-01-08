import math
import os
import pathlib
import typing
from collections.abc import Callable
from subprocess import CompletedProcess

from . import common
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


def get_default_build_platform() -> str | None:
    result: CompletedProcess[str] | None = common.run_command("gcc -dumpmachine", True, True, False, False)
    if result:
        value: str = result.stdout.strip()
        if (fields := common.triplet_field(value)).vendor == "pc":
            value = fields.drop_vendor()
        return value
    else:
        return None


class configure(common.basic_configure):
    build: str | None  # 构建平台
    gdb: bool  # 是否构建gdb
    gdbserver: bool  # 是否构建gdbserver
    newlib: bool  # 是否构建newlib
    jobs: int  # 并发数
    prefix_dir: pathlib.Path  # 工具链安装根目录

    def __init__(
        self,
        build: str | None = get_default_build_platform(),
        gdb: bool = True,
        gdbserver: bool = True,
        newlib: bool = True,
        jobs: int = math.floor((os.cpu_count() or 1) * 1.5),
        prefix_dir: str = str(pathlib.Path.home()),
    ) -> None:
        self.build = build
        self.gdb = gdb
        self.gdbserver = gdbserver
        self.newlib = newlib
        self.jobs = jobs
        self.prefix_dir = pathlib.Path(prefix_dir)

    def check(self) -> None:
        common._check_home(self.home)
        assert self.build and common.triplet_field.check(self.build), f"Invalid build platform: {self.build}."
        assert self.jobs > 0, f"Invalid jobs: {self.jobs}."


__all__ = ["modifier_list", "support_platform_list", "configure"]
