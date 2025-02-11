# PYTHON_ARGCOMPLETE_OK

import argparse
import enum
import functools
import inspect
import itertools
import json
import os
import shutil
import subprocess
import typing
from collections.abc import Callable
from pathlib import Path
from typing import Self

import colorama
import psutil


class _color(enum.StrEnum):
    """cli使用的颜色

    Attributes:
        warning: 警告用色
        error  : 错误用色
        success: 成功用色
        note   : 提示用色
        reset  : 恢复默认配色
        toolchains: 输出toolchains标志
    """

    warning = colorama.Fore.MAGENTA
    error = colorama.Fore.RED
    success = colorama.Fore.GREEN
    note = colorama.Fore.LIGHTBLUE_EX
    reset = colorama.Fore.RESET
    toolchains = f"{colorama.Fore.CYAN}[toolchains]{reset}"

    def wrapper(self, string: str) -> str:
        """以指定颜色输出string，然后恢复默认配色

        Args:
            string (str): 要输出的字符串

        Returns:
            str: 输出字符串
        """

        return f"{self}{string}{_color.reset}"


def toolchains_warning(string: str) -> str:
    """返回toolchains的警告信息

    Args:
        string (str): 警告字符串

    Returns:
        str: [toolchains] warning
    """

    return f"{_color.toolchains} {_color.warning.wrapper(string)}"


def toolchains_error(string: str) -> str:
    """返回toolchains的错误信息

    Args:
        string (str): 错误字符串

    Returns:
        str: [toolchains] error
    """

    return f"{_color.toolchains} {_color.error.wrapper(string)}"


def toolchains_success(string: str) -> str:
    """返回toolchains的成功信息

    Args:
        string (str): 成功字符串

    Returns:
        str: [toolchains] success
    """

    return f"{_color.toolchains} {_color.success.wrapper(string)}"


def toolchains_note(string: str) -> str:
    """返回toolchains的提示信息

    Args:
        string (str): 提示字符串

    Returns:
        str: [toolchains] note
    """

    return f"{_color.toolchains} {_color.note.wrapper(string)}"


def toolchains_info(string: str) -> str:
    """返回toolchains的普通信息

    Args:
        string (str): 提示字符串

    Returns:
        str: [toolchain] info
    """

    return f"{_color.toolchains} {string}"


class command_dry_run:
    """是否只显示命令而不实际执行"""

    _dry_run: bool = False

    @classmethod
    def get(cls) -> bool:
        return cls._dry_run

    @classmethod
    def set(cls, dry_run: bool) -> None:
        cls._dry_run = dry_run


def support_dry_run[
    **P, R
](echo_fn: Callable[..., str | None] | None = None, end: str | None = None) -> Callable[[Callable[P, R]], Callable[P, R | None]]:
    """根据dry_run参数和command_dry_run中的全局状态确定是否只回显命令而不执行，若fn没有dry_run参数则只会使用全局状态

    Args:
        echo_fn (Callable[..., str | None] | None, optional): 回调函数，返回要显示的命令字符串或None，无回调或返回None时不显示命令
            所有参数需要能在主函数的参数列表中找到，默认为无回调.
        end (str | None, optional): 在输出回显内容后使用的换行符，默认为换行.
    """

    def decorator(fn: Callable[P, R]) -> Callable[P, R | None]:
        signature = inspect.signature(fn)

        @functools.wraps(fn)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R | None:
            bound_args = signature.bind(*args, **kwargs)
            bound_args.apply_defaults()
            if echo_fn:
                param_list: list[typing.Any] = []
                for key in inspect.signature(echo_fn).parameters.keys():
                    assert (
                        key in bound_args.arguments
                    ), f"The param {key} of echo_fn is not in the param list of fn. Every param of echo_fn should be able to find in the param list of fn."
                    param_list.append(bound_args.arguments[key])
                echo = echo_fn(*param_list)
                if echo is not None:
                    print(echo, end=end)
            dry_run: bool | None = bound_args.arguments.get("dry_run")
            assert isinstance(dry_run, bool | None), f"The param dry_run must be a bool or None."
            if dry_run is None and command_dry_run.get() or dry_run:
                return None
            return fn(*bound_args.args, **bound_args.kwargs)

        return wrapper

    return decorator


