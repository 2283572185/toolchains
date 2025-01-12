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
    command: str | list[str], ignore_error: bool = False, capture: bool = False, echo: bool = True, dry_run: bool | None = None
) -> subprocess.CompletedProcess[str] | None:
    """运行指定命令, 若不忽略错误, 则在命令执行出错时抛出RuntimeError, 反之打印错误码

    Args:
        command (str | list[str]): 要运行的命令，使用str则在shell内运行，使用list[str]则直接运行
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
        result = subprocess.run(
            command if isinstance(command, str) else " ".join(command),
            stdout=pipe,
            stderr=pipe,
            shell=isinstance(command, str),
            check=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        if not ignore_error:
            raise RuntimeError(f'Command "{command}" failed.')
        elif echo:
            print(f'Command "{command}" failed with errno={e.returncode}, but it is ignored.')
        return None
    return result


@_support_dry_run(lambda path: f"[toolchains] Create directory {path}.")
def mkdir(path: pathlib.Path, remove_if_exist: bool = True, dry_run: bool | None = None) -> None:
    """创建目录

    Args:
        path (pathlib.Path): 要创建的目录
        remove_if_exist (bool, optional): 是否先删除已存在的同名目录. 默认先删除已存在的同名目录.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    if remove_if_exist and os.path.exists(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


@_support_dry_run(lambda src, dst: f"[toolchains] Copy {src} -> {dst}.")
def copy(src: pathlib.Path, dst: pathlib.Path, overwrite: bool = True, follow_symlinks: bool = False, dry_run: bool | None = None) -> None:
    """复制文件或目录

    Args:-> Callable[[Callable[P, R]], functools._Wrapped[P, R, P, R | None]]
        src (pathlib.Path): 源路径
        dst (pathlib.Path): 目标路径
        overwrite (bool, optional): 是否覆盖已存在项. 默认为覆盖.
        follow_symlinks (bool, optional): 是否复制软链接指向的目标，而不是软链接本身. 默认为保留软链接.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    # 创建目标目录
    dir = dst.parent
    mkdir(dir, False)
    if not overwrite and dst.exists():
        return
    if os.path.isdir(src):
        if dst.exists():
            shutil.rmtree(dst)
        shutil.copytree(src, dst, not follow_symlinks)
    else:
        if dst.exists():
            os.remove(dst)
        shutil.copyfile(src, dst, follow_symlinks=follow_symlinks)


@_support_dry_run(lambda src, dst: f"[toolchains] Copy {src} -> {dst} if src exists.")
def copy_if_exist(
    src: pathlib.Path, dst: pathlib.Path, overwrite: bool = True, follow_symlinks: bool = False, dry_run: bool | None = None
) -> None:
    """如果文件或目录存在则复制文件或目录

    Args:
        src (pathlib.Path): 源路径
        dst (pathlib.Path): 目标路径
        overwrite (bool, optional): 是否覆盖已存在项. 默认为覆盖.
        follow_symlinks (bool, optional): 是否复制软链接指向的目标，而不是软链接本身. 默认为保留软链接.
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    if src.exists():
        copy(src, dst, overwrite, follow_symlinks)


@_support_dry_run(lambda path: f"[toolchains] Remove {path}.")
def remove(path: pathlib.Path, dry_run: bool | None = None) -> None:
    """删除指定路径

    Args:
        path (pathlib.Path): 要删除的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    if path.is_dir():
        shutil.rmtree(path)
    else:
        os.remove(path)


@_support_dry_run(lambda path: f"[toolchains] Remove {path} if path exists.")
def remove_if_exists(path: pathlib.Path, dry_run: bool | None = None) -> None:
    """如果指定路径存在则删除指定路径

    Args:
        path (pathlib.Path): 要删除的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    if path.exists():
        remove(path)


@_support_dry_run(lambda path: f"[toolchains] Enter directory {path}.")
def chdir(path: pathlib.Path, dry_run: bool | None = None) -> pathlib.Path:
    """将工作目录设置为指定路径

    Args:
        path (pathlib.Path): 要进入的路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.

    Returns:
        pathlib.Path: 之前的工作目录
    """
    cwd = pathlib.Path.cwd()
    os.chdir(path)
    return cwd


@_support_dry_run(lambda src, dst: f"[toolchains] Rename {src} -> {dst}.")
def rename(src: pathlib.Path, dst: pathlib.Path, dry_run: bool | None = None) -> None:
    """重命名指定路径

    Args:
        src (pathlib.Path): 源路径
        dst (pathlib.Path): 目标路径
        dry_run (bool | None, optional): 是否只回显命令而不执行，默认为None.
    """
    src.rename(dst)


class chdir_guard:
    """在构造时进入指定工作目录并在析构时回到原工作目录"""

    cwd: pathlib.Path
    dry_run: bool | None

    def __init__(self, path: pathlib.Path, dry_run: bool | None = None) -> None:
        self.dry_run = dry_run
        self.cwd = chdir(path, dry_run) or pathlib.Path()

    def __del__(self) -> None:
        chdir(self.cwd, self.dry_run)


def check_lib_dir(lib: str, lib_dir: pathlib.Path, do_assert: bool = True) -> bool:
    """检查库目录是否存在

    Args:
        lib (str): 库名称，用于提供错误报告信息
        lib_dir (pathlib.Path): 库目录
        do_assert (bool, optional): 是否断言库存在. 默认断言.

    Returns:
        bool: 返回库是否存在
    """
    message = f'[toolchains] Cannot find lib "{lib}" in directory "{lib_dir}"'
    if not do_assert and not lib_dir.exists():
        print(message)
        return False
    else:
        assert lib_dir.exists(), message
    return True


class basic_environment:
    """gcc和llvm共用基本环境"""

    build: str  # build平台
    version: str  # 版本号
    major_version: str  # 主版本号
    home: pathlib.Path  # 源代码所在的目录
    jobs: int  # 编译所用线程数
    current_dir: pathlib.Path  # toolchains项目所在目录
    name_without_version: str  # 不带版本号的工具链名
    name: str  # 工具链名
    prefix_dir: pathlib.Path  # 安装路径
    bin_dir: pathlib.Path  # 安装后可执行文件所在目录

    def __init__(
        self, build: str, version: str, name_without_version: str, home: pathlib.Path, jobs: int, prefix_dir: pathlib.Path
    ) -> None:
        self.build = build
        self.version = version
        self.major_version = self.version.split(".")[0]
        self.name_without_version = name_without_version
        self.name = self.name_without_version + self.major_version
        self.home = home
        self.jobs = jobs
        self.current_dir = pathlib.Path(__file__).parent.resolve()
        self.prefix_dir = prefix_dir
        self.bin_dir = prefix_dir / self.name / "bin"

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
        os.environ["PATH"] = f"{self.bin_dir}{os.pathsep}{os.environ['PATH']}"

    def register_in_bashrc(self) -> None:
        """注册安装路径到用户配置文件"""
        with (self.home / ".bashrc").open("a") as bashrc_file:
            bashrc_file.write(f"export PATH={self.bin_dir}:$PATH\n")

    def copy_readme(self) -> None:
        """复制工具链说明文件"""
        readme_path = self.current_dir.parent / "readme" / f"{self.name_without_version}.md"
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


def _check_home(home: str | pathlib.Path) -> None:
    assert pathlib.Path(home).exists(), f'The home dir "{home}" does not exist.'


class basic_configure:
    """配置基类

    Attributes:
        encode_name_map: 编码时使用的构造函数参数名->成员名映射表
    """

    home: pathlib.Path
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

    def __init__(self, home: str = str(pathlib.Path.home()), base_path: pathlib.Path = pathlib.Path.cwd()) -> None:
        """初始化配置基类

        Args:
            home (pathlib.Path, optional): 源码树根目录. 默认为当前用户主目录.
            base_path (pathlib.Path, optional): 当home为相对路径时，转化home为绝对路径使用的基路径. 默认为当前工作目录.
        """
        self._origin_home_path = home
        self.home = (base_path / home).resolve()

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
            default=str(basic_configure().home),
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
            file_path = pathlib.Path(import_file)
            try:
                import_config_list = json.loads(file_path.read_text())
                assert isinstance(import_config_list, dict), f"Invalid configure file. The configure file must begin with a object."
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
        """解析命令选项并根据选项构造对象

        Args:
            args (argparse.Namespace): 命令选项

        Returns:
            Self: 构造的对象，如果命令选项中没有对应参数则使用默认值
        """
        _check_home(args.home)
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
        input_list["base_path"] = pathlib.Path.cwd()

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
                    output_list[key] = list(value)
                # 将pathlib.Path转化为字符串
                case pathlib.Path():
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

    @_support_dry_run(lambda self: f"[toolchains] Save settings -> {file}." if (file := self._args.export_file) else None)
    def save_config(self) -> None:
        """将配置保存到文件，使用json格式

        Args:
            config (object): 要保存的对象
            args (argparse.Namespace): 用户输入参数

        Raises:
            RuntimeError: 保存失败抛出异常
        """
        if export_file := self._args.export_file:
            file_path = pathlib.Path(export_file)
            try:
                file_path.write_text(json.dumps(self.encode(), indent=4))
            except Exception as e:
                raise RuntimeError(f'Export settings to file "{file_path}" failed: {e}')


assert __name__ != "__main__", "Import this file instead of running it directly."
