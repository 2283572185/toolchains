#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import math
from typing import Callable
from .gcc_environment import cross_environment as cross
from . import common
import argparse
from .modifier import modifier_list

# 列表不包含vendor字段
host_list = ("x86_64-linux-gnu", "x86_64-w64-mingw32")
target_list = (
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
)


class configure(common.basic_configure):
    build: str  # 构建平台
    gdb: bool  # 是否构建gdb
    gdbserver: bool  # 是否构建gdbserver
    newlib: bool  # 是否构建newlib
    jobs: int  # 并发数
    prefix_dir: str  # 工具链安装根目录

    def __init__(
        self,
        build: str = "x86_64-linux-gnu",
        gdb: bool = True,
        gdbserver: bool = True,
        newlib: bool = True,
        home: str = os.environ["HOME"],
        jobs: int = math.floor((os.cpu_count() or 1) * 1.5),
        prefix_dir: str = os.environ["HOME"],
    ) -> None:
        super().__init__(home)
        self.build = build
        self.gdb = gdb
        self.gdbserver = gdbserver
        self.newlib = newlib
        self.jobs = jobs
        self.prefix_dir = prefix_dir

    def check(self) -> None:
        common._check_home(self.home)
        assert self.jobs > 0, f"Invalid jobs: {args.jobs}."


def check_triplet(host: str, target: str) -> None:
    """检查输入triplet是否合法

    Args:
        host (str): 宿主平台
        target (str): 目标平台
    """
    for input_triplet, triplet_list, name in ((host, host_list, "Host"), (target, target_list, "Target")):
        input_triplet_field = common.triplet_field(input_triplet)
        for support_triplet in triplet_list:
            support_triplet_field = common.triplet_field(support_triplet)
            if input_triplet_field.weak_eq(support_triplet_field):
                break
        else:
            assert False, f'{name} "{input_triplet}" is not support.'


def _check_input(args: argparse.Namespace) -> None:
    assert args.jobs > 0, f"Invalid jobs: {args.jobs}."
    check_triplet(args.host, target_list[0] if args.dump else args.target)


def get_modifier(target: str) -> Callable[[cross], None] | None:
    """从修改器列表中查找对应函数

    Args:
        target (str): 目标平台

    Returns:
        Callable | None: 修改器
    """
    return modifier_list.get(target)


def build_specific_gcc(
    config: configure,
    host: str,
    target: str,
    modifier: None | Callable[[cross], None],
) -> None:
    """构建gcc工具链

    Args:
        config (configure): 编译环境
        host (str): 宿主平台
        target (str): 目标平台
        modifier (Callable[[cross], None], optional): 平台相关的修改器. 默认为None.
    """
    env = cross(host=host, target=target, modifier=modifier, **vars(config))
    env.build()


def dump_support_platform() -> None:
    """打印所有受支持的平台"""

    print("Host support:")
    for host in host_list:
        print(f"\t{host}")
    print("Target support:")
    for target in target_list:
        print(f"\t{target}")


if __name__ == "__main__":
    default_config = configure()

    parser = argparse.ArgumentParser(
        description="Build gcc toolchain to specific platform.", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    configure.add_argument(parser)
    parser.add_argument("--build", type=str, help="The build platform of the GCC toolchain.", default=default_config.build)
    parser.add_argument("--host", type=str, help="The host platform of the GCC toolchain.", default="x86_64-linux-gnu")
    parser.add_argument("--target", type=str, help="The target platform of the GCC toolchain.")
    parser.add_argument(
        "--gdb", action=argparse.BooleanOptionalAction, help="Whether to enable gdb support in GCC toolchain.", default=default_config.gdb
    )
    parser.add_argument(
        "--gdbserver",
        action=argparse.BooleanOptionalAction,
        help="Whether to enable gdbserver support in GCC toolchain.",
        default=default_config.gdbserver,
    )
    parser.add_argument(
        "--newlib",
        action=argparse.BooleanOptionalAction,
        help="Whether to enable newlib support in GCC freestanding toolchain.",
        default=default_config.newlib,
    )
    parser.add_argument(
        "--jobs",
        type=int,
        help="Number of concurrent jobs at build time. Use 1.5 times of cpu cores by default.",
        default=default_config.jobs,
    )
    parser.add_argument("--prefix-dir", type=str, help="The dir contains all the prefix dir.", default=default_config.prefix_dir)
    parser.add_argument("--dump", action="store_true", help="Print support platforms and exit.")
    args = parser.parse_args()
    _check_input(args)

    current_config = configure.parse_args(args)
    current_config.load_config(args)
    current_config.check()

    if args.dump:
        dump_support_platform()
    else:
        build_specific_gcc(current_config, args.host, args.target, get_modifier(args.target))

    current_config.save_config(args)