def _run_command_echo(command: str | list[str], echo: bool) -> str | None:
    """运行命令时回显信息

    Args:
        command (str | list[str]): 要运行的命令
        echo (bool): 是否回显

    Returns:
        str | None: 回显信息
    """

    if isinstance(command, list):
        command = " ".join(command)
    return toolchains_info(f"Run command: {command}") if echo else None


_FILE: typing.TypeAlias = typing.IO[typing.Any] | None


@support_dry_run(_run_command_echo)
def run_command(
    command: str | list[str],
    ignore_error: bool = False,
    capture: bool | tuple[_FILE, _FILE] = False,
    echo: bool = True,
    dry_run: bool | None = None,
) -> subprocess.CompletedProcess[str] | None:
    """运行指定命令, 若不忽略错误, 则在命令执行出错时抛出RuntimeError, 反之打印错误码

    Args:
        command (str | list[str]): 要运行的命令，使用str则在shell内运行，使用list[str]则直接运行
        ignore_error (bool, optional): 是否忽略错误. 默认不忽略错误.
        capture (bool | tuple[_FILE, _FILE], optional): 是否捕获命令输出，默认为不捕获. 若为tuple则capture[0]和capture[1]分别为stdout和stderr.
                                                      tuple中字段为None表示不捕获相应管道的数据，则相应数据会回显
        echo (bool, optional): 是否回显信息，设置为False将不回显任何信息，包括错误提示，默认为回显.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.

    Raises:
        RuntimeError: 命令执行失败且ignore_error为False时抛出异常

    Returns:
        None | subprocess.CompletedProcess[str]: 在命令正常执行结束后返回执行结果，否则返回None
    """

    if capture:
        if capture == True:
            stdout = stderr = subprocess.PIPE  # capture为True，不论是否回显都需要捕获输出
        else:
            stdout, stderr = capture  # 将输出捕获到传入的文件中
    elif echo:
        stdout = stderr = None  # 回显而不捕获输出则正常输出
    else:
        stdout = stderr = subprocess.DEVNULL  # 不回显又不捕获输出则丢弃输出
    try:
        result = subprocess.run(
            command if isinstance(command, str) else " ".join(command),
            stdout=stdout,
            stderr=stderr,
            shell=isinstance(command, str),
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        if not ignore_error:
            raise RuntimeError(toolchains_error(f'Command "{command}" failed.'))
        elif echo:
            print(toolchains_warning(f'Command "{command}" failed with errno={e.returncode}, but it is ignored.'))
        return None
    return result


def _mkdir_echo(path: Path) -> str:
    """创建目录时回显信息

    Args:
        path (Path): 要创建的目录路径

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Create directory {path}.")


@support_dry_run(_mkdir_echo)
def mkdir(path: Path, remove_if_exist: bool = True, dry_run: bool | None = None) -> None:
    """创建目录

    Args:
        path (Path): 要创建的目录
        remove_if_exist (bool, optional): 是否先删除已存在的同名目录. 默认先删除已存在的同名目录.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    if remove_if_exist and path.exists():
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def _copy_echo(src: Path, dst: Path) -> str:
    """在复制文件或目录时回显信息

    Args:
        src (Path): 源路径
        dst (Path): 目标路径

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Copy {src} -> {dst}.")


@support_dry_run(_copy_echo)
def copy(src: Path, dst: Path, overwrite: bool = True, follow_symlinks: bool = False, dry_run: bool | None = None) -> None:
    """复制文件或目录

    Args:-> Callable[[Callable[P, R]], functools._Wrapped[P, R, P, R | None]]
        src (Path): 源路径
        dst (Path): 目标路径
        overwrite (bool, optional): 是否覆盖已存在项. 默认为覆盖.
        follow_symlinks (bool, optional): 是否复制软链接指向的目标，而不是软链接本身. 默认为保留软链接.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    # 创建目标目录
    dir = dst.parent
    mkdir(dir, False)
    if not overwrite and dst.exists():
        return
    if src.is_dir():
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, not follow_symlinks)
    else:
        if dst.exists():
            os.remove(dst)
        shutil.copyfile(src, dst, follow_symlinks=follow_symlinks)


