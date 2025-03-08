import enum
import typing
from collections.abc import Sequence
from pathlib import Path

import packaging.version as version

from . import common


class extra_lib_version(enum.StrEnum):
    python = "3.13.2"
    iconv = "1.18"
    loongnix_linux = "4.19.190.8.22"
    loongnix_glibc = "2.28"
    loongnix = loongnix_linux
    gmp = "6.3.0"
    mpfr = "4.2.1"

    def _save_version_echo(self, dir: Path) -> str:
        """在保存包信息时回显信息

        Args:
            dir (Path): 要保存版本信息文件的目录

        Returns:
            str: 回显信息
        """

        return common.toolchains_info(f"Save version of {self.name} -> {dir / ".version"}.")

    @common.support_dry_run(_save_version_echo)
    def save_version(self, dir: Path) -> None:
        """将包版本信息保存到dir/.version文件中

        Args:
            dir (Path): 要保存版本信息文件的目录
        """

        (dir / ".version").write_text(self)

    def check_version(self, dir: Path) -> int:
        """检查包版本

        Args:
            dir (Path): 包根目录

        Returns:
            int: 三路比较结果，1为存在更新版本，0为版本一致，-1为需要更新
        """

        try:
            with (dir / ".version").open() as file:
                current_version = version.Version(file.readline())
                target_version = version.Version(self)
                if current_version > target_version:
                    return 1
                elif current_version == target_version:
                    return 0
                else:
                    return -1
        except Exception:
            return -1


def get_current_glibc_version() -> str | None:
    """获取当前glibc版本

    Returns:
        (str | None): 当前平台glibc版本，获取失败返回None
    """

    result = common.run_command("getconf GNU_LIBC_VERSION", ignore_error=True, capture=True, echo=False, dry_run=False)
    if result:
        return result.stdout.strip().split(" ", 1)[1]
    else:
        return None


class git_clone_type(enum.StrEnum):
    """git克隆类型

    Attributes:
        partial: 使用部分克隆，仅克隆提交树，然后签出最新提交。在一些较老的git服务器上不受支持。
        shallow: 使用浅克隆，仅克隆depth中指定数量的提交，可以加速克隆，但可能减慢git pull等操作。
        full: 使用完全克隆，克隆完整的git仓库，消耗较多流量和时间。
    """

    partial = "partial"  # 部分克隆
    shallow = "shallow"  # 浅克隆
    full = "full"  # 完全克隆

    @staticmethod
    def get_clone_option(config: "configure") -> str:
        match (config.clone_type):
            case git_clone_type.partial:
                return "--filter=blob:none"
            case git_clone_type.shallow:
                return f"--depth={config.shallow_clone_depth}"
            case git_clone_type.full:
                return ""


class git_url:
    remote: str
    path: str
    default_protocol: str

    def __init__(self, remote: str, path: str, default_protocol: str = "https") -> None:
        """配置一个git包的远程源

        Args:
            remote (str): 托管平台名称
            path (str): git包在托管平台下的路径
            default_protocol (str, optional): 非ssh模式下默认的网络协议. 默认为https.
        """

        self.remote = remote
        self.path = path
        self.default_protocol = default_protocol

    def get_url(self, prefer_ssh: bool) -> str:
        """获取git仓库的url

        Args:
            prefer_ssh (bool): 是否倾向于使用ssh
        """

        use_ssh = prefer_ssh and self.remote == "github.com"
        return f"git@{self.remote}:{self.path}" if use_ssh else f"{self.default_protocol}://{self.remote}/{self.path}"


class git_prefer_remote(enum.StrEnum):
    """git远程托管平台

    Attributes:
        github: 使用GitHub上的仓库，部分为镜像源
        native: 使用项目的原git仓库作为源
        nju   : 在可能时使用南京大学镜像源，否则退回到使用GitHub源
        tuna  : 在可能时使用清华大学镜像源，否则退回到使用GitHub源
        bfsu  : 在可能时使用北京外国语大学镜像源，否则退回到使用GitHub源
        nyist : 在可能时使用南阳理工学院镜像源，否则退回到使用GitHub源
        cernet: 在可能时使用校园网联合镜像源，否则退回到使用GitHub源
    """

    github = "github"
    native = "native"
    nju = "nju"
    tuna = "tuna"
    bfsu = "bfsu"
    nyist = "nyist"
    cernet = "cernet"


