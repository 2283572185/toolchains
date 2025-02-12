# GCC15工具链

## 平台

| build            | host               | target             |
| :--------------- | :----------------- | :----------------- |
| x86_64-linux-gnu | x86_64-w64-mingw32 | x86_64-w64-mingw32 |

## 版本

- GCC：15.0.0
- GDB：16.0.50
- Binutils：2.42.50
- Mingw-w64：10.0.0
- PExports：0.47

## 组件

- gcc
- g++
- binutils
- gdb (需要Python3.13.2)
- Python3.13.2 embed package
- .gdbinit (位于share下)
- pexports
- 调试符号：libgcc libstdc++ libatomic libquadmath

## 注意事项

将下列文件夹添加到PATH环境变量：

- bin
- lib
- lib32
