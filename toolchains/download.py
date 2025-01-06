#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import os

from . import common
from .download_source import *


def _exist_echo(lib: str) -> None:
    """包已存在时显示提示"""
    print(f"[toolchains] Lib {lib} exists, skip download.")


def _up_to_date_echo(lib: str) -> None:
    """包已是最新时显示提示"""
    print(f"[toolchains] Lib {lib} is up to date, skip update.")


def _check_version_echo(lib: str, result: int) -> bool:
    """根据包版本检查结果显示提示，并返回是否需要更新

    Args:
        lib (str): 包名称
        result (int): 版本检查结果

    Returns:
        bool: 是否需要更新
    """
    if result == 1:
        print(f"[toolchains] Lib {lib} is newer than default version, skip update.")
        return False
    elif result == 0:
        _up_to_date_echo(lib)
        return False
    else:
        return True


def download_gcc_contrib(config: configure) -> None:
    """下载gcc的依赖包

    Args:
        config (environment): 源代码下载环境
    """
    _ = common.chdir_guard(os.path.join(config.home, "gcc"))
    common.run_command("contrib/download_prerequisites")


def download_specific_extra_lib(config: configure, lib: str) -> None:
    """下载指定的非git托管包

    Args:
        config (environment): 源代码下载环境
        lib (str): 要下载的包
    """
    assert lib in all_lib_list.extra_lib_list, f"Unknown extra lib: {lib}"
    extra_lib_v = all_lib_list.extra_lib_list[lib]
    for lib, url in extra_lib_v.url_list.items():
        common.run_command(f"wget {url} -c -t {config.network_try_times} -O {os.path.join(config.home, lib)}")


def download(config: configure) -> None:
    """下载不存在的源代码，不会更新已有源代码

    Args:
        config (environment): 源代码下载环境
    """
    # 下载git托管的源代码
    for lib, url_fields in all_lib_list.get_prefer_git_lib_list(config).items():
        lib_dir = os.path.join(config.home, lib)
        if not os.path.exists(lib_dir):
            url = url_fields.get_url(config.git_use_ssh)
            extra_options: list[str] = [*extra_git_options_list.get_option(config, lib), git_clone_type.get_clone_option(config)]
            extra_option = " ".join(extra_options)
            for _ in range(config.network_try_times):
                try:
                    common.run_command(f"git clone {url} {extra_option} {lib_dir}")
                    break
                except Exception:
                    common.remove_if_exists(lib_dir)
                    print(f"[toolchains] Clone {lib} failed, retrying.")
            else:
                raise RuntimeError(f"[toolchains] Clone {lib} failed.")
            after_download_list.after_download_specific_lib(config, lib)
        else:
            _exist_echo(lib)

    # 下载非git托管代码
    for lib in config.extra_lib_list:
        assert lib in all_lib_list.extra_lib_list, f"Unknown extra lib: {lib}"
        if not all_lib_list.extra_lib_list[lib].check_exist(config):
            download_specific_extra_lib(config, lib)
            after_download_list.after_download_specific_lib(config, lib)
        else:
            _exist_echo(lib)
    for lib in ("gmp", "mpfr", "isl", "mpc"):
        if not os.path.exists(os.path.join(config.home, "gcc", lib)):
            download_gcc_contrib(config)
            break
    else:
        _exist_echo("gcc_contrib")


def update(config: configure) -> None:
    """更新所有源代码，要求所有包均已下载

    Args:
        config (environment): 源代码下载环境
    """
    # 更新git托管的源代码
    for lib in all_lib_list.get_prefer_git_lib_list(config):
        lib_dir = os.path.join(config.home, lib)
        assert os.path.exists(lib_dir), f"Cannot find lib: {lib}"
        for _ in range(config.network_try_times):
            try:
                result = common.run_command(f"git -C {lib_dir} fetch --dry-run", capture=True)
                break
            except Exception:
                print(f"[toolchains] Fetch {lib} failed, retrying.")
        else:
            raise RuntimeError(f"Fetch {lib} failed.")

        if not common.command_dry_run.get():
            assert result
            if result.stderr.strip():
                for _ in range(config.network_try_times):
                    try:
                        common.run_command(f"git -C {lib_dir} pull")
                        break
                    except Exception:
                        print(f"[toolchains] Pull {lib} failed, retrying.")
                else:
                    raise RuntimeError(f"Pull {lib} failed.")
                after_download_list.after_download_specific_lib(config, lib)
            else:
                _up_to_date_echo(lib)

    # 更新非git包
    for lib in config.extra_lib_list:
        lib_version = extra_lib_version[lib if lib != "python-embed" else "python"]
        need_download = _check_version_echo(
            lib, lib_version.check_version(os.path.join(config.home, all_lib_list.extra_lib_list[lib].version_dir))
        )
        if need_download:
            download_specific_extra_lib(config, lib)
            after_download_list.after_download_specific_lib(config, lib)


def auto_download(config: configure) -> None:
    """首先下载缺失的包，然后更新已有的包

    Args:
        config (environment): 源代码下载环境
    """
    download(config)
    update(config)


