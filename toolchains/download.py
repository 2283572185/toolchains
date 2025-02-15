#!/usr/bin/env python
# PYTHON_ARGCOMPLETE_OK

import argparse
import os
import pathlib
import tempfile

import argcomplete

from . import common
from .download_source import *


def _exist_echo(lib: str) -> None:
    """包已存在时显示提示"""
    common.toolchains_print(common.toolchains_note(f"Lib {lib} exists, skip download."))


def _up_to_date_echo(lib: str) -> None:
    """包已是最新时显示提示"""
    common.toolchains_print(common.toolchains_note(f"Lib {lib} is up to date, skip update."))


def _check_version_echo(lib: str, result: int) -> bool:
    """根据包版本检查结果显示提示，并返回是否需要更新

    Args:
        lib (str): 包名称
        result (int): 版本检查结果

    Returns:
        bool: 是否需要更新
    """
    if result == 1:
        common.toolchains_print(common.toolchains_note(f"Lib {lib} is newer than default version, skip update."))
        return False
    elif result == 0:
        _up_to_date_echo(lib)
        return False
    else:
        return True


def download_gcc_contrib(config: configure) -> None:
    """下载gcc的依赖包

    Args:
        config (configure): 源代码下载环境
    """
    with common.chdir_guard(config.home / "gcc"):
        common.run_command("contrib/download_prerequisites", echo=not common.command_quiet.get())
    common.status_counter.add_success()


def download_specific_extra_lib(config: configure, lib: str) -> None:
    """下载指定的非git托管包

    Args:
        config (configure): 源代码下载环境
        lib (str): 要下载的包名
    """
    assert lib in all_lib_list.extra_lib_list, common.toolchains_error(f"Unknown extra lib: {lib}")
    extra_lib_v = all_lib_list.extra_lib_list[lib]
    for file, url in extra_lib_v.url_list.items():
        common.run_command(f"wget {url} {common.command_quiet.get_option()} -c -t {config.network_try_times} -O {config.home / file}")
    common.status_counter.add_success()


def download(config: configure) -> None:
    """下载不存在的源代码，不会更新已有源代码

    Args:
        config (configure): 源代码下载环境
    """
    # 下载git托管的源代码
    for lib, url_fields in all_lib_list.get_prefer_git_lib_list(config).items():
        lib_dir = config.home / lib
        if not lib_dir.exists():
            url = url_fields.get_url(config.git_use_ssh)
            extra_options: list[str] = [*extra_git_options_list.get_option(config, lib), git_clone_type.get_clone_option(config)]
            extra_option = " ".join(extra_options)
            for _ in range(config.network_try_times):
                try:
                    common.run_command(f"git clone {url} {common.command_quiet.get_option()} {extra_option} {lib_dir}")
                    break
                except Exception:
                    common.remove_if_exists(lib_dir)
                    common.toolchains_print(common.toolchains_warning(f"Clone {lib} failed, retrying."))
            else:
                raise RuntimeError(common.toolchains_error(f"Clone {lib} failed."))
            after_download_list.after_download_specific_lib(config, lib)
            common.status_counter.add_success()
        else:
            _exist_echo(lib)

    # 下载非git托管代码
    for lib in config.extra_lib_list:
        assert lib in all_lib_list.extra_lib_list, common.toolchains_error(f"Unknown extra lib: {lib}")
        if not all_lib_list.extra_lib_list[lib].check_exist(config):
            download_specific_extra_lib(config, lib)
            after_download_list.after_download_specific_lib(config, lib)
        else:
            _exist_echo(lib)
    for lib in ("gmp", "mpfr", "isl", "mpc"):
        if not (config.home / "gcc" / lib).exists():
            download_gcc_contrib(config)
            break
    else:
        _exist_echo("gcc_contrib")
    common.toolchains_print(common.toolchains_success("Download libs successfully."))


def update(config: configure) -> None:
    """更新所有源代码，要求所有包均已下载

    Args:
        config (configure): 源代码下载环境
    """

    # 更新git托管的源代码
    for lib in all_lib_list.get_prefer_git_lib_list(config):
        lib_dir = config.home / lib
        assert lib_dir.exists(), common.toolchains_error(f"Cannot find lib: {lib}")
        with tempfile.TemporaryFile("r+") as file:
            for _ in range(config.network_try_times):
                try:
                    common.run_command(f"git -C {lib_dir} fetch --dry-run", capture=(file, file))
                    break
                except Exception:
                    common.toolchains_print(common.toolchains_warning(f"Fetch {lib} failed, retrying."))
                    file.truncate(0)
                    file.seek(0, os.SEEK_SET)
            else:
                raise RuntimeError(common.toolchains_error(f"Fetch {lib} failed."))

            if not common.command_dry_run.get():
                if file.tell():
                    for _ in range(config.network_try_times):
                        try:
                            common.run_command(f"git -C {lib_dir} pull {common.command_quiet.get_option()}")
                            break
                        except Exception:
                            common.toolchains_print(common.toolchains_warning(f"Pull {lib} failed, retrying."))
                    else:
                        raise RuntimeError(common.toolchains_error(f"Pull {lib} failed."))
                    after_download_list.after_download_specific_lib(config, lib)
                    common.status_counter.add_success()
                else:
                    _up_to_date_echo(lib)

    # 更新非git包
    for lib in config.extra_lib_list:
        lib_version = extra_lib_version[lib if lib != "python-embed" else "python"]
        need_download = _check_version_echo(
            lib, lib_version.check_version(config.home / all_lib_list.get_prefer_extra_lib_list(config, lib).version_dir)
        )
        if need_download:
            download_specific_extra_lib(config, lib)
            after_download_list.after_download_specific_lib(config, lib)

    common.toolchains_print(common.toolchains_success("Update libs successfully."))


