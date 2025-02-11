#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argparse

import argcomplete

from . import common
from .build_gcc_source import *


def check_triplet(host: str, target: str) -> None:
    """检查输入triplet是否合法

    Args:
        host (str): 宿主平台
        target (str): 目标平台
    """

    for input_triplet, triplet_list, name in (
        (host, support_platform_list.host_list, "Host"),
        (target, support_platform_list.target_list, "Target"),
    ):
        input_triplet_field = common.triplet_field(input_triplet)
        for support_triplet in triplet_list:
            support_triplet_field = common.triplet_field(support_triplet)
            if input_triplet_field.weak_eq(support_triplet_field):
                break
        else:
            assert False, f'{name} "{input_triplet}" is not support.'


def _check_input(args: argparse.Namespace) -> None:
    assert args.jobs > 0, f"Invalid jobs: {args.jobs}."
    check_triplet(args.host, support_platform_list.target_list[0] if args.dump else args.target)


def build_specific_gcc(
    config: configure,
    host: str,
    target: str,
) -> None:
    """构建gcc工具链

    Args:
        config (configure): 编译环境
        host (str): 宿主平台
        target (str): 目标平台
    """

    config_list = vars(config)
    del config_list["_origin_home_path"]
    env = environment(host=host, target=target, **config_list)
    modifier_list.modify(env, target)
    env.build()


def dump_support_platform() -> None:
    """打印所有受支持的平台"""

    print("Host support:")
    for host in support_platform_list.host_list:
        print(f"\t{host}")
    print("Target support:")
    for target in support_platform_list.target_list:
        print(f"\t{target}")


__all__ = [
    "modifier_list",
    "support_platform_list",
    "configure",
    "environment",
    "check_triplet",
    "build_specific_gcc",
    "dump_support_platform",
]


def main() -> None:
    default_config = configure()

    parser = argparse.ArgumentParser(
        description="Build gcc toolchain to specific platform.", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    configure.add_argument(parser)
    parser.add_argument("--build", type=str, help="The build platform of the GCC toolchain.", default=default_config.build)
    parser.add_argument("--host", type=str, help="The host platform of the GCC toolchain.", default=default_config.build)
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
        "-j",
        "--jobs",
        type=int,
        help="Number of concurrent jobs at build time. Use cpu cores + 2 by default.",
        default=default_config.jobs,
    )
    parser.add_argument(
        "--prefix", dest="prefix_dir", type=str, help="The dir contains all the prefix dir.", default=default_config.prefix_dir
    )
    parser.add_argument("--dump", action="store_true", help="Print support platforms and exit.")

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    _check_input(args)

    current_config = configure.parse_args(args)
    current_config.check()

    if args.dump:
        dump_support_platform()
    else:
        build_specific_gcc(current_config, args.host, args.target)

    current_config.save_config()
