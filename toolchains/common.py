# PYTHON_ARGCOMPLETE_OK

import argparse
import enum
import functools
import importlib.util
import inspect
import itertools
import json
import os
import shutil
import subprocess
import sys
import types
import typing
from collections.abc import Callable, Generator
from contextlib import contextmanager
from enum import IntEnum, IntFlag, auto
from pathlib import Path
from typing import Self

import colorama

# 受支持的os列表
support_os_list = ("linux", "w64", "none")


class message_type(IntEnum):
    """toolchains项目显示消息的前缀

    Attributes:
        toolchains         : 添加[toolchains]前缀
        toolchains_internal: 添加[toolchains internal]前缀
        none               : 不添加前缀
    """

    toolchains = auto()
    toolchain_internal = auto()
    none = auto()


class color(enum.StrEnum):
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
    toolchains_internal = f"{colorama.Fore.CYAN}[toolchains internal]{reset}"

    def wrapper(self, string: str) -> str:
        """以指定颜色输出string，然后恢复默认配色

        Args:
            string (str): 要输出的字符串

        Returns:
            str: 输出字符串
        """

        return f"{self}{string}{color.reset}"

    @staticmethod
    def get_prefix(message_prefix: message_type) -> str:
        """获取toolchains前缀

        Args:
            message_prefix (message_type): 前缀类型

        Returns:
            str: 前缀字符串
        """

        match (message_prefix):
            case message_type.toolchains:
                return color.toolchains + " "
            case message_type.toolchain_internal:
                return color.toolchains_internal + " "
            case message_type.none:
                return ""


class status_counter:
    """当前程序状态的计数"""

    class __counter:
        error: int = 0
        warning: int = 0
        note: int = 0
        info: int = 0
        success: int = 0

    __quiet: bool = False

    @classmethod
    def clear(cls) -> None:
        """清空计数"""

        for key in filter(lambda key: not key.startswith("_"), [*vars(cls.__counter)]):
            setattr(cls.__counter, key, 0)

    @classmethod
    def add_error(cls) -> None:
        """增加错误计数"""

        cls.__counter.error += 1

    @classmethod
    def add_warning(cls) -> None:
        """增加警告计数"""

        cls.__counter.warning += 1

    @classmethod
    def add_note(cls) -> None:
        """增加注意计数"""

        cls.__counter.note += 1

    @classmethod
    def add_info(cls) -> None:
        """增加信息计数"""

        cls.__counter.info += 1

    @classmethod
    def add_success(cls) -> None:
        """增加成功计数"""

        cls.__counter.success += 1

    @classmethod
    def get_counter(cls, name: str) -> int:
        assert name in ("error", "warning", "note", "info", "success")
        return typing.cast(int, getattr(cls.__counter, name))

    @classmethod
    def get_quiet(cls) -> bool:
        return cls.__quiet

    @classmethod
    def set_quiet(cls, quiet: bool) -> None:
        cls.__quiet = quiet

    @classmethod
    def show_status(cls) -> None:
        """根据全局状态显示当前状态计数"""

        if not cls.__quiet:
            print(
                color.toolchains,
                color.error.wrapper(f"error: {cls.__counter.error}"),
                color.warning.wrapper(f"waring: {cls.__counter.warning}"),
                color.note.wrapper(f"note: {cls.__counter.note}"),
                f"info: {cls.__counter.info}",
                color.success.wrapper(f"success: {cls.__counter.success}"),
            )


def toolchains_warning(string: str, message_prefix: message_type = message_type.toolchains) -> str:
    """返回toolchains的警告信息

    Args:
        string (str): 警告字符串
        message_prefix (message_type, optional): 前缀类型

    Returns:
        str: [toolchains] warning
    """

    status_counter.add_warning()
    return f"{color.get_prefix(message_prefix)}{color.warning.wrapper(string)}"


def toolchains_error(string: str, message_prefix: message_type = message_type.toolchains) -> str:
    """返回toolchains的错误信息

    Args:
        string (str): 错误字符串
        message_prefix (message_type, optional): 前缀类型

    Returns:
        str: [toolchains] error
    """

    status_counter.add_error()
    return f"{color.get_prefix(message_prefix)}{color.error.wrapper(string)}"