def auto_download(config: configure) -> None:
    """首先下载缺失的包，然后更新已有的包

    Args:
        config (configure): 源代码下载环境
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

    if lib in all_lib_list.extra_lib_list:
        install_item: list[pathlib.Path] = all_lib_list.get_prefer_extra_lib_list(config, lib).install_dir
    elif lib in all_lib_list.git_lib_list_github:
        install_item = [config.home / lib]
    elif lib == "gcc_contrib":
        gcc_dir = config.home / "gcc"
        if not gcc_dir.exists():
            common.toolchains_print(common.toolchains_note(f"Lib {lib} does not exist, skip remove."))
            return
        install_item = [
            gcc_dir / item for item in filter(lambda x: x.name.startswith(("gettext", "gmp", "mpc", "mpfr", "isl")), gcc_dir.iterdir())
        ]
    else:
        raise RuntimeError(common.toolchains_error(f"Unknown lib {lib}."))

    removed = False
    for dir in install_item:
        try:
            if dir.exists():
                common.remove(dir)
                removed = True
        except Exception as e:
            raise RuntimeError(common.toolchains_error(f"Remove lib {lib} failed: {e}"))
    if not removed:
        common.toolchains_print(common.toolchains_warning(f"Lib {lib} does not exist, skip remove."))


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
    common.toolchains_print(common.toolchains_success("Remove libs successfully."))


def _check_input(args: argparse.Namespace) -> None:
    """检查输入是否正确"""
    if args.command in ("download", "auto"):
        assert args.glibc_version, common.toolchains_error(f"Invalid glibc version: {args.glibc_version}")
        assert args.depth > 0, common.toolchains_error(f"Invalid shallow clone depth: {args.depth}.")
    if args.command in ("update", "download", "auto"):
        assert args.retry >= 0, common.toolchains_error(f"Invalid network try times: {args.retry}.")


__all__ = [
    "extra_lib_version",
    "git_clone_type",
    "git_prefer_remote",
    "all_lib_list",
    "configure",
    "after_download_list",
    "extra_git_options_list",
    "download_gcc_contrib",
    "download_specific_extra_lib",
    "download",
    "update",
    "auto_download",
    "get_system_lib_list",
    "remove_specific_lib",
    "remove",
]


def main() -> None:
    """cli主函数"""

    default_config = configure()

    parser = argparse.ArgumentParser(
        description="Download or update needy libs for building gcc and llvm.", formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands.")
    update_parser = subparsers.add_parser("update", help="Update installed libs. All libs should be installed before update.")
    download_parser = subparsers.add_parser("download", help="Download missing libs. This would not update existing libs.")
    auto_parser = subparsers.add_parser(
        "auto", help="Download missing libs, then update installed libs. This may take more time because of twice check."
    )
    system_parser = subparsers.add_parser("system", help="Print needy system libs and exit.")
    remove_parser = subparsers.add_parser(
        "remove", help="Remove installed libs. Use without specific lib name to remove all installed libs."
    )

    # 添加公共选项
    for subparser in (update_parser, download_parser, auto_parser, system_parser, remove_parser):
        configure.add_argument(subparser)
    for subparser in (update_parser, download_parser, auto_parser):
        subparser.add_argument(
            "--retry", type=int, help="The number of retries when a network operation failed.", default=default_config.network_try_times - 1
        )
        subparser.add_argument(
            "--extra-libs",
            action="extend",
            nargs="*",
            help="Extra non-git libs to install.",
            choices=all_lib_list.optional_extra_lib_list,
        )
        subparser.add_argument(
            "--remote",
            type=str,
            help="The remote repository preferred to use. The preferred remote will be used to accelerate download when possible.",
            default=default_config.git_remote,
            choices=git_prefer_remote,
        )
    for subparser in (download_parser, auto_parser):
        subparser.add_argument(
            "--glibc", dest="glibc_version", type=str, help="The version of glibc of target platform.", default=default_config.glibc_version
        )
        subparser.add_argument(
            "--clone-type",
            type=str,
            help="How to clone the git repository.",
            default=default_config.clone_type,
            choices=git_clone_type,
        )
        subparser.add_argument("--depth", type=int, help="The depth of shallow clone.", default=default_config.shallow_clone_depth)
        subparser.add_argument(
            "--ssh", type=bool, help="Whether to use ssh when cloning git repositories from github.", default=default_config.git_use_ssh
        )

    # 添加各个子命令专属选项
    remove_parser.add_argument(
        "remove",
        action="extend",
        nargs="*",
        help="Remove installed libs. Use without specific lib name to remove all installed libs.",
        choices=all_lib_list.all_lib_list,
    )

    argcomplete.autocomplete(parser)
    args = parser.parse_args()
    # 检查输入是否合法
    _check_input(args)

    current_config = configure.parse_args(args)

    # 检查合并配置后环境是否正确
    current_config.check()
    current_config.save_config()

    match (args.command):
        case "update":
            update(current_config)
        case "download":
            download(current_config)
        case "auto":
            auto_download(current_config)
        case "system":
            print(common.toolchains_info(f"Please install following system libs: \n{' '.join(get_system_lib_list())}"))
        case "remove":
            remove(current_config, args.remove or all_lib_list.all_lib_list)
        case _:
            pass

    common.status_counter.show_status()
