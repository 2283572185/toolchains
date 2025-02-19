from pathlib import Path

from common import *

from toolchains.common import support_dry_run


@support_dry_run(create_ldscript_echo)
def create_ldscript(ldscript_path: Path, dry_run: bool | None = None) -> None:
    """创建libm.a链接器脚本

    Args:
        ldscript_path (Path): 链接器脚本路径
    """

    ldscript = "OUTPUT_FORMAT(elf64-x86-64)\n" f"GROUP({find_libm(ldscript_path.parent)} libmvec.a)\n"

    ldscript_path.write_text(ldscript)


def main(lib_dir: Path) -> None:
    create_ldscript(lib_dir / "libm.a")
