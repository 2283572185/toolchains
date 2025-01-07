import argparse
from dataclasses import dataclass
import pathlib
import typing

import pytest

from toolchains.common import basic_configure


@dataclass(init=False, repr=False, match_args=False)
class configure(basic_configure):
    jobs: int
    prefix: pathlib.Path
    libs: list[str]

    def __init__(self, jobs: int = 1, prefix: str = str(pathlib.Path.home()), libs: list[str] | None = None) -> None:
        self.jobs = jobs
        self.prefix = pathlib.Path(prefix)
        self.libs = ["basic", *(libs or [])]


def test_default_construct() -> None:
    configure()


class test_basic_configure:
    parser: argparse.ArgumentParser
    default_config: configure

    @classmethod
    def setup_class(cls) -> None:
        cls.default_config = configure()
        cls.parser = argparse.ArgumentParser()
        subparsers = cls.parser.add_subparsers(dest="command")
        jobs_parser = subparsers.add_parser("jobs")
        prefix_parser = subparsers.add_parser("prefix")
        libs_parser = subparsers.add_parser("libs")

        # 添加公共选项
        for subparser in (jobs_parser, prefix_parser, libs_parser):
            configure.add_argument(subparser)

        # 添加各个子命令的选项
        jobs_parser.add_argument("--jobs", type=int, default=cls.default_config.jobs)
        prefix_parser.add_argument("--prefix", type=str, default=cls.default_config.prefix)
        libs_parser.add_argument("--libs", nargs="*", action="extend")

    def test_common_args(self) -> None:
        """测试公共选项是否添加到每个子命令中，针对basic_configure.add_argument"""

        subparsers = self.parser._subparsers
        assert subparsers
        subparser_actions = subparsers._group_actions[0].choices
        assert subparser_actions
        for _, subparser in subparser_actions.items():  # type: ignore
            arg_list: set[str] = set()
            subparser = typing.cast(argparse.ArgumentParser, subparser)
            for action in subparser._actions:
                arg_list.add(action.dest)
            assert {"home", "import_file", "export_file", "dry_run"} < arg_list

    @pytest.mark.parametrize("command", ["jobs", "prefix", "libs"])
    def test_default_config(self, command: str) -> None:
        """测试在不传递参数全部使用默认设置的情况下，各个子命令是否解析参数得到的configure对象是否和默认一致
           针对basic_configure.parse_args
        """
        args = self.parser.parse_args([command])
        current_config = configure.parse_args(args)
        assert self.default_config == current_config
