#!/usr/bin/env sh
# 获取脚本的目录部分
script_dir=$(dirname "$0")
# 转换为绝对路径
script_dir=$(cd "$script_dir" && pwd)
/usr/bin/env python3 "$script_dir/python_config.py" $@
