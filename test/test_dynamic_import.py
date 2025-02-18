from collections.abc import Callable
from pathlib import Path

from toolchains.common import *
import sys


def test_dynamic_import_function() -> None:
    """测试从模块动态导入函数能否正常工作"""

    root_dir = Path(__file__).parent
    module_path = root_dir / "dynamic_import_test" / "dynamic-import-test.py"
    sys_path = sys.path.copy()
    with dynamic_import_module(module_path) as module:
        foo :Callable[[int], int] = dynamic_import_function("foo", module)
        i = 1
        assert foo(i) == i
        bar: Callable[[str], str] = dynamic_import_function("bar", module)
        string = "Hello World"
        assert bar(string) == string
    # 测试sys.path是否复原
    assert sys_path == sys.path
