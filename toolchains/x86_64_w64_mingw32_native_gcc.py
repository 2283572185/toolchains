#!/usr/bin/python3
# -*- coding: utf-8 -*-
import gcc_environment as gcc
import os
import shutil

env = gcc.environment(host="x86_64-w64-mingw32")
lib_install_dir_list: dict[str, str] = {}
for lib in ("gmp", "expat", "iconv", "mpfr"):
    lib_install_dir_list[lib] = os.path.join(env.home, lib, "install")


def copy_lib(env: gcc.environment = env) -> None:
    """从x86_64-w64-mingw32交叉工具链中复制运行库"""
    cross_toolchain = gcc.environment(target="x86_64-w64-mingw32")
    for dll in ("libstdc++-6.dll", "libgcc_s_seh-1.dll"):
        shutil.copy(os.path.join(cross_toolchain.lib_prefix, "lib", dll), env.bin_dir)


def build_gdb_requirements(env: gcc.environment = env) -> list[str]:
    """编译安装libgmp, libexpat, libiconv, libmpfr

    Returns:
        list[str]: gdb依赖库相关的配置选项
    """
    lib_option = f"--host={env.host} --disable-shared"
    for lib, prefix in lib_install_dir_list.items():
        env.enter_build_dir(lib)
        env.configure(
            lib_option,
            f"--prefix={prefix}",
            f"--with-gmp={lib_install_dir_list['gmp']}" if lib == "mpfr" else "",
        )
        env.make()
        env.install()

    lib_option = ["--with-expat"]
    for lib in ("gmp", "mpfr"):
        lib_option.append(f"--with-{lib}={lib_install_dir_list[lib]}")
    for lib in ("expat", "iconv"):
        lib_option.append(f"--with-lib{lib}-prefix={lib_install_dir_list[lib]}")
    return lib_option


def build():
    # 更新源代码
    # env.update()

    basic_option = f"--disable-werror --prefix={env.prefix} --host={env.host} --target={env.target}"
    gcc_option = "--enable-multilib --enable-languages=c,c++ --disable-sjlj-exceptions --enable-threads=win32"
    binutils_option = f"--with-system-gdbinit={env.gdbinit_path} --with-python={env.python_config_path} CXXFLAGS=-D_WIN32_WINNT=0x0600"

    # 编译安装完整gcc
    env.enter_build_dir("gcc")
    env.configure(basic_option, gcc_option)
    env.make()
    # 调试库将从交叉工具链中复制，不需要单独安装
    env.install("install-strip")

    # 删除已安装的dll
    for file in filter(lambda x: x.endswith(".dll"), os.listdir(env.bin_dir)):
        gcc.remove(os.path.join(env.bin_dir, file))

    # 创建libpython.a
    env.build_libpython()
    # 编译安装libgmp, libexpat, libiconv, libmpfr
    lib_option = build_gdb_requirements()

    # 编译安装binutils和gdb
    env.enter_build_dir("binutils")
    env.configure(basic_option, *lib_option, binutils_option)
    env.make()
    env.install()

    # 复制gdb所需运行库
    copy_lib()
    # 复制文件
    env.copy_from_cross_toolchain()

    # 编译安装pexports
    env.enter_build_dir("pexports")
    env.configure(f"--prefix={env.prefix} --host={env.host}")
    env.make()
    env.install()

    # 打包工具链
    env.package(need_python_embed_package=True)


if __name__ == "__main__":
    build()
