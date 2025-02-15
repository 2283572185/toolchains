from toolchains.common import command_dry_run, need_dry_run


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
