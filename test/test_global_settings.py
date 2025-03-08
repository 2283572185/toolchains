import argparse

from toolchains.common import basic_configure, command_dry_run, command_quiet, need_dry_run, status_counter, toolchains_quiet


def test_need_dry_run() -> None:
    """测试need_dry_run是否能正确判断"""

    # 全局不进行的dry run
    command_dry_run.set(False)
    assert need_dry_run(None) == False
    assert need_dry_run(False) == False
    assert need_dry_run(True) == True

    # 全局进行dry run
    command_dry_run.set(True)
    assert need_dry_run(None) == True
    assert need_dry_run(False) == False
    assert need_dry_run(True) == True


def test_need_quiet() -> None:
    """测试安静选项是否正确判断"""

    parser = argparse.ArgumentParser()
    basic_configure.add_argument(parser)

    args = parser.parse_args([])
    basic_configure.parse_args(args)
    assert not command_quiet.get() and not toolchains_quiet.get() and not status_counter.get_quiet()
    assert command_quiet.get_option() == ""

    args = parser.parse_args(["-q"])
    basic_configure.parse_args(args)
    assert command_quiet.get() and not toolchains_quiet.get() and not status_counter.get_quiet()
    assert command_quiet.get_option() == "--quiet"

    args = parser.parse_args(["-qq"])
    basic_configure.parse_args(args)
    assert command_quiet.get() and toolchains_quiet.get() and not status_counter.get_quiet()

    args = parser.parse_args(["-qqq"])
    basic_configure.parse_args(args)
    assert command_quiet.get() and toolchains_quiet.get() and status_counter.get_quiet()


def test_status_counter() -> None:
    """测试状态计数器"""

    status_counter.clear()
    for name in ("error", "warning", "note", "info", "success"):
        getattr(status_counter, f"add_{name}")()
        assert status_counter.get_counter(name) == 1
