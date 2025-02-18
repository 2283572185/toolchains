# 测试能否在脚本中再次加载模块
from need_import import *

def foo(i:int) -> int:
    """返回输入的整数，用于测试动态导入功能

    Args:
        i (int): 输入整数

    Returns:
        int: 输入整数
    """

    return i
