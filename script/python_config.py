#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import enum
import os

assert __name__ == "__main__", "Run this file directly instead of importing it as a module."
assert (
    "PYTHON_EMBED_PACKAGE" in os.environ
), "Must set the environment variable PYTHON_EMBED_PACKAGE to the path of the python embed package."
python_dir = os.environ["PYTHON_EMBED_PACKAGE"]
assert os.path.exists(python_dir), f"The path {python_dir} does not exist."


class flag_list(enum.StrEnum):
    includes = f"-I{os.path.join(python_dir, 'include')}"
    ldflags = f"-L{python_dir} -lpython"
    exec_prefix = f"-L{python_dir}"


parse = argparse.ArgumentParser(
    description="Get the configure of python embed package when build GDB with python support for MinGW platform."
)
for flag in flag_list:
    name = flag.name
    parse.add_argument(
        f"--{name.replace('_', '-')}", action="store_true", help=f"The {name.replace('_', ' ')} of the python embed package."
    )
args: argparse.Namespace = parse.parse_args()
for flag in flag_list:
    if getattr(args, flag.name, None):
        print(flag)