def get_system_lib_list() -> list[str]:
    """获取系统包列表

    Returns:
        list[str]: 系统包列表
    """
    return all_lib_list.system_lib_list


def remove_specific_lib(config: configure, lib: str) -> None:
    """删除指定包

    Args:
        config (configure): 源代码下载环境
        lib (str): 要删除的包

    Raises:
        RuntimeError: 删除未知包时抛出异常
    """

    assert lib in all_lib_list.all_lib_list, f"Unknown lib {lib}."
    if lib in all_lib_list.extra_lib_list:
        install_item: list[str] = all_lib_list.extra_lib_list[lib].install_dir
    elif lib in all_lib_list.git_lib_list_github:
        install_item = [os.path.join(config.home, lib)]
    elif lib == "gcc_contrib":
        gcc_dir = os.path.join(config.home, "gcc")
        if not os.path.exists(gcc_dir):
            print(f"[toolchains] Lib {lib} does not exist, skip remove.")
            return
        install_item = [
            os.path.join(gcc_dir, item)
            for item in filter(lambda x: x.startswith(("gettext", "gmp", "mpc", "mpfr", "isl")), os.listdir(gcc_dir))
        ]

    removed = False
    for dir in install_item:
        try:
            if os.path.exists(dir):
                common.remove(dir)
                removed = True
        except Exception as e:
            raise RuntimeError(f"Remove lib {lib} failed: {e}")
    if not removed:
        print(f"[toolchains] Lib {lib} does not exist, skip remove.")


def remove(config: configure, libs: list[str]) -> None:
    """删除指定包

    Args:
        config (configure): 源代码下载环境
        libs (list[str]): 要删除的包列表

    Raises:
        RuntimeError: 删除未知包时抛出异常
    """
    for lib in libs:
        remove_specific_lib(config, lib)


def _check_input(args: argparse.Namespace) -> None:
    """检查输入是否正确"""
    assert args.glibc_version, f"Invalid glibc version: {args.glibc_version}"
    assert args.depth > 0, f"Invalid shallow clone depth: {args.depth}."
    assert args.retry >= 0, f"Invalid network try times: {args.retry}."


__all__ = [
    "download_gcc_contrib",
    "download_specific_extra_lib",
    "download",
    "update",
    "auto_download",
    "get_system_lib_list",
    "configure",
    "remove_specific_lib",
    "remove",
]


def main() -> None:
    default_config = configure()

    parser = argparse.ArgumentParser(
        description="Download or update needy libs for building gcc and llvm.", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    configure.add_argument(parser)
    parser.add_argument(
        "--glibc", dest="glibc_version", type=str, help="The version of glibc of target platform.", default=default_config.glibc_version
    )
    parser.add_argument(
        "--clone-type",
        type=str,
        help="How to clone the git repository.",
        default=default_config.clone_type,
        choices=git_clone_type,
    )
    parser.add_argument("--depth", type=int, help="The depth of shallow clone.", default=default_config.shallow_clone_depth)
    parser.add_argument(
        "--ssh", type=bool, help="Whether to use ssh when cloning git repositories from github.", default=default_config.git_use_ssh
    )
    parser.add_argument(
        "--extra-libs",
        action="extend",
        nargs="*",
        help="Extra non-git libs to install.",
        choices=all_lib_list.optional_extra_lib_list,
    )
    parser.add_argument(
        "--retry", type=int, help="The number of retries when a network operation failed.", default=default_config.network_try_times - 1
    )
    parser.add_argument(
        "--remote",
        type=str,
        help="The git remote preferred to use. The preferred remote will be used to accelerate git operation when possible.",
        default=default_config.git_remote,
        choices=git_prefer_remote,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--update",
        action="store_true",
        help="Update installed libs. All libs should be installed before update.",
    )
    group.add_argument("--download", action="store_true", help="Download missing libs. This would not update existing libs.")
    group.add_argument(
        "--auto",
        action="store_true",
        help="Download missing libs, then update installed libs. This may take more time because of twice check.",
    )
    group.add_argument("--system", action="store_true", help="Print needy system libs and exit.")
    group.add_argument(
        "--remove",
        action="extend",
        nargs="*",
        help="Remove installed libs. Use without specific lib name to remove all installed libs.",
        choices=all_lib_list.all_lib_list,
    )
    args = parser.parse_args()
    # 检查输入是否合法
    _check_input(args)

    current_config = configure.parse_args(args)
    current_config.load_config(args)
    current_config.reset_list_if_empty("extra_lib_list", "extra_libs", args)

    # 检查合并配置后环境是否正确
    current_config.check()
    current_config.save_config(args)

    if args.system:
        print(f"Please install following system libs: {' '.join(get_system_lib_list())}")
    elif args.auto:
        auto_download(current_config)
    elif args.update:
        update(current_config)
    elif args.download:
        download(current_config)
    elif args.remove is not None:
        remove(current_config, args.remove or all_lib_list.all_lib_list)


if __name__ == "__main__":
    main()
