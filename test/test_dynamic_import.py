from collections.abc import Callable
from pathlib import Path

from toolchains.common import dynamic_import_function


def test_dynamic_import_function() -> None:
    """测试从模块动态导入函数能否正常工作"""

    root_dir = Path(__file__).parent
    module_path = root_dir / "dynamic-import-test.py"
    echo: Callable[[str], str] = dynamic_import_function("echo", module_path)
    string = "Hello World"
    assert echo(string) == string
