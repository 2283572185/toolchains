import argparse
import functools
import inspect
import itertools
import json
import os
import pathlib
import shutil
import subprocess
import typing
from collections.abc import Callable
from typing import Self

import psutil


class command_dry_run:
    """是否只显示命令而不实际执行"""

    _dry_run: bool = False

    @classmethod
    def get(cls) -> bool:
        return cls._dry_run

    @classmethod
    def set(cls, dry_run: bool) -> None:
        cls._dry_run = dry_run


def _support_dry_run[**P, R](echo_fn: Callable[..., str | None] | None = None) -> Callable[[Callable[P, R]], Callable[P, R | None]]:
    """根据dry_run参数和command_dry_run中的全局状态确定是否只回显命令而不执行，若fn没有dry_run参数则只会使用全局状态

    Args:
        echo_fn (Callable[..., str | None] | None, optional): 回调函数，返回要显示的命令字符串或None，无回调或返回None时不显示命令，所有参数需要能在主函数的参数列表中找到，默认为无回调.
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
                    print(echo)
            dry_run: bool | None = bound_args.arguments.get("dry_run")
            assert isinstance(dry_run, bool | None), f"The param dry_run must be a bool or None."
            if dry_run is None and command_dry_run.get() or dry_run:
                return None
            return fn(*bound_args.args, **bound_args.kwargs)

        return wrapper

    return decorator


@_support_dry_run(lambda command, echo: f"[toolchains] Run command: {command}" if echo else None)
def run_command(
    command: str, ignore_error: bool = False, capture: bool = False, echo: bool = True, dry_run: bool | None = None
) -> subprocess.CompletedProcess[str] | None:
    """运行指定命令, 若不忽略错误, 则在命令执行出错时抛出RuntimeError, 反之打印错误码

    Args:
        command (str): 要运行的命令
        ignore_error (bool, optional): 是否忽略错误. 默认不忽略错误.
        capture (bool, optional): 是否捕获命令输出，默认为不捕获.
        echo (bool, optional): 是否回显信息，设置为False将不回显任何信息，包括错误提示，默认为回显.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.

    Raises:
        RuntimeError: 命令执行失败且ignore_error为False时抛出异常

    Returns:
        None | subprocess.CompletedProcess[str]: 在命令正常执行结束后返回执行结果，否则返回None
    """

    if capture:
        pipe = subprocess.PIPE  # capture为True，不论是否回显都需要捕获输出
    elif echo:
        pipe = None  # 回显而不捕获输出则正常输出
    else:
        pipe = subprocess.DEVNULL  # 不回显又不捕获输出则丢弃输出
    try:
        result = subprocess.run(command, stdout=pipe, stderr=pipe, shell=True, check=True, text=True)
    except subprocess.CalledProcessError as e:
        if not ignore_error:
            raise RuntimeError(f'Command "{command}" failed.')
        elif echo:
            print(f'Command "{command}" failed with errno={e.returncode}, but it is ignored.')
        return None
    return result


@_support_dry_run(lambda path: f"[toolchains] Create directory {path}.")
def mkdir(path: str, remove_if_exist: bool = True, dry_run: bool | None = None) -> None:
    """创建目录

    Args:
        path (str): 要创建的目录
        remove_if_exist (bool, optional): 是否先删除已存在的同名目录. 默认先删除已存在的同名目录.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    if remove_if_exist and os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


@_support_dry_run(lambda src, dst: f"[toolchains] Copy {src} -> {dst}.")
def copy(src: str, dst: str, overwrite: bool = True, follow_symlinks: bool = False, dry_run: bool | None = None) -> None:
    """复制文件或目录

    Args:-> Callable[[Callable[P, R]], functools._Wrapped[P, R, P, R | None]]
        src (str): 源路径
        dst (str): 目标路径
        overwrite (bool, optional): 是否覆盖已存在项. 默认为覆盖.
        follow_symlinks (bool, optional): 是否复制软链接指向的目标，而不是软链接本身. 默认为保留软链接.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    # 创建目标目录
    dir = os.path.dirname(dst)
    if dir != "":
        mkdir(dir, False)
    if not overwrite and os.path.exists(dst):
        return
    if os.path.isdir(src):
        if os.path.exists(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, not follow_symlinks)
    else:
        if os.path.exists(dst):
            os.remove(dst)
        shutil.copyfile(src, dst, follow_symlinks=follow_symlinks)


@_support_dry_run(lambda src, dst: f"[toolchains] Copy {src} -> {dst} if src exists.")
def copy_if_exist(src: str, dst: str, overwrite: bool = True, follow_symlinks: bool = False, dry_run: bool | None = None) -> None:
    """如果文件或目录存在则复制文件或目录

    Args:
        src (str): 源路径
        dst (str): 目标路径
        overwrite (bool, optional): 是否覆盖已存在项. 默认为覆盖.
        follow_symlinks (bool, optional): 是否复制软链接指向的目标，而不是软链接本身. 默认为保留软链接.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    if os.path.exists(src):
        copy(src, dst, overwrite, follow_symlinks)