def _copy_if_exist_echo(src: Path, dst: Path) -> str:
    """在复制文件或目录时回显信息

    Args:
        src (Path): 源路径
        dst (Path): 目标路径

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Copy {src} -> {dst} if src exists.")


@support_dry_run(_copy_if_exist_echo)
def copy_if_exist(src: Path, dst: Path, overwrite: bool = True, follow_symlinks: bool = False, dry_run: bool | None = None) -> None:
    """如果文件或目录存在则复制文件或目录

    Args:
        src (Path): 源路径
        dst (Path): 目标路径
        overwrite (bool, optional): 是否覆盖已存在项. 默认为覆盖.
        follow_symlinks (bool, optional): 是否复制软链接指向的目标，而不是软链接本身. 默认为保留软链接.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    if src.exists():
        copy(src, dst, overwrite, follow_symlinks)


def _remove_echo(path: Path) -> str:
    """在删除指定路径时回显信息

    Args:
        path (Path): 要删除的路径

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Remove {path}.")


@support_dry_run(_remove_echo)
def remove(path: Path, dry_run: bool | None = None) -> None:
    """删除指定路径

    Args:
        path (Path): 要删除的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    if path.is_dir():
        shutil.rmtree(path)
    else:
        os.remove(path)


def _remove_if_exists_echo(path: Path) -> str:
    """在删除指定路径时回显信息

    Args:
        path (Path): 要删除的路径

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Remove {path} if path exists.")


@support_dry_run(_remove_if_exists_echo)
def remove_if_exists(path: Path, dry_run: bool | None = None) -> None:
    """如果指定路径存在则删除指定路径

    Args:
        path (Path): 要删除的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    if path.exists():
        remove(path)


def _chdir_echo(path: Path) -> str:
    """在设置工作目录时回显信息

    Args:
        path (Path): 要进入的目录

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Enter directory {path}.")


@support_dry_run(_chdir_echo)
def chdir(path: Path, dry_run: bool | None = None) -> Path:
    """将工作目录设置为指定路径

    Args:
        path (Path): 要进入的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.

    Returns:
        Path: 之前的工作目录
    """

    cwd = Path.cwd()
    os.chdir(path)
    return cwd


def _rename_echo(src: Path, dst: Path) -> str:
    """在重命名指定路径时回显信息

    Args:
        src (Path): 源路径
        dst (Path): 目标路径

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Rename {src} -> {dst}.")


@support_dry_run(_rename_echo)
def rename(src: Path, dst: Path, dry_run: bool | None = None) -> None:
    """重命名指定路径

    Args:
        src (Path): 源路径
        dst (Path): 目标路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    src.rename(dst)


def _symlink_echo(src: Path, dst: Path) -> str:
    """在创建软链接时回显信息

    Args:
        src (Path): 源路径
        dst (Path): 目标路径

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Symlink {dst} -> {src}.")


@support_dry_run(_symlink_echo)
def symlink(src: Path, dst: Path, dry_run: bool | None = None) -> None:
    """创建软链接

    Args:
        src (Path): 源路径
        dst (Path): 目标路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    dst.symlink_to(src, src.is_dir())


def add_environ(key: str, value: str | Path) -> None:
    """添加系统环境变量

    Args:
        key (str): 环境变量名称
        value (str | Path): 环境变量的值
    """

    value = str(value)
    os.environ[key] = value


def insert_environ(key: str, value: str | Path) -> None:
    """在现有环境变量的前端插入新的值

    Args:
        key (str): 环境变量名称
        value (str | Path): 环境变量的值
    """

    value = str(value)
    os.environ[key] = f"{value}{os.pathsep}{os.environ[key]}"


class chdir_guard:
    """在构造时进入指定工作目录并在析构时回到原工作目录"""

    cwd: Path
    dry_run: bool | None

    def __init__(self, path: Path, dry_run: bool | None = None) -> None:
        self.dry_run = dry_run
        self.cwd = chdir(path, dry_run) or Path()

    def __del__(self) -> None:
        chdir(self.cwd, self.dry_run)


def _check_lib_dir_echo(lib: str, lib_dir: Path) -> str:
    """在检查库目录是否存在时回显信息

    Args:
        lib (str): 库名称
        lib_dir (Path): 库目录

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Checking {lib} in {lib_dir} ... ")