def toolchains_success(string: str, message_prefix: message_type = message_type.toolchains) -> str:
    """返回toolchains的成功信息

    Args:
        string (str): 成功字符串
        message_prefix (message_type, optional): 前缀类型

    Returns:
        str: [toolchains] success
    """

    status_counter.add_success()
    return f"{color.get_prefix(message_prefix)}{color.success.wrapper(string)}"


def toolchains_note(string: str, message_prefix: message_type = message_type.toolchains) -> str:
    """返回toolchains的提示信息

    Args:
        string (str): 提示字符串
        message_prefix (message_type, optional): 前缀类型

    Returns:
        str: [toolchains] note
    """

    status_counter.add_note()
    return f"{color.get_prefix(message_prefix)}{color.note.wrapper(string)}"


def toolchains_info(string: str, message_prefix: message_type = message_type.toolchains) -> str:
    """返回toolchains的普通信息

    Args:
        string (str): 提示字符串
        message_prefix (message_type, optional): 前缀类型

    Returns:
        str: [toolchain] info
    """

    status_counter.add_info()
    return f"{color.get_prefix(message_prefix)}{string}"


class command_dry_run:
    """是否只显示命令而不实际执行"""

    __dry_run: bool = False

    @classmethod
    def get(cls) -> bool:
        return cls.__dry_run

    @classmethod
    def set(cls, dry_run: bool) -> None:
        cls.__dry_run = dry_run


class command_quiet:
    """运行命令时是否添加--quiet --silent等参数"""

    __quiet: bool = False

    @classmethod
    def get(cls) -> bool:
        return cls.__quiet

    @classmethod
    def get_option(cls) -> str:
        return "--quiet" if cls.__quiet else ""

    @classmethod
    def set(cls, quiet: bool) -> None:
        cls.__quiet = quiet


class toolchains_quiet:
    """是否显示toolchains的提示信息"""

    __quiet: bool = False

    @classmethod
    def get(cls) -> bool:
        return cls.__quiet

    @classmethod
    def set(cls, quiet: bool) -> None:
        cls.__quiet = quiet


def toolchains_print(
    *values: object,
    sep: str | None = " ",
    end: str | None = "\n",
) -> None:
    """根据全局设置决定是否需要打印信息

    Args:
        sep (str | None, optional): 分隔符. 默认为空格.
        end (str | None, optional): 行尾序列. 默认为换行.
    """

    if not toolchains_quiet.get():
        print(*values, sep=sep, end=end)


def need_dry_run(dry_run: bool | None) -> bool:
    """根据输入和全局状态共同判断是否只回显而不运行命令

    Args:
        dry_run (bool | None): 当前是否只回显而不运行命令

    Returns:
        bool: 是否只回显而不运行命令
    """

    return bool(dry_run is None and command_dry_run.get() or dry_run)


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
                    assert key in bound_args.arguments, toolchains_error(
                        f"The param {key} of echo_fn is not in the param list of fn. Every param of echo_fn should be able to find in the param list of fn.",
                        message_type.toolchain_internal,
                    )
                    param_list.append(bound_args.arguments[key])
                echo = echo_fn(*param_list)
                if echo is not None:
                    toolchains_print(echo, end=end)
            dry_run: bool | None = bound_args.arguments.get("dry_run")
            assert isinstance(dry_run, bool | None), toolchains_error(
                f"The param dry_run must be a bool or None.", message_type.toolchain_internal
            )
            if need_dry_run(dry_run):
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

    stdout: int | _FILE
    stderr: int | _FILE
    if capture:
        if isinstance(capture, bool):
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
            toolchains_print(toolchains_warning(f'Command "{command}" failed with errno={e.returncode}, but it is ignored.'))
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


@support_dry_run()
def copy_if_exist(src: Path, dst: Path, overwrite: bool = True, follow_symlinks: bool = False, dry_run: bool | None = None) -> bool:
    """如果文件或目录存在则复制文件或目录

    Args:
        src (Path): 源路径
        dst (Path): 目标路径
        overwrite (bool, optional): 是否覆盖已存在项. 默认为覆盖.
        follow_symlinks (bool, optional): 是否复制软链接指向的目标，而不是软链接本身. 默认为保留软链接.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.

    Returns:
        bool: 是否发生了复制
    """

    if src.exists():
        copy(src, dst, overwrite, follow_symlinks)
        return True
    else:
        return False


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


