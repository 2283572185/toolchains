# GCC和LLVM工具链

## 工具链

本项目提供开发版的GCC和LLVM工具链。它们具有如下特征：

- 带有Python支持的GDB
- 带有Python支持的libstdc++
- 支持pretty-printer的.gdbinit
- 使用相对路径，可重新部署
- 已配置rpath并带有必要的动态库
- 支持调试符号

支持如下工具链：

| 工具链 | Host               | Target                              |
| :----- | :----------------- | :---------------------------------- |
| gcc    | x86_64-linux-gnu   | x86_64-linux-gnu                    |
| gcc    | x86_64-linux-gnu   | i686-linux-gnu                      |
| gcc    | x86_64-linux-gnu   | x86_64-w64-mingw32                  |
| gcc    | x86_64-linux-gnu   | i686-w64-mingw32                    |
| gcc    | x86_64-linux-gnu   | arm-none-eabi                       |
| gcc    | x86_64-linux-gnu   | x86_64-elf                          |
| gcc    | x86_64-linux-gnu   | loongarch64-linux-gnu               |
| gcc    | x86_64-linux-gnu   | loongarch64-loongnix-linux-gnu      |
| gcc    | x86_64-linux-gnu   | riscv64-linux-gnu                   |
| gcc    | x86_64-linux-gnu   | aarch64-linux-gnu                   |
| gcc    | x86_64-linux-gnu   | arm-linux-gnueabi                   |
| gcc    | x86_64-linux-gnu   | arm-linux-gnueabihf                 |
| gcc    | x86_64-linux-gnu   | mips64el-linux-gnuabi64             |
| gcc    | x86_64-w64-mingw32 | x86_64-w64-mingw32                  |
| gcc    | x86_64-w64-mingw32 | i686-w64-mingw32                    |
| gcc    | x86_64-w64-mingw32 | x86_64-linux-gnu                    |
| gcc    | x86_64-w64-mingw32 | i686-linux-gnu                      |
| gcc    | x86_64-w64-mingw32 | arm-none-eabi                       |
| gcc    | x86_64-w64-mingw32 | x86_64-elf                          |
| gcc    | x86_64-w64-mingw32 | loongarch64-linux-gnu               |
| gcc    | x86_64-w64-mingw32 | loongarch64-loongnix-linux-gnu      |
| gcc    | x86_64-w64-mingw32 | riscv64-linux-gnu                   |
| gcc    | x86_64-w64-mingw32 | aarch64-linux-gnu                   |
| gcc    | x86_64-w64-mingw32 | arm-linux-gnueabi                   |
| gcc    | x86_64-w64-mingw32 | arm-linux-gnueabihf                 |
| gcc    | x86_64-w64-mingw32 | mips64el-linux-gnuabi64             |
| llvm   | x86_64-linux-gnu   | X86, ARM, AArch64, LoongArch, RISCV |
| llvm   | x86_64-w64-mingw32 | X86, ARM, AArch64, LoongArch, RISCV |

## 构建流程说明与构建脚本

### 构建流程说明

本项目提供GCC和LLVM工具链的构建流程说明，可以参阅下表中的文件了解工具链构建流程。

| 文件          | 说明                   |
| :------------ | :--------------------- |
| build_gcc.md  | GCC工具链构建流程说明  |
| build_llvm.md | LLVM工具链构建流程说明 |

### 构建脚本

本项目在`script`目录下也提供了一组Python脚本用于自动化构建工具链，下表是相关文件说明：