class extra_lib:
    """非git包的配置"""

    url_list: dict[Path, str]
    install_dir: list[Path]
    version_dir: Path

    def __init__(self, url_list: dict[str, str], install_dir: Sequence[str | Path], version_dir: str | Path) -> None:
        """描述一个非git包的配置

        Args:
            url_list (dict[str, str]): 各个资源列表，dict[下载后文件名, url]
            install_dir (list[str | Path]): 安装路径
            version_dir (str): 包含版本文件的目录
        """

        self.url_list = {Path(file): url for file, url in url_list.items()}
        self.install_dir = [Path(dir) for dir in install_dir]
        self.version_dir = Path(version_dir)

    def create_mirror(self, url_list: dict[str, str]) -> "extra_lib":
        """在本包配置的基础上创建一个镜像

        Args:
            url_list (dict[str, str]): 镜像使用的url列表，dict[下载后文件名, url]
        """

        return extra_lib(url_list, self.install_dir, self.version_dir)

    def check_exist(self, config: "configure") -> bool:
        """检查包是否存在

        Args:
            config (environment): 源代码下载环境
        """

        for path in self.install_dir:
            if not (config.home / path).exists():
                return False
        else:
            return True


class all_lib_list:
    """所有包源列表

    Attributes:
        system_lib_list    : 系统包表
        git_lib_list_github: git包的GitHub源
        git_lib_list_native: git包的原仓库源
        git_lib_list_nju   : git包的南京大学镜像源
        git_lib_list_tuna  : git包的清华大学镜像源
        git_lib_list_bfsu  : git包的北京外国语大学镜像源
        git_lib_list_nyist : git包的南阳理工学院镜像源
        git_lib_list_cernet: git包的校园网联合镜像源
        extra_lib_list     : 非git包的信息列表，默认为南京大学镜像
        extra_lib_list_native: 非git包的信息列表，不使用镜像
        necessary_extra_lib_list: 必须的非git包列表
        optional_extra_lib_list : 可选的非git包列表
        all_lib_list       : 所有受支持的包列表
    """

    system_lib_list: typing.Final[list[str]] = [
        "bison",
        "flex",
        "texinfo",
        "make",
        "automake",
        "autoconf",
        "libtool",
        "git",
        "gcc",
        "g++",
        "tar",
        "zstd",
        "unzip",
        "libgmp-dev",
        "libmpfr-dev",
        "zlib1g-dev",
        "libexpat1-dev",
        "gawk",
        "bzip2",
        "cmake",
        "ninja-build",
        "clang",
        "lld",
        "libxml2-dev",
        "wget",
    ]
    git_lib_list_github: typing.Final[dict[str, git_url]] = {
        "gcc": git_url("github.com", "gcc-mirror/gcc.git"),
        "binutils": git_url("github.com", "bminor/binutils-gdb.git"),
        "mingw": git_url("github.com", "mirror/mingw-w64.git"),
        "expat": git_url("github.com", "libexpat/libexpat.git"),
        "linux": git_url("github.com", "torvalds/linux.git"),
        "glibc": git_url("github.com", "bminor/glibc.git"),
        "pexports": git_url("github.com", "bocke/pexports.git"),
        "zlib": git_url("github.com", "madler/zlib.git"),
        "libxml2": git_url("github.com", "GNOME/libxml2.git"),
        "newlib": git_url("github.com", "bminor/newlib.git"),
        "llvm": git_url("github.com", "llvm/llvm-project.git"),
    }
    git_lib_list_native: typing.Final[dict[str, git_url]] = {
        **git_lib_list_github,
        "gcc": git_url("gcc.gnu.org", "git/gcc.git", "git"),
        "binutils": git_url("sourceware.org", "git/binutils-gdb.git"),
        "mingw": git_url("git.code.sf.net", "p/mingw-w64/mingw-w64 mingw-w64-mingw-w64.git", "git"),
        "glibc": git_url("sourceware.org", "git/glibc.git"),
        "pexports": git_url("git.osdn.net", "gitroot/mingw/pexports.git", "git"),
        "libxml2": git_url("gitlab.gnome.org", "GNOME/libxml2.git"),
        "newlib": git_url("sourceware.org", "git/newlib-cygwin.git"),
    }
    git_lib_list_nju: typing.Final[dict[str, git_url]] = {
        **git_lib_list_github,
        "gcc": git_url("mirror.nju.edu.cn", "git/gcc.git"),
        "binutils": git_url("mirror.nju.edu.cn", "git/binutils-gdb.git"),
        "glibc": git_url("mirror.nju.edu.cn", "git/glibc.git"),
        "linux": git_url("mirror.nju.edu.cn", "git/linux.git"),
        "llvm": git_url("mirror.nju.edu.cn", "git/llvm-project.git"),
    }
    git_lib_list_tuna: typing.Final[dict[str, git_url]] = {
        **git_lib_list_github,
        "gcc": git_url("mirrors.tuna.tsinghua.edu.cn", "git/gcc.git"),
        "binutils": git_url("mirrors.tuna.tsinghua.edu.cn", "git/binutils-gdb.git"),
        "glibc": git_url("mirrors.tuna.tsinghua.edu.cn", "git/glibc.git"),
        "linux": git_url("mirrors.tuna.tsinghua.edu.cn", "git/linux.git"),
        "llvm": git_url("mirrors.tuna.tsinghua.edu.cn", "git/llvm-project.git"),
    }
    git_lib_list_bfsu: typing.Final[dict[str, git_url]] = {
        **git_lib_list_github,
        "gcc": git_url("mirrors.bfsu.edu.cn", "git/gcc.git"),
        "binutils": git_url("mirrors.bfsu.edu.cn", "git/binutils-gdb.git"),
        "glibc": git_url("mirrors.bfsu.edu.cn", "git/glibc.git"),
        "linux": git_url("mirrors.bfsu.edu.cn", "git/linux.git"),
        "llvm": git_url("mirrors.bfsu.edu.cn", "git/llvm-project.git"),
    }
    git_lib_list_nyist: typing.Final[dict[str, git_url]] = {
        **git_lib_list_github,
        "gcc": git_url("mirror.nyist.edu.cn", "git/gcc.git"),
        "binutils": git_url("mirror.nyist.edu.cn", "git/binutils-gdb.git"),
        "glibc": git_url("mirror.nyist.edu.cn", "git/glibc.git"),
        "linux": git_url("mirror.nyist.edu.cn", "git/linux.git"),
        "llvm": git_url("mirror.nyist.edu.cn", "git/llvm-project.git"),
    }
    git_lib_list_cernet: typing.Final[dict[str, git_url]] = {
        **git_lib_list_github,
        "gcc": git_url("mirrors.cernet.edu.cn", "gcc.git"),
        "binutils": git_url("mirrors.cernet.edu.cn", "binutils-gdb.git"),
        "glibc": git_url("mirrors.cernet.edu.cn", "glibc.git"),
        "linux": git_url("mirrors.cernet.edu.cn", "linux.git"),
        "llvm": git_url("mirrors.cernet.edu.cn", "llvm-project.git"),
    }

    # 额外包列表，由于native网络性能不佳，默认使用南京大学镜像
    extra_lib_list: typing.Final[dict[str, extra_lib]] = {
        "python-embed": extra_lib(
            {
                "python-embed.zip": f"https://mirrors.nju.edu.cn/python/{extra_lib_version.python}/python-{extra_lib_version.python}-embed-amd64.zip",
                "python_source.tar.xz": f"https://mirrors.nju.edu.cn/python/{extra_lib_version.python}/Python-{extra_lib_version.python}.tar.xz",
            },
            ["python-embed"],
            "python-embed",
        ),
        "loongnix": extra_lib(
            {
                "linux-loongnix.tar.gz": f"https://mirrors.nju.edu.cn/loongnix/pool/main/l/linux/linux_{extra_lib_version.loongnix_linux}.orig.tar.gz",
                "glibc-loongnix.tar.zst": f"https://github.com/24bit-xjkp/toolchains/releases/download/vendor-packages/glibc-loongnix-{extra_lib_version.loongnix_glibc}.tar.zst",
            },
            ["linux-loongnix", "glibc-loongnix"],
            "linux-loongnix",
        ),
        "iconv": extra_lib(
            {"iconv.tar.gz": f"https://ftp.gnu.org/pub/gnu/libiconv/libiconv-{extra_lib_version.iconv}.tar.gz"},
            [Path("binutils", "gdb", "libiconv")],
            Path("binutils", "gdb", "libiconv"),
        ),
        "gmp": extra_lib({"gmp.tar.xz": f"https://gmplib.org/download/gmp/gmp-{extra_lib_version.gmp}.tar.xz"}, ["gmp"], "gmp"),
        "mpfr": extra_lib({"mpfr.tar.xz": f"https://www.mpfr.org/mpfr-current/mpfr-{extra_lib_version.mpfr}.tar.xz"}, ["mpfr"], "mpfr"),
    }
    extra_lib_list_native: typing.Final[dict[str, extra_lib]] = {
        **extra_lib_list,
        "python-embed": extra_lib_list["python-embed"].create_mirror(
            {
                "python-embed.zip": f"https://www.python.org/ftp/python/{extra_lib_version.python}/python-{extra_lib_version.python}-embed-amd64.zip",
                "python_source.tar.xz": f"https://www.python.org/ftp/python/{extra_lib_version.python}/Python-{extra_lib_version.python}.tar.xz",
            }
        ),
        "loongnix": extra_lib_list["loongnix"].create_mirror(
            {
                "linux-loongnix.tar.gz": f"https://pkg.loongnix.cn/loongnix/pool/main/l/linux/linux_{extra_lib_version.loongnix_linux}.orig.tar.gz",
                "glibc-loongnix.tar.zst": f"https://gitee.com/xjkp-24bit/toolchains/releases/download/vendor-packages/glibc-loongnix-{extra_lib_version.loongnix_glibc}.tar.zst",
            }
        ),
    }
    necessary_extra_lib_list: typing.Final[set[str]] = {"python-embed", "gmp", "mpfr"}
    optional_extra_lib_list: typing.Final[set[str]] = {lib for lib in extra_lib_list} - necessary_extra_lib_list
    all_lib_list: typing.Final[list[str]] = [*git_lib_list_github, *extra_lib_list, "gcc_contrib"]

    @staticmethod
    def get_prefer_git_lib_list(config: "configure") -> dict[str, git_url]:
        """根据配置选择使用合适git源的git包列表

        Args:
            config (configure): 当前下载配置

        Returns:
            dict[str, git_url]: git包列表
        """

        return typing.cast(dict[str, git_url], getattr(all_lib_list, f"git_lib_list_{config.git_remote}"))

    @staticmethod
    def get_prefer_extra_lib_list(config: "configure", lib: str) -> extra_lib:
        """根据配置选择使用合适镜像源的非git包

        Args:
            config (configure): 当前下载配置
            lib (str): 包名称

        Returns:
            extra_lib: 非git包对象
        """

        return typing.cast(dict[str, extra_lib], getattr(all_lib_list, f"extra_lib_list_{config.git_remote}", all_lib_list.extra_lib_list))[
            lib
        ]


