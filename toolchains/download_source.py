import enum
import os
import typing

import packaging.version as version

from . import common


class extra_lib_version(enum.StrEnum):
    python = "3.13.1"
    iconv = "1.18"
    loongnix = "4.19.190"
    gmp = "6.3.0"
    mpfr = "4.2.1"

    @common._support_dry_run()
    def save_version(self, dir: str) -> None:
        """将包版本信息保存到dir/.version文件中

        Args:
            dir (str): 要保存版本信息文件的目录
        """
        with open(os.path.join(dir, ".version"), "w") as file:
            file.write(self)

    def check_version(self, dir: str) -> int:
        """检查包版本

        Args:
            dir (str): 包根目录

        Returns:
            int: 三路比较结果，1为存在更新版本，0为版本一致，-1为需要更新
        """
        try:
            with open(os.path.join(dir, ".version")) as file:
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


def get_current_glib_version() -> str | None:
    """获取当前glibc版本

    Returns:
        str | None: 当前平台glibc版本，获取失败返回None
    """
    result = common.run_command("getconf GNU_LIBC_VERSION", ignore_error=True, capture=True, echo=False, dry_run=False)
    if result:
        return result.stdout.strip().split(" ", 1)[1]
    else:
        return None


class git_clone_type(enum.StrEnum):
    """git克隆类型"""

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
    remote: str  # 托管平台
    path: str  # git路径
    default_protocol: str  # 非ssh下默认的网络协议

    def __init__(self, remote: str, path: str, default_protocol: str = "https") -> None:
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
    """git远程托管平台"""

    github = "github"
    native = "native"
    nju = "nju"
    tuna = "tuna"
    bfsu = "bfsu"
    nyist = "nyist"
    cernet = "cernet"


class extra_lib:
    url_list: dict[str, str]  # 各个资源列表，dict[下载后文件名, url]
    install_dir: list[str]  # 安装路径
    version_dir: str  # 包含版本文件的目录

    def __init__(self, url_list: dict[str, str], install_dir: list[str], version_dir: str) -> None:
        self.url_list = url_list
        self.install_dir = install_dir
        self.version_dir = version_dir

    def check_exist(self, config: "configure") -> bool:
        """检查包是否存在

        Args:
            config (environment): 源代码下载环境
        """
        for path in self.install_dir:
            if not os.path.exists(os.path.join(config.home, path)):
                return False
        else:
            return True


class all_lib_list:
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
        "python3",
        "tar",
        "xz-utils",
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
        "zlib1g-dev",
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

    extra_lib_list: typing.Final[dict[str, extra_lib]] = {
        "python-embed": extra_lib(
            {
                "python-embed.zip": f"https://www.python.org/ftp/python/{extra_lib_version.python}/python-{extra_lib_version.python}-embed-amd64.zip",
                "python_source.tar.xz": f"https://www.python.org/ftp/python/{extra_lib_version.python}/Python-{extra_lib_version.python}.tar.xz",
            },
            ["python-embed"],
            "python-embed",
        ),
        "loongnix": extra_lib(
            {
                "linux-loongnix.tar.gz": "https://pkg.loongnix.cn/loongnix/pool/main/l/linux/linux_4.19.190.8.22.orig.tar.gz",
                "glibc-loongnix.tar.gz": "https://pkg.loongnix.cn/loongnix/pool/main/g/glibc/glibc_2.28.orig.tar.gz",
            },
            ["linux-loongnix", "glibc-loongnix"],
            "linux-loongnix",
        ),
        "iconv": extra_lib(
            {"iconv.tar.gz": f"https://ftp.gnu.org/pub/gnu/libiconv/libiconv-{extra_lib_version.iconv}.tar.gz"},
            [os.path.join("binutils", "gdb", "libiconv")],
            os.path.join("binutils", "gdb", "libiconv"),
        ),
        "gmp": extra_lib({"gmp.tar.xz": f"https://gmplib.org/download/gmp/gmp-{extra_lib_version.gmp}.tar.xz"}, ["gmp"], "gmp"),
        "mpfr": extra_lib({"mpfr.tar.xz": f"https://www.mpfr.org/mpfr-current/mpfr-{extra_lib_version.mpfr}.tar.xz"}, ["mpfr"], "mpfr"),
    }
    necessary_extra_lib_list: typing.Final[set[str]] = {"python-embed", "gmp", "mpfr"}  # 必须的非git托管包
    optional_extra_lib_list: typing.Final[set[str]] = {lib for lib in extra_lib_list} - necessary_extra_lib_list  # 可选的非git托管包
    all_lib_list: typing.Final[list[str]] = [*git_lib_list_github, *extra_lib_list, "gcc_contrib"]  # 所有受支持的包

    @staticmethod
    def get_prefer_git_lib_list(config: "configure") -> dict[str, git_url]:
        return typing.cast(dict[str, git_url], getattr(all_lib_list, f"git_lib_list_{config.git_remote}"))


class configure(common.basic_configure):
    glibc_version: str | None  # glibc版本号
    clone_type: git_clone_type  # 是否使用部分克隆
    shallow_clone_depth: int  # 浅克隆深度
    git_use_ssh: bool  # 使用ssh克隆git托管的代码
    extra_lib_list: list[str]  # 其他非git托管包
    network_try_times: int  # 进行网络操作时重试的次数
    git_remote: git_prefer_remote

    def __init__(
        self,
        glibc_version: str | None = get_current_glib_version(),
        clone_type: str = git_clone_type.partial,
        depth: int = 1,
        ssh: bool = False,
        extra_libs: list[str] | None = None,
        retry: int = 5,
        remote: str = git_prefer_remote.github,
    ) -> None:
        self.glibc_version = glibc_version
        self.clone_type = git_clone_type[clone_type]
        self.shallow_clone_depth = depth
        self.git_use_ssh = ssh
        self.extra_lib_list = [*all_lib_list.necessary_extra_lib_list, *(extra_libs or [])]
        self.network_try_times = retry + 1
        self.git_remote = git_prefer_remote[remote]

    def check(self) -> None:
        common._check_home(self.home)
        assert self.glibc_version, f"Invalid glibc version: {self.glibc_version}"
        assert self.shallow_clone_depth > 0, f"Invalid shallow clone depth: {self.shallow_clone_depth}."
        assert self.network_try_times >= 1, f"Invalid network try times: {self.network_try_times}."


