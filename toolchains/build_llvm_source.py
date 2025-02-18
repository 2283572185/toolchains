import typing

from . import common
from .build_gcc_source import support_platform_list as gcc_support_platform_list
from .llvm_environment import environment


class modifier_list:
    """针对特定平台修改llvm构建环境的回调函数"""

    @staticmethod
    def modify(env: environment, target: str) -> None:
        target = target.replace("-", "_")
        if modifier := getattr(modifier_list, target, None):
            modifier(env)


def generate_target_list_from_gcc() -> tuple[list[str], list[str]]:
    """从gcc目标列表中获取目标

    Returns:
        tuple[list[str], list[str]]: (宿主平台列表, 独立平台列表)
    """

    phony_triplet = "phony-phony-phony"
    hosted_list: list[str] = []
    freestanding_list: list[str] = []

    for target in gcc_support_platform_list.target_list:
        toolchain_type = common.toolchain_type.classify_toolchain(phony_triplet, phony_triplet, target)
        if toolchain_type.contain(common.toolchain_type.freestanding):
            hosted_list.append(target)
        else:
            freestanding_list.append(target)

    return hosted_list, freestanding_list


class support_platform_list:
    """受支持的平台列表

    Attributes:
        host_list  : 支持的LLVM工具链宿主平台
        arch_list: 支持的LLVM目标平台
        project_list: 支持的子项目
        runtime_list: 支持的运行时库
        hosted_list: gcc支持的宿主平台
        freestanding_list: gcc支持的独立平台
        target_list: 支持的runtimes的target列表
    """

    host_list: typing.Final[list[str]] = gcc_support_platform_list.host_list
    arch_list: typing.Final[list[str]] = ["X86", "AArch64", "RISCV", "ARM", "LoongArch", "Mips"]
    project_list: typing.Final[list[str]] = ["clang", "clang-tools-extra", "lld", "lldb"]
    runtime_list: typing.Final[list[str]] = ["libcxx", "libcxxabi", "libunwind", "compiler-rt", "openmp"]
    hosted_list, freestanding_list = generate_target_list_from_gcc()
    target_list: typing.Final[list[str]] = [*hosted_list, "armv6m-none-eabi"]


class configure(common.basic_build_configure):
    """llvm构建配置"""

    toolchain_type: str = "LLVM"

    def __init__(
        self,
    ) -> None:
        """设置llvm构建配置

        Args:

        """

        super().__init__()


__all__ = ["modifier_list", "support_platform_list", "configure", "environment"]
