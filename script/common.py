from pathlib import Path

from toolchains.common import toolchains_info


def find_libm(lib_dir: Path) -> str | None:
    """查找libm-version.a文件

    Args:
        lib_dir (Path): 库目录

    Returns:
        str | None: libm文件名，未找到则返回None
    """

    for item in lib_dir.iterdir():
        if (name := item.name).startswith("libm-"):
            return name
    return None


def create_ldscript_echo(ldscript_path: Path) -> str:
    """创建链接器脚本时回显的内容

    Args:
        ldscript_path (Path): 链接器脚本路径

    Returns:
        str: 回显内容
    """

    return toolchains_info(f'Create ldscript "{ldscript_path}".')


__all__ = ["find_libm", "create_ldscript_echo"]