class configure(common.basic_configure):
    """源代码下载配置信息"""

    glibc_version: str | None
    clone_type: git_clone_type
    shallow_clone_depth: int
    git_use_ssh: bool
    extra_lib_list: set[str]
    network_try_times: int
    git_remote: git_prefer_remote

    _origin_extra_lib_list: set[str]  # 用户输入的其他非git托管包列表
    _origin_retry: int  # 用户输入的重试的次数

    def __init__(
        self,
        glibc_version: str | None = None,
        clone_type: str = git_clone_type.partial,
        depth: int = 1,
        ssh: bool = False,
        extra_libs: list[str] | None = None,
        retry: int = 5,
        remote: str = git_prefer_remote.github,
    ) -> None:
        """设置源代码配置信息，可默认构造以提供默认配置

        Args:
            glibc_version (str | None, optional): glibc版本号. 默认为当前平台的glibc版本.
            clone_type (str, optional): git克隆类型. 默认为部分克隆.
            depth (int, optional): git浅克隆深度. 默认为1.
            ssh (bool, optional): 是否使用ssh克隆GitHub上的git包. 默认为不用ssh，即使用https.
            extra_libs (list[str] | None, optional): 额外的非git包列表. 默认不启用额外包.
            retry (int, optional): 进行网络操作时重试的次数. 默认为5次.
            remote (str, optional): 倾向于使用的git源. 默认为GitHub源.
        """

        super().__init__()
        self.glibc_version = glibc_version or get_current_glibc_version()
        self.clone_type = git_clone_type[clone_type]
        self.shallow_clone_depth = depth
        self.register_encode_name_map("depth", "shallow_clone_depth")
        self.git_use_ssh = ssh
        self.register_encode_name_map("ssh", "git_use_ssh")
        self._origin_extra_lib_list = {*(extra_libs or [])}
        self.register_encode_name_map("extra_libs", "_origin_extra_lib_list")
        self.extra_lib_list = {*all_lib_list.necessary_extra_lib_list, *self._origin_extra_lib_list}
        self._origin_retry = retry
        self.register_encode_name_map("retry", "_origin_retry")
        self.network_try_times = self._origin_retry + 1
        self.git_remote = git_prefer_remote[remote]
        self.register_encode_name_map("remote", "git_remote")

    def check(self, need_glibc: bool) -> None:
        """检查各个参数是否合法"""

        common.check_home(self.home)
        if need_glibc:
            assert self.glibc_version, f"Invalid glibc version: {self.glibc_version}"
        assert self.shallow_clone_depth > 0, f"Invalid shallow clone depth: {self.shallow_clone_depth}."
        assert self.network_try_times >= 1, f"Invalid network try times: {self.network_try_times}."