@support_dry_run()
def remove_if_exists(path: Path, dry_run: bool | None = None) -> bool:
    """如果指定路径存在则删除指定路径

    Args:
        path (Path): 要删除的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.

    Returns:
        bool: 是否发生了移动
    """

    if path.exists():
        remove(path)
        return True
    else:
        return False


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


def _symlink_echo(target: Path, symlink_path: Path) -> str:
    """在创建软链接时回显信息

    Args:
        target (Path): 软链接的目标路径
        symlink_path (Path): 软链接所在路径

    Returns:
        str: 回显信息
    """

    return toolchains_info(f"Symlink {symlink_path} -> {target}.")


@support_dry_run(_symlink_echo)
def symlink(target: Path, symlink_path: Path, overwrite: bool = True, dry_run: bool | None = None) -> None:
    """创建软链接

    Args:
        target (Path): 软链接的目标路径
        symlink_path (Path): 软链接所在路径
        overwrite (bool, optional): 是否覆盖现有文件
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    if not overwrite and symlink_path.exists():
        return
    remove_if_exists(symlink_path)
    symlink_path.symlink_to(target, target.is_dir())


def symlink_if_exist(target: Path, symlink_path: Path, overwrite: bool = True, dry_run: bool | None = None) -> None:
    """如果目标存在则创建软链接

    Args:
        target (Path): 软链接的目标路径
        symlink_path (Path): 软链接所在路径
        overwrite (bool, optional): 是否覆盖现有文件
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """

    if target.exists():
        symlink(target, symlink_path, overwrite, dry_run)


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


@contextmanager
def chdir_guard(path: Path, dry_run: bool | None = None) -> Generator[None, None, None]:
    """临时进入指定的工作目录

    Args:
        path (Path): 要进入的工作目录
        dry_run (bool | None, optional): 是否只回显而不运行命令. 默认为None.
    """
    cwd = chdir(path, dry_run) or Path()
    yield
    chdir(cwd, dry_run)


def _check_lib_dir_echo(lib: str, lib_dir: Path, dry_run: bool | None) -> str:
    """在检查库目录是否存在时回显信息

    Args:
        lib (str): 库名称
        lib_dir (Path): 库目录

    Returns:
        str: 回显信息
    """

    basic_info = toolchains_info(f"Checking {lib} in {lib_dir} ... ")
    if need_dry_run(dry_run):
        return basic_info + toolchains_note("skip for dry run\n", message_type.none)
    else:
        return basic_info


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

    if not do_assert and not lib_dir.exists():
        toolchains_print(color.error.wrapper("no"))
        return False
    else:
        assert lib_dir.exists(), toolchains_error(f"Cannot find lib '{lib}' in directory '{lib_dir}'.")
    toolchains_print(toolchains_success("yes", message_type.none))
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
    compress_level: int  # zstd压缩等级

    def __init__(
        self, build: str, version: str, name_without_version: str, home: Path, jobs: int, prefix_dir: Path, compress_level: int
    ) -> None:
        self.build = build
        self.version = version
        self.major_version = self.version.split(".")[0]
        self.name_without_version = name_without_version
        self.name = self.name_without_version + self.major_version
        self.home = home
        self.jobs = jobs
        self.root_dir = Path(__file__).parent.resolve()
        self.script_dir = self.root_dir.parent / "script"
        self.prefix_dir = prefix_dir
        self.bin_dir = self.prefix_dir / self.name / "bin"
        self.compress_level = compress_level

    def compress(self, name: str | None = None) -> None:
        """压缩构建完成的工具链

        Args:
            name (str, optional): 要压缩的目标名称，是相对于self.prefix_dir的路径. 默认为self.name.
        """

        chdir(self.prefix_dir)
        name = name or self.name
        run_command(f"tar -cf {name}.tar {name}")
        run_command(f"zstd --ultra --rm -{self.compress_level} -T{self.jobs} -f {name}.tar")

    def register_in_env(self) -> None:
        """注册安装路径到环境变量"""
        insert_environ("PATH", self.bin_dir)

    def installed(self) -> bool:
        """判断工具链是否已经安装

        Returns:
            bool: 工具链是否已经安装
        """

        return self.bin_dir.exists()


class triplet_field:
    """平台名称各个域的内容"""

    arch: str  # 架构
    os: str  # 操作系统
    vendor: str  # 制造商
    abi: str  # abi/libc
    num: int  # 非unknown的字段数
    triplet: str  # 原平台名称

    def __init__(self, triplet: str, normalize: bool = False) -> None:
        """解析平台名称

        Args:
            triplet (str): 输入平台名称
            normalize (bool, optional): 是否将none替换为unknown. 默认不替换.

        Raises:
            RuntimeError: 输入平台名称无法解析
        """

        self.triplet = triplet
        fields = triplet.split("-")
        self.arch = fields[0]
        self.num = len(fields)
        message = toolchains_error(f'Illegal triplet "{triplet}"')
        match (self.num):
            case 2:
                self.os = "unknown"
                self.vendor = "unknown"
                self.abi = fields[1]
            case 3:
                if fields[1] in support_os_list:
                    self.os = fields[1]
                    self.vendor = "unknown"
                else:
                    self.os = "unknown"
                    self.vendor = fields[1]
                self.abi = fields[2]
            case 4:
                self.vendor = fields[1]
                self.os = fields[2]
                self.abi = fields[3]
            case _:
                raise RuntimeError(message)

        assert self.arch and self.vendor and self.os and self.abi, message

        # 正则化
        if normalize:
            if self.os == "none":
                self.os = "unknown"

    @classmethod
    def try_parse(cls, triplet: str) -> Self:
        """尝试解析平台名称，无法解析部分以""代替，不会产生异常，num为总字段数

        Args:
            triplet (str): 输入平台名称

        Returns:
            Self: 平台字段对象
        """

        result = cls.__new__(cls)
        result.triplet = triplet
        fields = triplet.split("-")

        # 根据第1个字段探测arch
        result.arch = fields[0] if fields else ""
        result.vendor = ""
        result.os = ""
        result.abi = ""

        def detect_vendor_os() -> None:
            """根据第2个字段探测vendor或os"""

            for os in support_os_list:
                if os.startswith(fields[1]):
                    result.os = fields[1]
                    result.vendor = ""
                    break
            else:
                result.vendor = fields[1]
                result.os = ""

        result.num = len(fields)
        match (result.num):
            case 0 | 1:
                pass
            case 2:
                detect_vendor_os()
            case 3:
                detect_vendor_os()
                # 探测到os，下一个只能是abi
                if result.os:
                    result.abi = fields[2]
                # 探测到vendor，下一个是os
                else:
                    result.os = fields[2]
            case _:
                result.arch = fields[0]
                result.vendor = fields[1]
                result.os = fields[2]
                result.abi = fields[3]

        return result

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


class files_completer:
    """支持文件补全"""

    def __init__(self, allowed_suffix: str | list[str] = []) -> None:
        if isinstance(allowed_suffix, str):
            allowed_suffix = [allowed_suffix]
        self.allowed_suffix = allowed_suffix

    def __call__(self, prefix: str, **_: typing.Any) -> list[str]:
        return _path_complete(prefix, True, self.allowed_suffix)


def dir_completer(prefix: str, **_: typing.Any) -> list[str]:
    """支持目录补全"""

    return _path_complete(prefix, False, [])


class triplet_completer:
    """支持平台名称补全"""

    origin_triplet_list: list[str]
    triplet_list: list[triplet_field]
    option_list: list[str]
    arch_list: list[str]

    def __init__(self, triplet_list: list[str], option_list: list[str] = []) -> None:
        """创建平台名称补全对象

        Args:
            triplet_list (list[str]): 平台列表
            option_list (list[str]): 其他选项列表，如"all"选项
        """

        self.origin_triplet_list = triplet_list
        self.triplet_list = [triplet_field(triplet) for triplet in triplet_list]
        self.option_list = option_list
        self.arch_list = list({triplet.arch for triplet in self.triplet_list})

    class _filter:
        arch: str
        os: str
        abi: str

        def __init__(self, arch: str, os: str, abi: str) -> None:
            self.arch = arch
            self.os = os
            self.abi = abi

        def __call__(self, triplet: triplet_field) -> bool:
            def arch_filter() -> bool:
                if self.os:
                    return triplet.arch == self.arch
                else:
                    return triplet.arch.startswith(self.arch)

            def os_filter() -> bool:
                if self.os and not self.abi:
                    return triplet.os.startswith(self.os)
                elif self.os and self.abi:
                    return triplet.os == self.os
                else:
                    return True

            def abi_filter() -> bool:
                return not self.abi or triplet.abi.startswith(self.abi)

            return arch_filter() and os_filter() and abi_filter()

    def _get_filter(self, arch: str, os: str = "", abi: str = "") -> "filter[triplet_field]":
        return filter(self._filter(arch, os, abi), self.triplet_list)

    def _get_triplet_list(self, arch: str, os: str = "", abi: str = "") -> list[str]:
        return [triplet.triplet for triplet in self._get_filter(arch, os, abi)]

    def __call__(self, prefix: str, **_: typing.Any) -> list[str]:
        # 解析已输入内容
        parse_result = triplet_field.try_parse(prefix)
        result: list[str] = []
        match (prefix.count("-")):
            case 0:
                result = self._get_triplet_list(parse_result.arch) if prefix else self.origin_triplet_list
            case 1:
                result = self._get_triplet_list(parse_result.arch, parse_result.os)
            case 2:
                arch = parse_result.arch
                os = parse_result.os
                if abi := parse_result.abi:
                    result = self._get_triplet_list(arch, os, abi)
                else:
                    triplet_list = self._get_filter(arch, os)
                    result = ["-".join((arch, parse_result.vendor, triplet.os, triplet.abi)) for triplet in triplet_list]
            case 3:
                arch = parse_result.arch
                os = parse_result.os
                abi = parse_result.abi
                abi_list = [triplet.abi for triplet in self._get_filter(arch, os, abi)]
                result = ["-".join((arch, parse_result.vendor, os, abi)) for abi in abi_list]
            case _:
                result = []

        for option in self.option_list:
            if option.startswith(prefix):
                result.append(option)

        return result


def resolve_path(path: str | Path, base_path: Path) -> Path:
    """将相对路径转化为基于base_path的绝对路径，已经是绝对路径则不变

    Args:
        path (str | Path): 输入路径
        base_path (Path): 基路径

    Returns:
        Path: 转化后的绝对路径
    """

    path = Path(path)
    if not path.is_absolute():
        return (base_path / path).resolve()
    else:
        return path.resolve()


class basic_configure:
    """配置基类

    Attributes:
        encode_name_map: 编码时使用的构造函数参数名->成员名映射表
    """

    home: Path
    _origin_home_path: str
    _args: argparse.Namespace  # 解析后的命令选项

    encode_name_map: dict[str, str] = {}

    def get_public_fields(self) -> dict[str, typing.Any]:
        """以字典形式获取所有公开字段

        Returns:
            dict[str, typing.Any]: 打包成字典的公开字段
        """

        return {key: value for key, value in filter(lambda x: not x[0].startswith("_"), vars(self).items())}

    def register_encode_name_map(self, param_name: str, attribute_name: str) -> None:
        """将param_name->attribute_name的映射关系记录到类的encode_name_map表
        注意：需要先给属性赋值，保证属性存在后再进行注册

        Args:
            param_name (str): 构造函数参数名
            attribute_name (str): 成员属性名
        """

        cls = type(self)
        parma_list = self._get_default_param_list().keys()
        assert param_name in parma_list, toolchains_error(
            f"The param {param_name} is not a parma of the __init__ function.", message_type.toolchain_internal
        )
        assert hasattr(self, attribute_name), toolchains_error(
            f"The attribute {attribute_name} is not an attribute of self.", message_type.toolchain_internal
        )
        cls.encode_name_map[param_name] = attribute_name

    def __init__(self, home: str = str(Path.home()), base_path: Path = Path.cwd()) -> None:
        """初始化配置基类

        Args:
            home (Path, optional): 源码树根目录. 默认为当前用户主目录.
            base_path (Path, optional): 当home为相对路径时，转化home为绝对路径使用的基路径. 默认为当前工作目录.
        """

        self._origin_home_path = home
        self.register_encode_name_map("home", "_origin_home_path")
        self.home = resolve_path(home, base_path)

    @classmethod
    def add_argument(cls, parser: argparse.ArgumentParser) -> None:
        """为argparse添加--home、--export和--import选项

        Args:
            parser (argparse.ArgumentParser): 命令行解析器
        """

        action = parser.add_argument(
            "--home",
            type=str,
            help="The home directory to find source trees. "
            "If home is inputted as a relative path, it will be converted to an absolute path relative to the cwd."
            "If home is imported as a relative path from configure file, it will be converted to an absolute path relative to the directory of the configure file",
            default=str(basic_configure().home),
        )
        setattr(action, "completer", dir_completer)
        action = parser.add_argument(
            "--export",
            dest="export_file",
            type=str,
            help="Export settings to specific file. The origin home path is saved to the configure file.",
        )
        setattr(action, "completer", files_completer(".json"))
        action = parser.add_argument(
            "--import",
            dest="import_file",
            type=str,
            help="Import settings from specific file. "
            "If the home in configure file is a a relative path, "
            "it will be converted to an absolute path relative to the directory of the configure file.",
        )
        setattr(action, "completer", files_completer(".json"))
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action=argparse.BooleanOptionalAction,
            help="Preview the commands without actually executing them.",
            default=False,
        )
        parser.add_argument(
            "-q",
            "--quiet",
            action="count",
            help="Increase quiet level (use -q, -qq, etc.). "
            'Level 1 will add options like "--quiet" to commands we run if possible. '
            "Level 2 will disable command echos of this program. "
            "Level 3 and above will disable the echo of status counter in this program.",
            default=0,
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
                assert isinstance(import_config_list, dict), toolchains_error(
                    f"Invalid configure file. The configure file must begin with a object."
                )
                import_config_list = typing.cast(dict[str, typing.Any], import_config_list)
            except Exception as e:
                raise RuntimeError(toolchains_error(f'Import file "{file_path}" failed: {e}'))
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
        result: Self = cls.__new__(cls)
        current_cls = cls
        while current_cls != object:
            param_list: dict[str, typing.Any] = {}
            for key in itertools.islice(inspect.signature(current_cls.__init__).parameters.keys(), 1, None):
                if key in input_list:
                    param_list[key] = input_list[key]
            current_cls.__init__(result, **param_list)
            current_cls = current_cls.__bases__[0]
        return result

    @classmethod
    def _get_default_param_list(cls) -> dict[str, typing.Any]:
        """获取类型构造函数的默认参数

        Returns:
            dict[str, typing.Any]: 默认参数列表
        """

        result: dict[str, typing.Any] = {}
        current_cls = cls
        while current_cls != object:
            current_result: dict[str, typing.Any] = {
                param.name: param.default
                for param in itertools.islice(inspect.signature(current_cls.__init__).parameters.values(), 1, None)
            }
            result.update(current_result)
            current_cls = current_cls.__bases__[0]

        return result

    @classmethod
    def parse_args(cls, args: argparse.Namespace) -> Self:
        """解析命令选项并根据选项构造对象，会自动解析配置文件

        Args:
            args (argparse.Namespace): 命令选项

        Returns:
            Self: 构造的对象，如果命令选项中没有对应参数则使用默认值
        """

        default_list: dict[str, typing.Any] = cls._get_default_param_list()

        def set_default(**parma_list: typing.Any) -> None:
            """设置参数的默认值"""

            for parma, value in parma_list.items():
                setattr(args, parma, getattr(args, parma, value))

        # 针对未添加通用选项的情况
        set_default(home=default_list["home"], dry_run=False, quiet=0, import_file=None, export_file=None)
        check_home(args.home)
        command_dry_run.set(args.dry_run)
        if args.quiet >= 1:
            command_quiet.set(True)
        if args.quiet >= 2:
            toolchains_quiet.set(True)
        if args.quiet >= 3:
            status_counter.set_quiet(True)
        args_list = vars(args)
        input_list: dict[str, typing.Any] = {}
        current_cls = cls
        while current_cls != basic_configure:
            for param in itertools.islice(inspect.signature(current_cls.__init__).parameters.keys(), 1, None):
                if param in args_list:
                    input_list[param] = args_list[param]
            current_cls = current_cls.__bases__[0]
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

    def _map_value(self) -> dict[str, typing.Any]:
        """将构造函数参数列表中的参数名key通过encode_name_map映射为对象的属性名

        Returns:
            dict[str, typing.Any]: 输出属性列表
        """

        output_list: dict[str, typing.Any] = {}
        current_cls = type(self)
        while current_cls != object:
            for key in itertools.islice(inspect.signature(current_cls.__init__).parameters.keys(), 1, None):
                mapped_key = self.encode_name_map.get(key, key)  # 进行参数名->属性名映射，映射失败则直接使用参数名
                value = getattr(self, mapped_key, None)
                match (value):
                    case None:
                        # 若key不存在且未被映射过则跳过，是不需要序列化的中间参数
                        # 若key不存在且映射过则说明映射表encode_name_map有误
                        assert mapped_key == key, toolchains_error(
                            f"The encode_name_map maps the param {key} to a noexist attribute.", message_type.toolchain_internal
                        )
                    # 将集合转化为列表
                    case set():
                        output_list[key] = list(typing.cast(set[object], value))
                    # 将Path转化为字符串
                    case Path():
                        output_list[key] = str(value)
                    # 正常转化
                    case _:
                        output_list[key] = value
            current_cls = current_cls.__bases__[0]
        return output_list

    def encode(self) -> dict[str, typing.Any]:
        """编码self到字典，可供序列化使用
        根据self的构造函数参数列表得到参数名key，然后通过encode_name_map将key转化为对象的属性名（若不在encode_name_map中则继续使用key），最后将属性序列化

        Returns:
            dict[str, typing.Any]: 编码后的字典
        """

        output_list: dict[str, typing.Any] = self._map_value()
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
                raise RuntimeError(toolchains_error(f'Export settings to file "{file_path}" failed: {e}'))


def get_default_build_platform() -> str | None:
    """获取默认的build平台，即当前平台

    Returns:
        str | None: 默认build平台. 获取失败返回None
    """

    result: subprocess.CompletedProcess[str] | None = run_command("gcc -dumpmachine", True, True, False, False)
    return result.stdout.strip() if result else None


class basic_build_configure(basic_configure):
    """工具链构建配配置"""

    build: str | None
    jobs: int
    _origin_prefix_dir: str
    prefix_dir: Path
    compress_level: int

    def __init__(
        self,
        build: str | None = None,
        jobs: int | None = None,
        prefix_dir: str = str(Path.home()),
        compress_level: int = 17,
        base_path: Path = Path.cwd(),
    ) -> None:
        """初始化工具链构建配置

        Args:
            build (str | None, optional): 构建平台. 默认为gcc -dumpmachine输出的结果，即当前平台.
            jobs (int | None, optional): 构建时的并发数. 默认为当前平台cpu核心数的1.5倍.
            prefix_dir (str, optional): 工具链安装根目录. 默认为用户主目录.
            compress_level (int, optional): zstd压缩等级(1~22). 默认为17级
            base_path (Path, optional): 将prefix转化为绝对路径时使用的基路径
        """

        super().__init__()
        self.build = build or get_default_build_platform()
        self.jobs = jobs or (os.cpu_count() or 1) + 2
        self._origin_prefix_dir = prefix_dir
        self.register_encode_name_map("prefix_dir", "_origin_prefix_dir")
        self.prefix_dir = resolve_path(prefix_dir, base_path)
        self.compress_level = compress_level

    @classmethod
    def add_argument(cls, parser: argparse.ArgumentParser) -> None:
        """为argparse添加--build、--jobs、--prefix和--compress选项

        Args:
            parser (argparse.ArgumentParser): 命令行解析器
        """

        super().add_argument(parser)
        toolchain_type = typing.cast(str, getattr(cls, "toolchain_type"))
        default_config = basic_build_configure()
        parser.add_argument(
            "--build", type=str, help=f"The build platform of the {toolchain_type} toolchain.", default=default_config.build
        )
        parser.add_argument(
            "-j",
            "--jobs",
            type=int,
            help="Number of concurrent jobs at build time.",
            default=default_config.jobs,
        )
        action = parser.add_argument(
            "--prefix",
            dest="prefix_dir",
            type=str,
            help="The dir to install the toolchain."
            "If prefix is inputted as a relative path, it will be converted to an absolute path relative to the cwd."
            "If prefix is imported as a relative path from configure file, it will be converted to an absolute path relative to the directory of the configure file",
            default=default_config.prefix_dir,
        )
        setattr(action, "completer", dir_completer)
        parser.add_argument(
            "--compress",
            dest="compress_level",
            type=int,
            help="The compress level of zstd when packing. Support 1~22.",
            default=default_config.compress_level,
        )

    def check(self) -> None:
        """检查工具链构建配置是否合法"""

        check_home(self.home)
        assert self.build and triplet_field.check(self.build), toolchains_error(f"Invalid build platform: {self.build}.")
        assert self.jobs > 0, toolchains_error(f"Invalid jobs: {self.jobs}.")
        assert 1 <= self.compress_level <= 22, toolchains_error(f"Invalid compress level: {self.compress_level}")


@contextmanager
def dynamic_import_module(module_path: Path) -> Generator[types.ModuleType, None, None]:
    """动态导入模块

    Args:
        module_path (Path): 模块路径
    """

    module_name = module_path.stem.replace("-", "_")
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    message = toolchains_error(f'Cannot load module "{module_path}".', message_type.toolchain_internal)
    assert spec, message
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader, message
    module_dir = str(module_path.parent)
    sys.path.insert(0, module_dir)
    loader.exec_module(module)
    yield module
    for i, dir in enumerate(sys.path):
        if dir == module_dir:
            del sys.path[i]


def dynamic_import_function(function_name: str, module: types.ModuleType) -> Callable[..., typing.Any]:
    """从模块中动态导入函数

    Args:
        function_name (str): 函数名称
        module (types.ModuleType): 加载的模块

    Raises:
        RuntimeError: 导入失败抛出异常

    Returns:
        Callable[..., typing.Any]: 导入的函数
    """

    try:
        return typing.cast(Callable[..., typing.Any], getattr(module, function_name))
    except:
        raise RuntimeError(
            toolchains_error(f'Cannot import function "{function_name}" from "{module.__name__}".', message_type.toolchain_internal)
        )


class toolchain_type(IntFlag):
    """工具链类型枚举

    Attributes:
        native        : 本地工具链，build == host == target
        cross         : 交叉工具链，build == host != target
        canadian      : 加拿大工具链，build != host == target
        canadian_cross: 加拿大交叉工具链，build != host != target
        hosted        : 宿主工具链，target为宿主平台
        freestanding  : 独立工具链，target为独立平台
    """

    native = auto()
    cross = auto()
    canadian = auto()
    canadian_cross = auto()
    hosted = auto()
    freestanding = auto()

    def __str__(self) -> str:
        freestanding_hosted_type = "unknown"
        target_type = "unknown"
        for flag in toolchain_type:
            if self & flag:
                if flag in (toolchain_type.hosted, toolchain_type.freestanding):
                    freestanding_hosted_type = flag.name or "unknown"
                else:
                    target_type = (flag.name or "unknown").replace("_", " ")
        return f"{freestanding_hosted_type} {target_type} toolchain"

    def contain(self, mask: "toolchain_type") -> bool:
        """判断是否包含掩码中指定的标记

        Args:
            mask (toolchain_type): 掩码

        Returns:
            bool: 是否包含相应标记
        """

        return bool(self & mask)

    @staticmethod
    def classify_toolchain(build: str, host: str, target: str) -> "toolchain_type":
        """鉴别工具链种类

        Args:
            build (str): build平台
            host (str): host平台
            target (str): target平台

        Returns:
            toolchain_type: 工具链类型
        """

        if build == host == target:
            result = toolchain_type.native
        elif build == host != target:
            result = toolchain_type.cross
        elif build != host == target:
            result = toolchain_type.canadian
        else:
            result = toolchain_type.canadian_cross

        target_field = triplet_field(target)
        result |= toolchain_type.freestanding if target_field.abi in ("elf", "eabi") else toolchain_type.hosted
        return result


assert __name__ != "__main__", "Import this file instead of running it directly."
