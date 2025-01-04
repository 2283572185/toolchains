#!/usr/bin/python3
# -*- coding: utf-8 -*-
import llvm_environment as llvm
from sysroot import auto_build_sysroot

# 确保sysroot存在
auto_build_sysroot()
env = llvm.environment()


def build(stage: int = env.stage) -> None:
    env.stage = stage
    # loongarch64-loongnix-linux-gnu过于老旧，编译相关库时出错
    system_list = [i for i in filter(lambda x: x != "loongarch64-loongnix-linux-gnu", env.system_list.keys())]
    if env.stage == 1:
        basic_command = ("-stdlib=libstdc++", "-unwindlib=libgcc", "-rtlib=libgcc") if not env.bootstrap else ()
        env.config("llvm", env.host, *basic_command, **{**env.dylib_option_list, **env.llvm_option_list_1})
        env.make("llvm")
        env.install("llvm")
        env.remove_build_dir("llvm")
        for target in system_list:
            basic_command = ()
            option = env.llvm_option_list_1
            match target:
                case "x86_64-w64-mingw32" | "i686-w64-mingw32":
                    option = env.llvm_option_list_w32_1
                case "arm-linux-gnueabi" | "arm-linux-gnueabihf":
                    # 编译compiler-rt需要armv6+
                    basic_command = ("-march=armv6",)
            env.config("runtimes", target, *basic_command, **option)
            env.make("runtimes")
            env.install("runtimes")
            env.build_sysroot(target)
            env.remove_build_dir("runtimes")
        if not env.bootstrap:
            # 再编译一遍库以便让运行时不依赖gnu相关库
            env.stage = 3
        else:
            env.stage += 1

    basic_command = ("-stdlib=libc++", "-unwindlib=libunwind", "-rtlib=compiler-rt")
    if env.stage == 2:
        env.config("llvm", env.host, *basic_command, **{**env.dylib_option_list, **env.llvm_option_list_2})
        env.make("llvm")
        env.install("llvm")
        env.copy_llvm_libs()
        env.stage += 1

    if env.stage == 3:
        for target in ["i686-w64-mingw32", "loongarch64-linux-gnu", "x86_64-w64-mingw32", "x86_64-linux-gnu", "riscv64-linux-gnu"]:
            option = env.llvm_option_list_3
            basic_command = ("-stdlib=libc++", "-unwindlib=libunwind", "-rtlib=compiler-rt")
            match target:
                case "x86_64-w64-mingw32":
                    option = env.llvm_option_list_w32_3
                case "i686-w64-mingw32":
                    option = env.llvm_option_list_w32_3
                    basic_command = (*basic_command, "-lgcc")
                case "arm-linux-gnueabi" | "arm-linux-gnueabihf":
                    basic_command = (*basic_command, "-march=armv6")
            env.config("runtimes", target, *basic_command, **option)
            env.make("runtimes")
            env.install("runtimes")
            env.build_sysroot(target)
            env.remove_build_dir("runtimes")
        env.stage += 1

    if env.stage == 4:
        env.change_name()
        env.package()


if __name__ == "__main__":
    build()