| 文件                                  | 说明                                                                            |
| :------------------------------------ | :------------------------------------------------------------------------------ |
| prefix-lib.suffix $^{[1]}$            | 链接器脚本，用于代替autotools生成的带有绝对路径的链接器脚本以得到可移植的工具链 |
| .gdbinit                              | gdb配置文件，用于自动配置pretty-print                                           |
| auto_gcc.py                           | gcc构建脚本的接口，可以获取各种信息和实现全自动构建 $^{[2]}$                    |
| common.py                             | GCC和LLVM构建脚本共用的一些构建环境和实用函数                                   |
| gcc_environment.py                    | GCC构建环境，所有GCC构建脚本均通过该环境完成构建流程                            |
| llvm_environment.py                   | LLVM构建环境，所有LLVM构建脚本均通过该环境完成构建流程                          |
| python_config.py                      | 在交叉编译gdb时用于获取Python库所在路径                                         |
| python_config.sh                      | 将Python脚本包装为sh脚本，因为binutils-gdb的configure脚本仅支持sh脚本           |
| sysroot.py                            | 制作构建LLVM工具链所需的初始sysroot，仅包含libc和GNU相关库文件                  |
| plat_clang.py $^{[3]}$                | LLVM工具链构建脚本 $^{[4]}$                                                     |
| plat_native_gcc.py $^{[3]}$           | GCC本地工具链/加拿大工具链构建脚本 $^{[4]}$                                     |
| plat_host_plat_target_gcc.py $^{[3]}$ | GCC交叉工具链/加拿大交叉工具链构建脚本 $^{[4]}$                                 |
| download.py $^{[5]}$                  | 自动从github和其他源下载构建GCC和LLVM所需的包                                   |

注释：

[1] 字段说明如下表所示：

| 字段   | 说明                                                                                                  |
| :----- | :---------------------------------------------------------------------------------------------------- |
| prefix | 一般为arch，若存在多个target则会增加vendor字段（如`loongnix`）或abi字段（如`hf`），取决于target间差异 |
| lib    | glibc中库名称，如`libc`和`libm`，取决于哪些库使用了链接器脚本而非软链接                               |
| suffix | glibc中库文件名后缀，如`.so`和`.a`，取决于哪些类型的库使用了链接器脚本而非软链接                      |

[2] 该脚本支持如下选项：

| 选项        | 说明                                                                     |
| :---------- | :----------------------------------------------------------------------- |
| --build     | 全自动构建所有GCC工具链                                                  |
| --dump_info | 打印所有构建脚本、目标和构建顺序信息                                     |
| --dump_path | 以shell脚本形式打印所有存在的工具链的bin目录列表，可用于设置PATH环境变量 |
| --help      | 打印帮助信息                                                             |
| 作为库包含  | 可以通过`scripts`对象获取构建脚本、目标和已安装工具链相关信息            |

[3] plat字段表示一个triplet，用于描述一个目标平台，如`x86_6-linux-gnu`

[4] 构建脚本可作为库使用，也可直接执行。引用这些脚本可以获取工具链的构建环境和一些实用函数，直接执行可以完成自动化构建

[5] 该脚本支持如下选项：

| 选项            | 说明                                                                   |
| :-------------- | :--------------------------------------------------------------------- |
| --glibc_version | 设置目标平台的Glibc版本，默认为系统Glibc版本                           |
| --home          | 设置源码树的根目录，默认为`$HOME`                                      |
| --clone_type    | Git克隆类型，默认为部分克隆                                            |
| --depth         | 使用Git进行浅克隆时的克隆深度，默认为1                                 |
| --ssh           | 是否在从github克隆时使用SSH，默认为否                                  |
| --extra_libs    | 要下载或更新的额外包                                                   |
| --retry         | 网络操作失败时最大重试次数，默认为5次                                  |
| --remote        | 设置首选git源，在源可用时使用源以加速克隆，默认为github                |
| --update        | 更新已安装的包，要求所有包均已安装                                     |
| --download      | 下载缺失的包，不会更新已安装的包                                       |
| --auto          | 先下载缺失的包，然后更新已安装的包。由于二次检查，可能会需要更多时间。 |
| --system        | 打印需要的系统包                                                       |
| --remove        | 删除已经安装的包，不指定包名则删除所有安装的包                         |
| --import        | 从文件中导入配置                                                       |
| --export        | 将配置导出到文件                                                       |
| --help          | 打印帮助信息                                                           |

remote选项支持的git源如下：

