#!/usr/bin/python3
# -*- coding: utf-8 -*-
import llvm_environment as llvm

env = llvm.environment(host="x86_64-w64-mingw32")


def build(_: int = env.stage) -> None:
    assert not env.bootstrap, "Cannot bootstrap a canadian toolchain since it runs on a different machine."
    env.stage = 1
    basic_command = ("-stdlib=libc++", "-unwindlib=libunwind", "-rtlib=compiler-rt")
    for lib in llvm.lib_list:
        command = (*basic_command, "-lws2_32", "-lbcrypt")
        env.config(lib, env.host, *command, **env.lib_option)
        env.make(lib)
        env.install(lib)

    env.config("llvm", env.host, *basic_command, **{**env.dylib_option_list, **env.llvm_option_list_1, **env.llvm_cross_option})
    env.make("llvm")
    env.install("llvm")
    env.copy_llvm_libs()
    env.remove_build_dir("llvm")
    env.package()


if __name__ == "__main__":
    build()
