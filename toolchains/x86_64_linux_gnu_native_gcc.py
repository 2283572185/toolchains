#!/usr/bin/python3
# -*- coding: utf-8 -*-
import gcc_environment as gcc

env = gcc.environment()


def build() -> None:
    # 更新源代码
    # env.update()

    basic_option = f"--disable-werror --enable-nls --prefix={env.prefix}"
    # 编译gcc
    env.enter_build_dir("gcc")
    env.configure(basic_option, "--disable-bootstrap --enable-multilib --enable-languages=c,c++")
    env.make()
    env.install()
    env.strip_debug_symbol()
    # 第一次编译时需要注册环境变量，运行完该脚本后可以source ~/.bashrc来加载环境变量
    # env.register_in_bashrc()

    # 编译binutils
    env.enter_build_dir("binutils")
    env.configure(basic_option, f"--with-system-gdbinit={env.gdbinit_path} LDFLAGS={env.rpath_option} --enable-gold")
    env.make()
    env.install()

    # 打包工具链
    env.package()


if __name__ == "__main__":
    build()