class after_download_list:
    @staticmethod
    def expat(config: configure) -> None:
        _ = common.chdir_guard(os.path.join(config.home, "expat", "expat"))
        common.run_command("./buildconf.sh")

    @staticmethod
    def pexports(config: configure) -> None:
        _ = common.chdir_guard(os.path.join(config.home, "pexports"))
        common.run_command("autoreconf -if")

    @staticmethod
    def python_embed(config: configure) -> None:
        python_version = extra_lib_version.python
        python_embed_zip = os.path.join(config.home, "python-embed.zip")
        python_source_txz = os.path.join(config.home, "python_source.tar.xz")
        python_source = os.path.join(config.home, "python_source")
        python_embed = os.path.join(config.home, "python-embed")
        # 删除已安装包
        common.remove_if_exists(python_embed)

        # 解压embed包
        common.run_command(f"unzip -o {python_embed_zip}  python3*.dll python3*.zip *._pth -d {python_embed} -x python3.dll")
        common.remove(python_embed_zip)
        # 解压源代码包
        common.run_command(f"tar -xaf {python_source_txz}")
        common.rename(f"Python-{python_version}", python_source)
        common.remove(python_source_txz)

        # 复制头文件
        include_dir: str = os.path.join(python_embed, "include")
        common.copy(os.path.join(python_source, "Include"), include_dir)
        common.copy(os.path.join(python_source, "PC", "pyconfig.h.in"), os.path.join(include_dir, "pyconfig.h"))
        common.remove(python_source)

        # 记录python版本号
        python_version.save_version(python_embed)

    @staticmethod
    def loongnix(config: configure) -> None:
        linux_tgz = os.path.join(config.home, "linux-loongnix.tar.gz")
        glibc_tgz = os.path.join(config.home, "glibc-loongnix.tar.gz")
        linux_dir = os.path.join(config.home, "linux-loongnix")
        glibc_dir = os.path.join(config.home, "glibc-loongnix")
        # 删除已安装包
        common.remove_if_exists(linux_dir)
        common.remove_if_exists(glibc_dir)
        # 解压linux
        common.mkdir(linux_dir)
        common.run_command(f"tar -xaf {linux_tgz} -C {linux_dir}")
        common.remove(linux_tgz)
        # 解压glibc
        common.run_command(f"tar -xaf {glibc_tgz} -C {config.home}")
        common.rename(os.path.join(config.home, "glibc-2.28"), glibc_dir)
        common.remove(glibc_tgz)
        extra_lib_version.loongnix.save_version(linux_dir)

    @staticmethod
    def iconv(config: configure) -> None:
        iconv_version = extra_lib_version.iconv
        gdb_dir = os.path.join(config.home, "binutils", "gdb")
        iconv_tgz = os.path.join(config.home, "iconv.tar.gz")
        iconv_dir = os.path.join(gdb_dir, "libiconv")
        # 删除已安装包
        common.remove_if_exists(iconv_dir)
        common.run_command(f"tar -xaf {iconv_tgz} -C {gdb_dir}")
        common.rename(os.path.join(gdb_dir, f"libiconv-{iconv_version}"), iconv_dir)
        common.remove(iconv_tgz)
        iconv_version.save_version(iconv_dir)

    @staticmethod
    def gmp(config: configure) -> None:
        gmp_version = extra_lib_version.gmp
        gmp_dir = os.path.join(config.home, "gmp")
        gmp_txz = os.path.join(config.home, "gmp.tar.xz")
        # 删除已安装包
        common.remove_if_exists(gmp_dir)
        common.run_command(f"tar -xaf {gmp_txz} -C {config.home}")
        common.rename(os.path.join(config.home, f"gmp-{gmp_version}"), gmp_dir)
        common.remove(gmp_txz)
        gmp_version.save_version(gmp_dir)

    @staticmethod
    def mpfr(config: configure) -> None:
        mpfr_version = extra_lib_version.mpfr
        mpfr_dir = os.path.join(config.home, "mpfr")
        mpfr_txz = os.path.join(config.home, "mpfr.tar.xz")
        # 删除已安装包
        common.remove_if_exists(mpfr_dir)
        common.run_command(f"tar -xaf {mpfr_txz} -C {config.home}")
        common.rename(os.path.join(config.home, f"mpfr-{mpfr_version}"), mpfr_dir)
        common.remove(mpfr_txz)
        mpfr_version.save_version(mpfr_dir)

    @staticmethod
    def after_download_specific_lib(config: configure, lib: str) -> None:
        lib = lib.replace("-", "_")
        if lib in vars(after_download_list) and not common.command_dry_run.get():
            getattr(after_download_list, lib)(config)


class extra_git_options_list:
    @staticmethod
    def glibc(config: configure) -> list[str]:
        return [f"-b release/{config.glibc_version}/master"]

    @staticmethod
    def get_option(config: configure, lib: str) -> list[str]:
        if lib in vars(extra_git_options_list) and not common.command_dry_run.get():
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
