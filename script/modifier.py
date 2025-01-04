from typing import Callable
from . import gcc_environment as gcc

# 修改器列表
modifier_list: dict[str, Callable[[gcc.cross_environment], None]] = {}


def register(fn: Callable[[gcc.cross_environment], None]) -> Callable[[gcc.cross_environment], None]:
    """注册修改器到列表

    Args:
        fn (function): 修改器函数
    """
    name: str = fn.__name__
    field_list = name.split("_")[:-1]
    name = "-".join(field_list)
    # 特殊处理x86_64
    name.replace("x86-64", "x86_64")
    modifier_list[name] = fn
    return fn


@register
def arm_linux_gnueabi_modifier(env: gcc.cross_environment) -> None:
    env.adjust_glibc_arch = "arm-sf"


@register
def arm_linux_gnueabihf_modifier(env: gcc.cross_environment) -> None:
    env.adjust_glibc_arch = "arm-hf"


@register
def loongarch64_loongnix_linux_gnu_modifier(env: gcc.cross_environment) -> None:
    env.adjust_glibc_arch = "loongarch64-loongnix"
    env.libc_option.append("--enable-obsolete-rpc")
    env.gcc_option.append("--disable-libsanitizer")


@register
def x86_64_w64_mingw32_modifier(env: gcc.cross_environment) -> None:
    env.libc_option += ["--disable-lib32", "--enable-lib64"]


@register
def i686_w64_mingw32_modifier(env: gcc.cross_environment) -> None:
    env.libc_option += ["--disable-lib64", "--enable-lib32"]
