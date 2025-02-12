# GCC15工具链

## 平台

| build            | host             | target           |
| :--------------- | :--------------- | :--------------- |
| x86_64-linux-gnu | x86_64-linux-gnu | x86_64-linux-gnu |

## 版本

- GCC：15.0.0
- GDB：16.0.50
- Binutils：2.42.50

## 组件

- gcc
- g++
- binutils
- gdb (需要python3.13.2)
- .gdbinit (位于share下)
- 调试符号：libgcc libstdc++ libatomic libquadmath libgomp

## 注意事项

若出现类似```shell /lib/x86_64-linux-gnu/libstdc++.so.6: version 'CXXABI_1.3.15' not found```的提示，可将`lib64/libstdc++.so.6.0.33`复制到系统目录，
并重新链接`/lib/x86_64-linux-gnu/libstdc++.so.6`到`libstdc++.so.6.0.33`，其他库同理。同时，只有链接到该工具链带的动态库才能使用调试符号。

没有打包python3.13.2,需要自行通过包管理器安装。
