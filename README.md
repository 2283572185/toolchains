# GCC和LLVM工具链

该仓库提供开发版的GCC和LLVM工具链。它们具有如下特征：
- 带有Python支持的GDB
- 带有Python支持的libstdc++
- 支持pretty-printer的.gdbinit
- 使用相对路径，可重新部署
- 已配置rpath并带有必要的动态库

支持如下工具链：
| 工具链 | 宿主               | 目标                                      |
| ------ | ------------------ | ----------------------------------------- |
| gcc    | x86_64-linux-gnu   | x86_64-linux-gnu                          |
| gcc    | x86_64-linux-gnu   | x86_64-w64-mingw32                        |
| gcc    | x86_64-w64-mingw32 | x86_64-w64-mingw32                        |
| llvm   | x86_64-linux-gnu   | X86, ARM, AArch64, LoongArch, WebAssembly |
| llvm   | x86_64-w64-mingw32 | X86, ARM, AArch64, LoongArch, WebAssembly |