@support_dry_run(_check_lib_dir_echo, "")
def check_lib_dir(lib: str, lib_dir: Path, do_assert: bool = True, dry_run: bool | None = None) -> bool:
    """检查库目录是否存在

    Args:
        lib (str): 库名称，用于提供错误报告信息
        lib_dir (Path): 库目录
        do_assert (bool, optional): 是否断言库存在. 默认断言.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.

    Returns:
        bool: 返回库是否存在
    """

    message = toolchains_error(f"Cannot find lib '{lib}' in directory '{lib_dir}'.")
    if not do_assert and not lib_dir.exists():
        print(toolchains_error("no"))
        return False
    else:
        assert lib_dir.exists(), message
    print(toolchains_success("yes"))
    return True


class basic_environment:
    """gcc和llvm共用基本环境"""

    build: str  # build平台
    version: str  # 版本号
    major_version: str  # 主版本号
    home: Path  # 源代码所在的目录
    jobs: int  # 编译所用线程数
    root_dir: Path  # toolchains项目所在目录
    script_dir: Path  # script所在目录
    readme_dir: Path  # readme所在目录
    name_without_version: str  # 不带版本号的工具链名
    name: str  # 工具链名
    prefix_dir: Path  # 安装路径
    bin_dir: Path  # 安装后可执行文件所在目录

    def __init__(self, build: str, version: str, name_without_version: str, home: str, jobs: int, prefix_dir: str) -> None:
        self.build = build
        self.version = version
        self.major_version = self.version.split(".")[0]
        self.name_without_version = name_without_version
        self.name = self.name_without_version + self.major_version
        self.home = Path(home)
        self.jobs = jobs
        self.root_dir = Path(__file__).parent.resolve()
        self.script_dir = self.root_dir.parent / "script"
        self.readme_dir = self.root_dir.parent / "readme"
        self.prefix_dir = Path(prefix_dir)
        self.bin_dir = self.prefix_dir / self.name / "bin"

    def compress(self, name: str | None = None) -> None:
        """压缩构建完成的工具链

        Args:
            name (str, optional): 要压缩的目标名称，是相对于self.home的路径. 默认为self.name.
        """

        _ = chdir_guard(self.home)
        name = name or self.name
        run_command(f"tar -cf {name}.tar {name}")
        memory_MB = psutil.virtual_memory().available // 1048576 + 3072
        run_command(f"xz -fev9 -T 0 --memlimit={memory_MB}MiB {name}.tar")

    def register_in_env(self) -> None:
        """注册安装路径到环境变量"""
        insert_environ("PATH", self.bin_dir)

    def _register_in_bashrc_echo(self) -> str:
        """在.bashrc中注册工具链时回显信息

        Returns:
            str: 回显信息
        """

        return toolchains_info(f"Registering toolchain -> {self.home / '.bashrc'}.")

    @support_dry_run(_register_in_bashrc_echo)
    def register_in_bashrc(self, dry_run: bool | None = None) -> None:
        """注册安装路径到用户配置文件

        Args:
            dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
        """

        with (self.home / ".bashrc").open("a") as file:
            file.write(f"export PATH={self.bin_dir}:$PATH\n")

    def copy_readme(self) -> None:
        """复制工具链说明文件"""

        readme_path = self.readme_dir / f"{self.name_without_version}.md"
        target_path = self.home / self.name / "README.md"
        copy(readme_path, target_path)