| 源     | 说明                                                                           |
| :----- | :----------------------------------------------------------------------------- |
| github | 默认远程源，部分为仓库镜像，支持ssh克隆                                        |
| native | 各个git库的原生远程源，可以克隆最新的提交，但可能访问较慢，部分仓库使用git协议 |
| nju    | 南京大学开源镜像站，包含gcc、binutils、linux、glibc、llvm仓库镜像              |
| tuna   | 清华大学开源软件镜像站，镜像同上                                               |
| bfsu   | 北京外国语大学开源软件镜像站，镜像同上                                         |
| nyist  | 南阳理工学院开源软件镜像站，镜像同上                                           |
| cernet | 校园网联合镜像站，mirrorz-302 智能选择，镜像同上                               |

### 工具链说明

在`readme`目录下可以找到各个工具链的说明文件，构建脚本会将说明文件和工具链一同打包。在使用工具链前请参阅工具链目录下的`README.md`文件，
或参阅[构建流程说明](#构建流程说明)。

## Xmake支持

本项目为[受支持的工具链](#工具链)提供了xmake支持，下面是一个示例：

```lua
-- 导入所有文件
includes("xmake/*.lua")
-- 设置允许的xmake模式
set_allowedmodes(support_rules_table)
-- 根据mode选项添加规则
add_rules(get_config("mode"))
target("test")
    add_files("*.cpp")
target_end()
```

通过`toolchain`选项可以轻松地选取要使用的工具链，并完成`--sysroot`等选项的配置，下面是一个示例：

```shell
# 使用clang进行交叉编译
xmake f --toolchain=aarch64-linux-gnu-clang -a arm64-v8a -p linux
# 使用gcc进行交叉编译
xmake f --toolchain=aarch64-linux-gnu-gcc -a arm64-v8a -p linux
```

xmake支持也提供了`target-clang`和`target-gcc`工具链。使用这两个工具链时脚本会尝试根据`plat`和`arch`推导出目标平台，若无法推导则配置失败，此时应该指定一个具体的工具链。
在常用平台上编译时可以直接使用这两个工具链，而无需在xmake选项和工具链间重复指定目标平台。下面是一个示例：

```shell
# 根据arch和plat自动推导工具链，相当于--toolchain=aarch64-linux-gnu-clang
xmake f --toolchain=target-clang -a arm64-v8a -p linux
```

如果使用`cross`平台，则需要通过`--target_os`选项指定目标平台。下面是一个示例：

```shell
# 相当于--toolchain=loongarch64-linux-gnu-clang
xmake f --toolchain=target-clang -a loong64 -p cross --target_os=linux
```

使用`cross`平台并且不指定`--target_os`选项则会推导出独立工具链，下面是一个示例：

```shell
# 推导出独立工具链，相当于--toolchain=arm-none-eabi
xmake f --toolchain=target-clang -a arm -p cross
```

### xmake文件说明

xmake支持文件位于`xmake`文件夹下，下面是各个文件的说明：

| 文件                | 说明                                                            |
| :------------------ | :-------------------------------------------------------------- |
| option.lua          | 提供各种xmake配置选项，包含`utility/utility.lua`文件            |
| rule.lua            | 提供4种常用xmake规则，包含`option.lua`文件                      |
| toolchain.lua       | 提供各种xmake工具链，包含`option.lua`和`utility/target.lua`文件 |
| utility/target.lua  | 受支持的目标平台表，内部文件                                    |
| utility/utility.lua | 提供各种配置工具，内部文件                                      |

其中`option.lua`可以单独使用，此时需要使用`add_options`来关联选项和目标。如果使用`toolchain.lua`中定义的工具链，这些选项会自动添加到相应工具链中。
`utility/target.lua`可以通过`includes`函数引入到描述域中，此时函数和变量均可使用；也可以通过`import`函数引入脚本域，此时仅函数接口可用。

### xmake选项说明

下面是`option.lua`提供的xmake配置选项说明：

- march 设置工具链的`-march`选项，默认为`default`

   | 选项   | 说明                                                      |
   | :----- | :-------------------------------------------------------- |
   | no     | 不添加`-march`选项                                        |
   | detect | 如果可以则添加`-march=native`选项，否则不添加`-march`选项 |
   | arch   | 添加`-march=arch`选项，`arch`不能为`no`和`detect`         |

- sysroot 设置工具链的`--sysroot`选项，默认为`detect`

    | 选项   | 说明                                                                         |
    | :----- | :--------------------------------------------------------------------------- |
    | no     | 不添加`--sysroot`选项                                                        |
    | detect | 工具链为clang则自动探测sysroot，为gcc则不添加选项 $^*$                       |
    | path   | 添加`--sysroot=path`选项，`path`可以是绝对路径或不为`no`和`detect`的相对路径 |

    *：关于自动探测支持请参阅[sysroot说明](readme/sysroot.md#说明)。

- rtlib 设置clang的`-rtlib`选项，默认为`default`

    | 选项        | 说明                                                |
    | :---------- | :-------------------------------------------------- |
    | default     | 不添加`-rtlib`选项，即使用构建clang时指定的默认选项 |
    | libgcc      | 添加`-rtlib=libgcc`，指定使用`libgcc`               |
    | compiler-rt | 添加`-rtlib=compiler-rt`，指定使用`compiler-rt`     |
    | platform    | 添加`-rtlib=platform`，即使用目标平台的默认选项     |

- unwindlib 设置clang的`-unwindlib`选项，默认为`default`

    | 选项            | 说明                                                      |
    | :-------------- | :-------------------------------------------------------- |
    | default         | 不添加`-unwind`选项，即使用构建clang时指定的默认选项      |
    | libgcc          | 添加`-unwind=libgcc`，指定使用`libgcc` $^*$               |
    | libunwind       | 添加`-unwind=libunwind`，指定使用`libunwind` $^*$         |
    | platform        | 添加`-unwind=platform`，即使用目标平台的默认选项 $^*$     |
    | force_libgcc    | 强制添加`-unwind=libgcc`，指定使用`libgcc` $^*$           |
    | force_libunwind | 强制添加`-unwind=libunwind`，指定使用`libunwind` $^*$     |
    | force_platform  | 强制添加`-unwind=platform`，即使用目标平台的默认选项 $^*$ |

    *：为避免`argument unused`警告，默认情况下仅在`rtlib`选项为`compiler-rt`时添加该选项，可以使用force版本强制添加

- debug_strip 设置在启用调试符号的规则中是否要剥离符号表，默认为`no`

    | 选项  | 说明                                                   |
    | :---- | :----------------------------------------------------- |
    | no    | 如果可能，不剥离任何符号                               |
    | debug | 剥离调试符号到独立符号文件                             |
    | all   | 剥离调试符号到独立符号文件，然后去除目标文件中所有符号 |

- enable_lto 设置在具有发布属性的规则（如`release`，`minsizerel`和`releasedbg`）中是否启用链接时优化（LTO），默认为`true`

    | 选项  | 说明    |
    | :---- | :------ |
    | true  | 启用LTO |
    | false | 禁用LTO |

    该选项在编译器与链接器不匹配时特别有用，因为此时需要禁用LTO才能正常完成构建流程。例如使用`clang`进行编译而使用`ld.bfd`进行链接，此时若启用LTO则会提示无法识别文件格式。
    通常，`clang`使用`lld`进行链接，但如果`lld`不支持目标平台，则可能发生上述情况。使用该选项可以方便地根据需求设置或禁用LTO。

### xmake工具链说明

可以使用`xmake show -l toolchains`命令查看所有受支持的工具链名称，具体工具链的信息可以参阅[受支持的工具链](#工具链)。
工具链的命名规则和说明如下：

| 名称        | 说明                                                                                    |
| :---------- | :-------------------------------------------------------------------------------------- |
| native-tool | 本地工具链，对于clang不会添加`--target`选项，对于gcc会查找`gcc`工具                     |
| target-tool | 根据xmake的`arch`和`plat`选项自动推导出目标平台工具链                                   |
| plat-tool   | 目标平台为plat的工具链，对于clang会添加`--target=plat`选项，对于gcc会查找`plat-gcc`工具 |

注解：`tool`表示工具链类型，为`clang`或`gcc`

xmake工具链还会根据目标平台的特性添加一些选项，如为`loongarch64-loongnix-linux-gnu`平台添加`-Wl,-dynamic-linker=/lib64/ld.so.1`选项以修改动态库加载器路径。