class after_download_list:
    """在包下载完成后执行的回调函数"""

    @staticmethod
    def expat(config: configure) -> None:
        """通过autoconf生成expat的configure文件

        Args:
            config (configure): 当前源代码下载配置
        """

        with common.chdir_guard(config.home / "expat" / "expat"):
            common.run_command("./buildconf.sh")

    @staticmethod
    def pexports(config: configure) -> None:
        """通过autoconf生成pexports的configure文件

        Args:
            config (configure): 当前源代码下载配置
        """

        with common.chdir_guard(config.home / "pexports"):
            common.run_command("autoreconf -if")

    @staticmethod
    def python_embed(config: configure) -> None:
        """解压python embed package和python源代码，提取出dll和include文件，并合并到python-embed文件夹中

        Args:
            config (configure): 当前源代码下载配置
        """

        python_version = extra_lib_version.python
        python_embed_zip = config.home / "python-embed.zip"
        python_source_txz = config.home / "python_source.tar.xz"
        python_source = config.home / "python_source"
        python_embed = config.home / "python-embed"
        # 删除已安装包
        common.remove_if_exists(python_embed)

        # 解压embed包
        common.run_command(f"unzip -o {python_embed_zip}  python3*.dll python3*.zip *._pth -d {python_embed} -x python3.dll")
        common.remove(python_embed_zip)
        # 解压源代码包
        common.run_command(f"tar -xaf {python_source_txz}")
        common.rename(Path(f"Python-{python_version}"), python_source)
        common.remove(python_source_txz)

        # 复制头文件
        include_dir = python_embed / "include"
        common.copy(python_source / "Include", include_dir)
        common.copy(python_source / "PC" / "pyconfig.h.in", include_dir / "pyconfig.h")
        common.remove(python_source)

        # 记录python版本号
        python_version.save_version(python_embed)

    @staticmethod
    def loongnix(config: configure) -> None:
        """解压loongnix的linux和glibc源代码到linux-loongnix和glibc-loongnix文件夹下

        Args:
            config (configure): 当前源代码下载配置
        """

        linux_tgz = config.home / "linux-loongnix.tar.gz"
        glibc_tzst = config.home / "glibc-loongnix.tar.zst"
        linux_dir = config.home / "linux-loongnix"
        glibc_dir = config.home / "glibc-loongnix"
        # 删除已安装包
        common.remove_if_exists(linux_dir)
        common.remove_if_exists(glibc_dir)
        # 解压linux
        common.mkdir(linux_dir)
        common.run_command(f"tar -xaf {linux_tgz} -C {linux_dir}")
        common.remove(linux_tgz)
        # 解压glibc
        common.mkdir(glibc_dir)
        common.run_command(f"tar -xaf {glibc_tzst} -C {glibc_dir}")
        common.remove(glibc_tzst)

        extra_lib_version.loongnix.save_version(linux_dir)

    @staticmethod
    def iconv(config: configure) -> None:
        """解压iconv包到gdb目录下

        Args:
            config (configure): 当前源代码下载配置
        """

        iconv_version = extra_lib_version.iconv
        gdb_dir = config.home / "binutils" / "gdb"
        iconv_tgz = config.home / "iconv.tar.gz"
        iconv_dir = gdb_dir / "libiconv"
        # 删除已安装包
        common.remove_if_exists(iconv_dir)
        common.run_command(f"tar -xaf {iconv_tgz} -C {gdb_dir}")
        common.rename(gdb_dir / f"libiconv-{iconv_version}", iconv_dir)
        common.remove(iconv_tgz)
        iconv_version.save_version(iconv_dir)

    @staticmethod
    def gmp(config: configure) -> None:
        """解压gmp到home下

        Args:
            config (configure): 当前源代码下载配置
        """

        gmp_version = extra_lib_version.gmp
        gmp_dir = config.home / "gmp"
        gmp_txz = config.home / "gmp.tar.xz"
        # 删除已安装包
        common.remove_if_exists(gmp_dir)
        common.run_command(f"tar -xaf {gmp_txz} -C {config.home}")
        common.rename(config.home / f"gmp-{gmp_version}", gmp_dir)
        common.remove(gmp_txz)
        gmp_version.save_version(gmp_dir)

    @staticmethod
    def mpfr(config: configure) -> None:
        """解压mpfr到home下

        Args:
            config (configure): 当前源代码下载配置
        """

        mpfr_version = extra_lib_version.mpfr
        mpfr_dir = config.home / "mpfr"
        mpfr_txz = config.home / "mpfr.tar.xz"
        # 删除已安装包
        common.remove_if_exists(mpfr_dir)
        common.run_command(f"tar -xaf {mpfr_txz} -C {config.home}")
        common.rename(config.home / f"mpfr-{mpfr_version}", mpfr_dir)
        common.remove(mpfr_txz)
        mpfr_version.save_version(mpfr_dir)

    @staticmethod
    def after_download_specific_lib(config: configure, lib: str) -> None:
        """根据包名执行对应的回调函数

        Args:
            config (configure): 当前源代码下载配置
            lib (str): 下载好的包名
        """

        lib = lib.replace("-", "_")
        if lib in vars(after_download_list) and not common.command_dry_run.get():
            getattr(after_download_list, lib)(config)


class extra_git_options_list:
    """克隆git包时要使用的额外git选项表"""

    @staticmethod
    def glibc(config: configure) -> list[str]:
        """获取glibc的额外克隆选项，需要设置指定的分支

        Args:
            config (configure): 当前源代码下载配置
        """
        return [f"-b release/{config.glibc_version}/master"]

    @staticmethod
    def get_option(config: configure, lib: str) -> list[str]:
        """根据要克隆的git包名获取额外选项

        Args:
            config (configure): 当前源代码下载配置
            lib (str): git包名

        Returns:
            list[str]: 额外选项表
        """
        if lib in vars(extra_git_options_list):
            return typing.cast(list[str], getattr(extra_git_options_list, lib)(config))
        return []


__all__ = [
    "extra_lib_version",
    "git_clone_type",
    "git_prefer_remote",
    "all_lib_list",
    "configure",
    "after_download_list",
    "extra_git_options_list",
]
