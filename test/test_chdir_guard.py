from pathlib import Path

import py  # type: ignore

from toolchains.common import chdir_guard


def test_chdir_guard(tmpdir: py.path.LocalPath) -> None:
    """测试chdir_guard"""

    cwd = Path.cwd()
    path = Path(tmpdir)
    with chdir_guard(path):
        assert Path.cwd() == path
    assert Path.cwd() == cwd
    with chdir_guard(path, True):
        assert Path.cwd() == cwd
    assert Path.cwd() == cwd