@_support_dry_run(lambda path: f"[toolchains] Remove {path}.")
def remove(path: str, dry_run: bool | None = None) -> None:
    """删除指定路径

    Args:
        path (str): 要删除的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    if os.path.isdir(path):
        shutil.rmtree(path)
    else:
        os.remove(path)


@_support_dry_run(lambda path: f"[toolchains] Remove {path} if path exists.")
def remove_if_exists(path: str, dry_run: bool | None = None) -> None:
    """如果指定路径存在则删除指定路径

    Args:
        path (str): 要删除的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    if os.path.exists(path):
        remove(path)


@_support_dry_run(lambda path: f"[toolchains] Enter directory {path}.")
def chdir(path: str, dry_run: bool | None = None) -> str:
    """将工作目录设置为指定路径

    Args:
        path (str): 要进入的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.

    Returns:
        str: 之前的工作目录
    """
    cwd = os.getcwd()
    os.chdir(path)
    return cwd


@_support_dry_run(lambda src, dst: f"[toolchains] Rename {src} -> {dst}.")
def rename(src: str, dst: str, dry_run: bool | None = None) -> None:
    """重命名指定路径

    Args:
        src (str): 源路径
        dst (str): 目标路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    os.rename(src, dst)


class chdir_guard:
    """在构造时进入指定工作目录并在析构时回到原工作目录"""

    cwd: str
    dry_run: bool | None

    def __init__(self, path: str, dry_run: bool | None = None) -> None:
        self.dry_run = dry_run
        self.cwd = chdir(path, dry_run) or ""

    def __del__(self) -> None:
        chdir(self.cwd, self.dry_run)


def check_lib_dir(lib: str, lib_dir: str, do_assert: bool = True) -> bool:
    """检查库目录是否存在

    Args:
        lib (str): 库名称，用于提供错误报告信息
        lib_dir (str): 库目录
        do_assert (bool, optional): 是否断言库存在. 默认断言.

    Returns:
        bool: 返回库是否存在
    """
    message = f'[toolchains] Cannot find lib "{lib}" in directory "{lib_dir}"'
    if not do_assert and not os.path.exists(lib_dir):
        print(message)
        return False
    else:
        assert os.path.exists(lib_dir), message
    return True


class basic_environment:
    """gcc和llvm共用基本环境"""

    build: str  # build平台
    version: str  # 版本号
    major_version: str  # 主版本号
    home: str  # 源代码所在的目录
    jobs: int  # 编译所用线程数
    current_dir: str  # toolchains项目所在目录
    name_without_version: str  # 不带版本号的工具链名
    name: str  # 工具链名
    prefix_dir: str  # 安装路径
    bin_dir: str  # 安装后可执行文件所在目录

    def __init__(self, build: str, version: str, name_without_version: str, home: str, jobs: int, prefix_dir: str) -> None:
        self.build = build
        self.version = version
        self.major_version = self.version.split(".")[0]
        self.name_without_version = name_without_version
        self.name = self.name_without_version + self.major_version
        self.home = home
        self.jobs = jobs
        self.current_dir = os.path.abspath(os.path.dirname(__file__))
        self.prefix_dir = prefix_dir
        self.bin_dir = os.path.join(prefix_dir, self.name, "bin")

    def compress(self, name: str | None = None) -> None:
        """压缩构建完成的工具链

        Args:
            name (str, optional): 要压缩的目标名称，是相对于self.home的路径. 默认为self.name.
        """
        os.chdir(self.home)
        name = name or self.name
        run_command(f"tar -cf {name}.tar {name}")
        memory_MB = psutil.virtual_memory().available // 1048576 + 3072
        run_command(f"xz -fev9 -T 0 --memlimit={memory_MB}MiB {name}.tar")

    def register_in_env(self) -> None:
        """注册安装路径到环境变量"""
        os.environ["PATH"] = f"{self.bin_dir}:{os.environ['PATH']}"

    def register_in_bashrc(self) -> None:
        """注册安装路径到用户配置文件"""
        with open(os.path.join(self.home, ".bashrc"), "a") as bashrc_file:
            bashrc_file.write(f"export PATH={self.bin_dir}:$PATH\n")

    def copy_readme(self) -> None:
        """复制工具链说明文件"""
        readme_path = os.path.join(self.current_dir, "..", "readme", f"{self.name_without_version}.md")
        target_path = os.path.join(os.path.join(self.home, self.name), "README.md")
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


def _check_home(home: str) -> None:
    assert os.path.exists(home), f'The home dir "{home}" does not exist.'


class basic_configure:
    home: str  # 源码树根目录
    _origin_home_path: str  # 用户输入的原始源码树根目录

    @staticmethod
    def add_argument(parser: argparse.ArgumentParser) -> None:
        """为argparse添加--home、--export和--import选项

        Args:
            parser (argparse.ArgumentParser): 命令行解析器
        """
        parser.add_argument(
            "--home",
            type=str,
            help="The home directory to find source trees. "
            "If home is a relative path, it will be converted to an absolute path relative to the cwd.",
            default=str(pathlib.Path.home()),
        )
        parser.add_argument(
            "--export",
            dest="export_file",
            type=str,
            help="Export settings to specific file. The origin home path is saved to the configure file.",
        )
        parser.add_argument(
            "--import",
            dest="import_file",
            type=str,
            help="Import settings from specific file. "
            "If the home in configure file is a a relative path, "
            "it will be converted to an absolute path relative to the directory of the configure file.",
        )
        parser.add_argument(
            "--dry-run",
            dest="dry_run",
            action=argparse.BooleanOptionalAction,
            help="Preview the commands without actually executing them.",
            default=False,
        )

    @classmethod
    def parse_args(cls, args: argparse.Namespace) -> Self:
        """解析命令选项并根据选项构造对象

        Args:
            args (argparse.Namespace): 命令选项

        Returns:
            Self: 构造的对象，如果命令选项中没有对应参数则使用默认值
        """
        _check_home(args.home)
        command_dry_run.set(args.dry_run)
        args_list = vars(args)
        parma_list: dict[str, typing.Any] = {}
        for parma in itertools.islice(inspect.signature(cls.__init__).parameters.keys(), 1, None):
            assert parma != "home", "This function will set home. So home should not in the parma list of the __init__ function."
            if parma in args_list:
                parma_list[parma] = args_list[parma]
        result = cls(**parma_list)
        result._origin_home_path = args.home
        result.home = str(pathlib.Path(args.home).absolute())  # 尝试转化为基于当前工作目录的绝对路径
        return result

    def encode(self) -> dict[str, typing.Any]:
        """编码self到字典，可供序列化使用
        使用_origin_home_path作为输出的home字段，不会输出私有字段

        Returns:
            dict[str, typing.Any]: 编码后的字典
        """
        config_list: dict[str, typing.Any] = {}
        for key, value in vars(self).items():
            match (key, value):
                # 不序列化home
                case ("home", _):
                    pass
                # 将_origin_home_path保存到home字段
                case ("_origin_home_path", _):
                    config_list["home"] = value
                # 将pathlib.Path转化为字符串
                case (_, pathlib.Path()):
                    config_list[key] = str(value)
                # 不序列化私有字段
                case (_, _) if key.startswith("_"):
                    pass
                # 正常转化
                case (_, _):
                    config_list[key] = value

        return config_list

    def save_config(self, args: argparse.Namespace) -> None:
        """将配置保存到文件，使用json格式

        Args:
            config (object): 要保存的对象
            args (argparse.Namespace): 用户输入参数

        Raises:
            RuntimeError: 保存失败抛出异常
        """
        export_file: str | None = args.export_file
        if export_file:
            try:
                with open(export_file, "w") as file:
                    json.dump(self.encode(), file, indent=4)
                print(f'[toolchains] Settings have been written to file "{export_file}"')
            except Exception as e:
                raise RuntimeError(f'Export settings to file "{export_file}" failed: {e}')

    def load_config(self, args: argparse.Namespace) -> None:
        """从配置文件中加载配置，然后合并加载的配置和用户输入的配置

        Args:
            current_config (object): 当前用户输入的配置
            args (argparse.Namespace): 用户输入参数

        Raises:
            RuntimeError: 加载失败抛出异常
        """
        import_file: str | None = args.import_file
        if import_file:
            try:
                with open(import_file) as file:
                    import_config_list = json.load(file)
                assert isinstance(import_config_list, dict), f"Invalid configure file. The configure file must begin with a object."
            except Exception as e:
                raise RuntimeError(f'Import file "{import_file}" failed: {e}')

            if home_path := import_config_list.get("home"):
                home_path = pathlib.Path(home_path)
                if not home_path.is_absolute():
                    home_path = pathlib.Path(import_file).parent / home_path
                import_config_list["home"] = str(home_path)
            current_config_list = vars(self)
            default_config_list = vars(type(self)())
            self.__dict__ = {
                # 若import_config中没有则使用default_config中的值，以便在配置类更新后原配置文件可以正确加载
                key: (import_config_list.get(key, default_value) if (default_value := default_config_list.get(key)) == value else value)
                for key, value in current_config_list.items()
            }

    def reset_list_if_empty(self, list_name: str, arg_name: str, args: argparse.Namespace) -> None:
        """在用户输入指定列表类型选项，但没有指定表项时将该选项变为默认选项
           用于允许用户清空从配置文件中加载的列表类型选项

        Args:
            list_name (str): 列表成员名称
            arg_name (str): 用户输入对应参数的名称
            args (argparse.Namespace): 用户输入参数
        """
        assert isinstance(getattr(self, list_name), list), f"The {list_name} must be a list."
        if args.import_file and getattr(args, arg_name) == []:
            setattr(self, list_name, getattr(type(self)(), list_name))


assert __name__ != "__main__", "Import this file instead of running it directly."