class triplet_field:
    """平台名称各个域的内容"""

    arch: str  # 架构
    os: str  # 操作系统
    vendor: str  # 制造商
    abi: str  # abi/libc
    num: int  # 非unknown的字段数

    def __init__(self, triplet: str, normalize: bool = False) -> None:
        """解析平台名称

        Args:
            triplet (str): 输入平台名称
        """

        field = triplet.split("-")
        self.arch = field[0]
        self.num = len(field)
        match (self.num):
            case 2:
                self.os = "unknown"
                self.vendor = "unknown"
                self.abi = field[1]
            case 3:
                self.os = field[1]
                self.vendor = "unknown"
                self.abi = field[2]
            case 4:
                self.vendor = field[1]
                self.os = field[2]
                self.abi = field[3]
            case _:
                raise RuntimeError(f'Illegal triplet "{triplet}"')

        assert self.arch and self.vendor and self.os and self.abi, f'Illegal triplet "{triplet}"'

        # 正则化
        if normalize:
            if self.os == "none":
                self.os = "unknown"

    @staticmethod
    def check(triplet: str) -> bool:
        """检查平台名称是否合法

        Args:
            triplet (str): 平台名称

        Returns:
            bool: 是否合法
        """

        try:
            triplet_field(triplet)
        except Exception:
            return False
        return True

    def weak_eq(self, other: "triplet_field") -> bool:
        """弱相等比较，允许vendor字段不同

        Args:
            other (triplet_field): 待比较对象

        Returns:
            bool: 是否相同
        """

        return self.arch == other.arch and self.os == other.os and self.abi == other.abi

    def drop_vendor(self) -> str:
        """返回去除vendor字段后的triplet

        Returns:
            str: 不含vendor的triplet
        """

        return f"{self.arch}-{self.os}-{self.abi}"


def check_home(home: str | Path) -> None:
    assert Path(home).exists(), f'The home dir "{home}" does not exist.'


def _path_complete(prefix: str, need_file: bool, allowed_suffix: list[str]) -> list[str]:
    """生产路径补全信息

    Args:
        prefix (str): 已输入的部分路径
        need_file (bool): 是否需要列出可选文件
        allowed_suffix (list[str]): 接受的文件后缀列表，为[]表示接受所有后缀，只有当need_file为True时有效

    Returns:
        list[str]: 可选路径列表
    """

    incomplete_path = Path(prefix)
    dot_count = len(prefix) - len(prefix.rstrip("."))
    # 当输入的最后一级以. .. / \结尾时，Path处理的结果就是目录前缀，反之需要获取父目录
    complete_prefix = incomplete_path if prefix.endswith(("/", "/.", "\\", "\\.")) and dot_count <= 2 else incomplete_path.parent
    # 在shell中解析输入
    parser_result = run_command(f"echo {complete_prefix}", ignore_error=True, capture=True, echo=False, dry_run=False)

    result: list[str] = []
    if parser_result:
        absolute_path = Path(parser_result.stdout.strip())
        for path in absolute_path.iterdir():
            # 在用户没有明确输入.时，不显示隐藏项目
            if not prefix.endswith(".") and path.name.startswith("."):
                continue
            path_followed = path.resolve() if path.is_symlink() else path
            if path_followed.is_file():
                if not need_file:
                    continue
                if allowed_suffix and not path_followed.suffix in allowed_suffix:
                    continue

            path = complete_prefix / path.relative_to(absolute_path)
            path_str = str(path)
            if path.is_dir():
                path_str += "/"
            result.append(path_str)
    return sorted(result)


class _files_completer:
    """支持文件补全"""

    def __init__(self, allowed_suffix: str | list[str] = []) -> None:
        if isinstance(allowed_suffix, str):
            allowed_suffix = [allowed_suffix]
        self.allowed_suffix = allowed_suffix

    def __call__(self, prefix: str, **_: dict[str, typing.Any]) -> list[str]:
        return _path_complete(prefix, True, self.allowed_suffix)


def _dir_completer(prefix: str, **_: dict[str, typing.Any]) -> list[str]:
    """支持目录补全"""

    return _path_complete(prefix, False, [])


