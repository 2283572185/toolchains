import argparse
import json
import pathlib
import typing

import py
import pytest

from toolchains.common import basic_configure, command_dry_run

type Path = py.path.LocalPath


class configure(basic_configure):
    jobs: int
    prefix: pathlib.Path
    libs: set[str]
    _origin_libs: set[str]
    _private: int  # 私有对象，在序列化/反序列化时不应该被访问

    def __init__(self, jobs: int = 1, prefix: str = str(pathlib.Path.home()), libs: list[str] | None = None) -> None:
        super().__init__()
        self.jobs = jobs
        self.prefix = pathlib.Path(prefix)
        self._origin_libs = {*(libs or [])}
        self.register_encode_name_map("libs", "_origin_libs")
        self.libs = {"basic", *self._origin_libs}
        self._private = 0

    def __eq__(self, other: object) -> bool:
        assert isinstance(other, configure)
        return self.home == other.home and self.jobs == other.jobs and self.prefix == other.prefix and self.libs == other.libs


def test_default_construct() -> None:
    """测试configure是否可以正常默认构造"""
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

    def test_subcommand_jobs(self) -> None:
        """测试jobs选项能否正常解析
        针对整数解析
        """
        custom_jobs = 2
        args = self.parser.parse_args(["jobs", f"--jobs={custom_jobs}"])
        current_config = configure.parse_args(args)
        assert current_config == configure(jobs=custom_jobs)

    def test_subcommand_prefix(self, tmpdir: Path) -> None:
        """测试prefix选项能否正常解析
        针对需要从字符串构造的对象
        """
        custom_prefix = str(tmpdir)
        args = self.parser.parse_args(["prefix", f"--prefix={custom_prefix}"])
        current_config = configure.parse_args(args)
        assert current_config == configure(prefix=custom_prefix)

    def test_subcommand_libs(self) -> None:
        """测试libs选项能否正常解析
        针对可空列表解析
        """
        custom_libs = ["extra1", "extra2"]
        args = self.parser.parse_args(["libs", "--libs", *custom_libs])
        current_config = configure.parse_args(args)
        assert current_config == configure(libs=custom_libs)

        # 用户尝试清空列表，变回默认设置
        args = self.parser.parse_args(["libs", "--libs"])
        current_config = configure.parse_args(args)
        assert current_config == self.default_config

    def test_import(self, tmpdir: Path) -> None:
        """测试从文件导入配置信息

        Args:
            tmpdir (Path): 临时文件路径
        """
        tmpfile = pathlib.Path(tmpdir) / "test.json"
        custom_prefix = str(tmpdir)  # 用户输入prefix
        import_libs = ["basic", "extra1", "extra2"]  # 保存在json中的libs

        test_json: dict[str, typing.Any] = {
            "home": str(tmpdir),
            "jobs": self.default_config.jobs,
            "prefix": str(self.default_config.prefix),
            "libs": import_libs,
        }
        with open(tmpfile, "w") as file:
            json.dump(test_json, file)

        args = self.parser.parse_args(["prefix", "--import", str(tmpfile), "--prefix", custom_prefix])
        current_config = configure.parse_args(args)
        gt = configure(jobs=self.default_config.jobs, prefix=custom_prefix, libs=["extra1", "extra2"])
        gt.home = str(tmpdir)
        assert current_config == gt

        # 尝试恢复默认配置
        args = self.parser.parse_args(["libs", "--import", str(tmpfile), "--libs"])
        current_config = configure.parse_args(args)
        gt = configure(jobs=self.default_config.jobs)
        gt.home = str(tmpdir)
        assert current_config == gt

    def test_export(self, tmpdir: Path) -> None:
        """测试导出配置信息到文件

        Args:
            tmpdir (Path): 临时文件路径
        """
        tmpfile = pathlib.Path(tmpdir) / "test.json"
        custom_prefix = str(tmpdir)  # 用户输入prefix
        args = self.parser.parse_args(["prefix", "--prefix", custom_prefix, "--home", ".", "--export", str(tmpfile)])
        current_config = configure.parse_args(args)
        current_config.save_config()

        gt = {"home": ".", "jobs": self.default_config.jobs, "prefix": custom_prefix, "libs": []}
        with tmpfile.open() as file:
            export_config = json.load(file)
        assert export_config == gt

    def test_dry_run(self) -> None:
        """测试全局的dry_run状态是否正常设置"""
        args = self.parser.parse_args(["prefix", "--dry-run"])
        _ = configure.parse_args(args)
        assert command_dry_run.get() == True
        args = self.parser.parse_args(["prefix", "--no-dry-run"])
        _ = configure.parse_args(args)
        assert command_dry_run.get() == False

    def test_import_noexist_file(self, tmpdir: Path) -> None:
        """测试打开一个不存在的配置文件

        Args:
            tmpdir (Path): 临时文件目录
        """
        with pytest.raises(Exception):
            args = self.parser.parse_args(["prefix", "--import", str(tmpdir / "test.json")])
            _ = configure.parse_args(args)

    def test_export_unwritable_file(self) -> None:
        """测试写入一个不可写的配置文件

        Args:
            tmpdir (Path): 临时文件目录
        """
        with pytest.raises(Exception):
            args = self.parser.parse_args(["prefix", "--export", "/dev/full"])
            _ = configure.parse_args(args)
            _.save_config()