class basic_configure:
    """配置基类

    Attributes:
        encode_name_map: 编码时使用的构造函数参数名->成员名映射表
    """

    home: Path
    _origin_home_path: str
    _args: argparse.Namespace  # 解析后的命令选项

    encode_name_map: dict[str, str] = {"home": "_origin_home_path"}

    def register_encode_name_map(self, param_name: str, attribute_name: str) -> None:
        """将param_name->attribute_name的映射关系记录到类的encode_name_map表
        注意：需要先给属性赋值，保证属性存在后再进行注册

        Args:
            param_name (str): 构造函数参数名
            attribute_name (str): 成员属性名
        """

        cls = type(self)
        assert (
            param_name in inspect.signature(cls.__init__).parameters.keys()
        ), f"The param {param_name} is not a parma of the __init__ function."
        assert hasattr(self, attribute_name), f"The attribute {attribute_name} is not an attribute of self."
        cls.encode_name_map[param_name] = attribute_name

    def __init__(self, home: str = str(Path.home()), base_path: Path = Path.cwd()) -> None:
        """初始化配置基类

        Args:
            home (Path, optional): 源码树根目录. 默认为当前用户主目录.
            base_path (Path, optional): 当home为相对路径时，转化home为绝对路径使用的基路径. 默认为当前工作目录.
        """

        self._origin_home_path = home
        self.home = (base_path / home).resolve()

    @staticmethod
    def add_argument(parser: argparse.ArgumentParser) -> None:
        """为argparse添加--home、--export和--import选项

        Args:
            parser (argparse.ArgumentParser): 命令行解析器
        """

        action = parser.add_argument(
            "--home",
            type=str,
            help="The home directory to find source trees. "
            "If home is a relative path, it will be converted to an absolute path relative to the cwd.",
            default=str(basic_configure().home),
        )
        setattr(action, "completer", _dir_completer)
        action = parser.add_argument(
            "--export",
            dest="export_file",
            type=str,
            help="Export settings to specific file. The origin home path is saved to the configure file.",
        )
        setattr(action, "completer", _files_completer(".json"))
        action = parser.add_argument(
            "--import",
            dest="import_file",
            type=str,
            help="Import settings from specific file. "
            "If the home in configure file is a a relative path, "
            "it will be converted to an absolute path relative to the directory of the configure file.",
        )
        setattr(action, "completer", _files_completer(".json"))
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action=argparse.BooleanOptionalAction,
            help="Preview the commands without actually executing them.",
            default=False,
        )

    @staticmethod
    def load_config(args: argparse.Namespace) -> dict[str, typing.Any]:
        """从配置文件中加载配置

        Args:
            args (argparse.Namespace): 用户输入参数

        Returns:
            dict[str, typing.Any]: 解码得到的字典

        Raises:
            RuntimeError: 加载失败抛出异常
        """

        if import_file := args.import_file:
            file_path = Path(import_file)
            try:
                with file_path.open() as file:
                    import_config_list = json.load(file)
                assert isinstance(import_config_list, dict), f"Invalid configure file. The configure file must begin with a object."
                import_config_list = typing.cast(dict[str, typing.Any], import_config_list)
            except Exception as e:
                raise RuntimeError(f'Import file "{file_path}" failed: {e}')
            import_config_list["base_path"] = file_path.parent
            return import_config_list
        else:
            return {}

    @classmethod
    def decode(cls, input_list: dict[str, typing.Any]) -> Self:
        """从字典input_list中解码出对象，供反序列化使用
        根据basic_configure的构造函数参数列表得到参数名key，然后从input_list中获取key对应的value（若key不存在则跳过），最后使用关键参数key=value列表调用basic_configure的构造函数
        然后对cls重复上述操作

        Args:
            input_list (dict[str, typing.Any]): 输入字典

        Returns:
            Self: 解码得到的对象
        """

        # 先处理子类，因为子类调用了基类的默认构造，会覆盖基类的成员
        param_list: dict[str, typing.Any] = {}
        for key in itertools.islice(inspect.signature(cls.__init__).parameters.keys(), 1, None):
            if key in input_list:
                param_list[key] = input_list[key]
        result: Self = cls(**param_list)

        # 处理基类
        param_list = {}
        for key in itertools.islice(inspect.signature(basic_configure.__init__).parameters.keys(), 1, None):
            if key in input_list:
                param_list[key] = input_list[key]
        basic_configure.__init__(result, **param_list)
        return result

    @classmethod
    def _get_default_param_list(cls) -> dict[str, typing.Any]:
        """获取类型构造函数的默认参数

        Returns:
            dict[str, typing.Any]: 默认参数列表
        """

        return {param.name: param.default for param in itertools.islice(inspect.signature(cls.__init__).parameters.values(), 1, None)}

    @classmethod
    def parse_args(cls, args: argparse.Namespace) -> Self:
        """解析命令选项并根据选项构造对象，会自动解析配置文件

        Args:
            args (argparse.Namespace): 命令选项

        Returns:
            Self: 构造的对象，如果命令选项中没有对应参数则使用默认值
        """

        check_home(args.home)
        command_dry_run.set(args.dry_run)
        args_list = vars(args)
        input_list: dict[str, typing.Any] = {}
        default_list: dict[str, typing.Any] = {
            **basic_configure._get_default_param_list(),
            **cls._get_default_param_list(),
        }
        for param in itertools.islice(inspect.signature(cls.__init__).parameters.keys(), 1, None):
            assert param != "home", "This function will set home. So home should not in the param list of the __init__ function."
            if param in args_list:
                input_list[param] = args_list[param]
        input_list["home"] = args.home
        input_list["base_path"] = Path.cwd()

        import_list: dict[str, typing.Any] = cls.load_config(args)
        result_list: dict[str, typing.Any] = import_list
        for key, value in input_list.items():
            if value != default_list[key]:
                result_list[key] = value
        result = cls.decode(result_list)
        result._args = args
        return result

    def _map_value(self, cls: type[Self | "basic_configure"]) -> dict[str, typing.Any]:
        """将构造函数参数列表中的参数名key通过encode_name_map映射为对象的属性名

        Args:
            cls (type): 获取构造函数用的类型

        Returns:
            dict[str, typing.Any]: 输出属性列表
        """

        output_list: dict[str, typing.Any] = {}
        for key in itertools.islice(inspect.signature(cls.__init__).parameters.keys(), 1, None):
            mapped_key = self.encode_name_map.get(key, key)  # 进行参数名->属性名映射，映射失败则直接使用参数名
            value = getattr(self, mapped_key, None)
            match (value):
                case None:
                    # 若key不存在且未被映射过则跳过，是不需要序列化的中间参数
                    # 若key不存在且映射过则说明映射表encode_name_map有误
                    assert mapped_key == key, f"The encode_name_map maps the param {key} to a noexist attribute."
                # 将集合转化为列表
                case set():
                    output_list[key] = list(typing.cast(set[object], value))
                # 将Path转化为字符串
                case Path():
                    output_list[key] = str(value)
                # 正常转化
                case _:
                    output_list[key] = value
        return output_list

    def encode(self) -> dict[str, typing.Any]:
        """编码self到字典，可供序列化使用
        根据self的构造函数参数列表得到参数名key，然后通过encode_name_map将key转化为对象的属性名（若不在encode_name_map中则继续使用key），最后将属性序列化

        Returns:
            dict[str, typing.Any]: 编码后的字典
        """

        output_list: dict[str, typing.Any] = {**self._map_value(basic_configure), **self._map_value(type(self))}
        return output_list

    def _save_config_echo(self) -> str | None:
        """保存配置到文件时回显信息

        Returns:
            str | None: 回显信息
        """

        return toolchains_info(f"Save settings -> {file}.") if (file := self._args.export_file) else None

    @support_dry_run(_save_config_echo)
    def save_config(self) -> None:
        """将配置保存到文件，使用json格式

        Args:
            config (object): 要保存的对象
            args (argparse.Namespace): 用户输入参数

        Raises:
            RuntimeError: 保存失败抛出异常
        """

        if export_file := self._args.export_file:
            file_path = Path(export_file)
            try:
                file_path.write_text(json.dumps(self.encode(), indent=4))
            except Exception as e:
                raise RuntimeError(f'Export settings to file "{file_path}" failed: {e}')


assert __name__ != "__main__", "Import this file instead of running it directly."
