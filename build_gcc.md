# 构建GCC工具链

## 基本信息

| 项目        | 版本         |
| :---------- | :----------- |
| OS          | Ubuntu 24.10 |
| GCC         | 15.0.0       |
| GDB         | 17.0.50      |
| Binutils    | 2.44.50      |
| Python $^*$ | 3.13.2       |
| Linux       | 6.14-rc2     |
| Glibc       | 2.40         |
| Mingw-w64   | 12.0.0       |
| PExports    | 0.47         |
| Iconv       | 1.18         |
| Gmp         | 6.3.0        |
| Mpfr        | 4.2.1        |
| Expat       | 2.6.4        |

*: 在为Windows平台编译带有Python支持的GDB时需要下载Python包，Linux平台可以使用系统自带包

## 准备工作

### 1.安装系统包

```shell
sudo apt install bison flex texinfo make automake autoconf libtool git gcc g++ gcc-multilib g++-multilib python3 tar zstd unzip libgmp-dev libmpfr-dev zlib1g-dev libexpat1-dev gawk bzip2
```

### 2.下载源代码

```shell
git clone https://github.com/gcc-mirror/gcc.git --depth=1 gcc
git clone https://github.com/bminor/binutils-gdb.git --depth=1 binutils
git clone https://github.com/mirror/mingw-w64.git --depth=1 mingw
git clone https://github.com/libexpat/libexpat.git --depth=1 expat
cd  ~/expat/expat
./buildconf.sh
cd ~
git clone https://github.com/torvalds/linux.git --depth=1 linux
# glibc版本要与目标系统使用的版本对应
git clone https://github.com/bminor/glibc.git -b release/2.39/master --depth=1 glibc
git clone https://github.com/bocke/pexports.git --depth=1 pexports
cd ~/pexports
autoreconf -if
cd ~
# 编译Windows下带有Python支持的gdb需要嵌入式Python3环境
wget https://www.python.org/ftp/python/3.13.2/python-3.13.2-embed-amd64.zip -O python-embed.zip
unzip -o python-embed.zip  python3*.dll python3*.zip *._pth -d python-embed -x python3.dll
rm python-embed.zip
# 下载Python源代码以提取include目录
wget https://www.python.org/ftp/python/3.13.2/Python-3.13.2.tar.xz -O Python.tar.xz
tar -xaf Python.tar.xz
rm Python.tar.xz
cd Python-3.13.2/Include
mkdir ~/python-embed/include
cp -r * ~/python-embed/include
cd ../PC
cp pyconfig.h ~/python-embed/include
cd ~
rm -rf Python-3.13.2
wget https://ftp.gnu.org/pub/gnu/libiconv/libiconv-1.17.tar.gz -O iconv.tar.gz
tar -axf iconv.tar.gz
rm iconv.tar.gz
mv libiconv-1.17/ iconv
```

### 3.安装依赖库

```shell
cd ~/gcc
contrib/download_prerequisites
cp -rfL gmp mpfr ..
cd ~
```

## 构建gcc本地工具链

| build            | host             | target           |
| :--------------- | :--------------- | :--------------- |
| x86_64-linux-gnu | x86_64-linux-gnu | x86_64-linux-gnu |

### 4.编译安装gcc

```shell
export PREFIX=~/x86_64-linux-gnu-native-gcc15
cd ~/gcc
mkdir build
cd build
../configure --disable-werror --enable-multilib --enable-languages=c,c++ --disable-bootstrap --enable-nls --prefix=$PREFIX
make -j 20
make install-strip -j 20
# 单独安装带调试符号的库文件
make install-target-libgcc install-target-libstdc++-v3 install-target-libatomic install-target-libquadmath install-target-libgomp -j 20
echo "export PATH=$PREFIX/bin:"'$PATH' >> ~/.bashrc
source ~/.bashrc
```

参阅[gcc配置选项](https://gcc.gnu.org/install/configure.html)。

### 5.编译安装binutils和gdb

由于readline使用k&r c编写，即`int foo()`具有可变参数，使用新gcc编译会导致错误，因此需要对如下文件进行修改：

```c
// binutils/readline/readline/tcap.h

extern int tgetent (...);
extern int tgetflag (...);
extern int tgetnum (...);
extern char *tgetstr (...);

extern int tputs (...);

extern char *tgoto (...);
```

对gprofng需要进行如下修改：

```c
#include "hwcfuncs.h"

#ifdef __linux__
#define HWCFUNCS_SIGNAL         SIGIO
#define HWCFUNCS_SIGNAL_STRING  "SIGIO"
```

```shell
cd ~/binutils
mkdir build
cd build
export ORIGIN='$$ORIGIN'
../configure --prefix=$PREFIX --disable-werror --enable-nls --with-system-gdbinit=$PREFIX/share/.gdbinit LDFLAGS="-Wl,-rpath='$ORIGIN'/../lib64"
make -j 20
make install-strip -j 20
unset ORIGIN
```

`--with-system-gdbinit=$PREFIX/share/.gdbinit`选项是用于设置默认的.gdbinit，而我们可以在默认的.gdbinit中配置好pretty-printer模块，
这样就可以实现开箱即用的pretty-printer。参见[GDB系统设置](https://sourceware.org/gdb/current/onlinedocs/gdb.html/System_002dwide-configuration.html#System_002dwide-configuration)。

`export ORIGIN='$$ORIGIN'`和`LDFLAGS="-Wl,-rpath='$ORIGIN'/../lib64"`选项是用于设置gdb的rpath。由于编译时使用的gcc版本比系统自带的更高，故链接的libstdc++版本也更高。
因而需要将rpath设置到编译出来的libstdc++所在的目录。

### 6.创建.gdbinit

由`libstdc++.so.6.0.33-gdb.py`配置pretty-printer，完成后转至[第7步](#7修改libstdc的python支持)：

```python
# share/.gdbinit
python
import os
import gdb
import sys

# gdb启动时会将sys.path[0]设置为share/gdb/python
scriptPath = os.path.join(sys.path[0], "../../../lib64/libstdc++.so.6.0.33-gdb.py")
gdb.execute(f"source {scriptPath}")
end
```

由`share/.gdbinit`直接配置pretty-printer，完成后直接跳转至[第8步](#8剥离调试符号到独立符号文件)：

```python
# share/.gdbinit
python
import os
import gdb
import sys

# gdb启动时会将sys.path[0]设置为share/gdb/python
share_dir = os.path.abspath(os.path.join(sys.path[0], "../../"))
# 在share目录下搜索gcc的python支持
python_dir = ""
for dir in os.listdir(share_dir):
    current_dir = os.path.join(share_dir, dir, "python")
    if dir[0:3] == "gcc" and os.path.isdir(current_dir):
        python_dir = current_dir
        break
if python_dir != "":
    sys.path.insert(0, python_dir)
    from libstdcxx.v6 import register_libstdcxx_printers
    register_libstdcxx_printers(gdb.current_objfile())
else:
    print("Cannot find gcc python support because share/gcc*/python directory does not exist.")
end
```

### 7.修改libstdc++的python支持

```python
# lib64/libstdc++.so.6.0.33-gdb.py
import sys
import gdb
import os

current_dir = os.path.dirname(os.path.abspath(__file__))
# pretty-printer所需的python脚本位于share/gcc-15.0.0/python下
# 故使用哪个libstdc++.so.6.0.33-gdb.py都不影响结果，此处选择lib64下的
python_dir  = os.path.normpath(os.path.join(current_dir, "../share/gcc-15.0.0/python"))
if not python_dir in sys.path:
    sys.path.insert(0, python_dir)
# 注册pretty-printer
from libstdcxx.v6 import register_libstdcxx_printers
register_libstdcxx_printers(gdb.current_objfile())
```

同理，修改`lib32/libstdc++.so.6.0.33-gdb.py`，尽管在默认配置中该文件不会被加载。

### 8.剥离调试符号到独立符号文件

通过`make install-target`命令可以安装未strip的运行库，但这样的运行库体积过大，不利于部署。因此需要剥离调试符号到独立的符号文件中。

在[第4步](#4编译安装gcc)中我们保留了以下库的调试符号：libgcc libstdc++ libatomic libquadmath libgomp

接下来逐个完成剥离操作：

```shell
# 生成独立的调试符号文件
objcopy --only-keep-debug $PREFIX/lib64/libgcc_s.so.1 $PREFIX/lib64/libgcc_so.1.debug
# 剥离动态库的调试符号
strip $PREFIX/lib64/libgcc_s.so.1
# 关联调试符号和动态库
objcopy --add-gnu-debuglink=$PREFIX/lib64/libgcc_s.so.1.debug $PREFIX/lib64/libgcc_s.so.1
# 重复上述操作直到处理完所有动态库
```

### 9.打包工具链

```shell
cd $PREFIX/bin
# 值得注意的是，此时编译出来的gcc不包含cc，这会导致编译build的目标时一些依赖cc的工具报错
ln -s gcc cc
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export MEMORY=$(cat /proc/meminfo | awk '/MemTotal/ {printf "%dGiB\n", int($2/1024/1024)}')
tar -cf x86_64-linux-gnu-native-gcc15.tar x86_64-linux-gnu-native-gcc15/
xz -ev9 -T 0 --memlimit=$MEMORY x86_64-linux-gnu-native-gcc15.tar
```

## 构建mingw[交叉工具链](https://en.wikipedia.org/wiki/Cross_compiler)

| build            | host             | target             |
| :--------------- | :--------------- | :----------------- |
| x86_64-linux-gnu | x86_64-linux-gnu | x86_64-w64-mingw32 |

### 10.设置环境变量

```shell
export TARGET=x86_64-w64-mingw32
export HOST=x86_64-linux-gnu
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
```

### 11.编译安装binutils

```shell
cd binutils/build
rm -rf *
# Linux下不便于调试Windows,故不编译gdb
../configure --disable-werror --enable-nls --disable-gdb --prefix=$PREFIX --target=$TARGET
make -j 20
make install-strip -j 20
echo "export PATH=$PREFIX/bin:"'$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 12.安装mingw-w64头文件

```shell
cd ~/mingw
mkdir build
cd build
# 这是交叉编译器，故目标平台的头文件需要装在$TARGET目录下
../configure --prefix=$PREFIX/$TARGET --with-default-msvcrt=ucrt --host=$TARGET --without-crt
make install
```

### 13.编译安装gcc和libgcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --enable-multilib --enable-languages=c,c++ --enable-nls --disable-sjlj-exceptions --enable-threads=win32 --prefix=$PREFIX --target=$TARGET
make all-gcc all-target-libgcc -j 20
make install-strip-gcc install-strip-target-libgcc -j 20
```

遇到如下情况：

```log
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 dllcrt2.o: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -lmingwthrd: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -lmingw32: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -lmingwex: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -lmoldname: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -lmsvcrt: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -ladvapi32: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -lshell32: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -luser32: 没有那个文件或目录
/home/luo/x86_64-linux-gnu-host-x86_64-w64-mingw32-cross-gcc15/x86_64-w64-mingw32/bin/ld: 找不到 -lkernel32: 没有那个文件或目录
```

尝试禁用动态库编译出gcc和libgcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --enable-multilib --enable-languages=c,c++ --enable-nls --disable-sjlj-exceptions --enable-threads=win32 --prefix=$PREFIX --target=$TARGET --disable-shared
make all-gcc all-target-libgcc -j 20
make install-strip-gcc install-strip-target-libgcc -j 20
```

### 14.编译安装完整mingw-w64

```shell
cd ~/mingw/build
rm -rf *
../configure --prefix=$PREFIX/$TARGET --with-default-msvcrt=ucrt --host=$TARGET
make -j 24
make install-strip -j 24
# 构建交叉工具链时multilib在$TARGET/lib/32而不是$TARGET/lib32下
cd $PREFIX/$TARGET/lib
ln -s ../lib32 32
```

### 15.编译安装完整gcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --enable-multilib --enable-languages=c,c++ --enable-nls --disable-sjlj-exceptions --enable-threads=win32 --prefix=$PREFIX --target=$TARGET
make -j 20
make install-strip -j 20
# 单独安装带调试符号的库文件
make install-target-libgcc install-target-libstdc++-v3 install-target-libatomic install-target-libquadmath -j 20
```

### 16.剥离调试符号到独立符号文件

在[第15步](#15编译安装完整gcc)中我们保留了以下库的调试符号：libgcc libstdc++ libatomic libquadmath。但需要注意的是，x86_64下libgcc名为`libgcc_s_seh-1.dll`，而i386下libgcc名为`libgcc_s_dw2-1.dll`。

接下来逐个完成剥离操作：

```shell
# 生成独立的调试符号文件
$TARGET-objcopy --only-keep-debug $PREFIX/$TARGET/lib/libgcc_s_seh-1.dll $PREFIX/$TARGET/lib/libgcc_s_seh-1.dll.debug
# 剥离动态库的调试符号
$TARGET-strip $PREFIX/$TARGET/lib/libgcc_s_seh-1.dll
# 关联调试符号和动态库
$TARGET-objcopy --add-gnu-debuglink=$PREFIX/$TARGET/lib/libgcc_s_seh-1.dll.debug $PREFIX/$TARGET/lib/libgcc_s_seh-1.dll
# 重复上述操作直到处理完所有动态库
```

### 17.编译安装pexports

```shell
cd ~/pexports
mkdir build
cd build
../configure --prefix=$PREFIX
make -j 20
make install-strip -j 20
# 添加pexports前缀
mv $PREFIX/bin/pexports $PREFIX/bin/$TARGET-pexports
```

### 18.打包工具链

```shell
cd ~
export PACKAGE=$HOST-host-$TARGET-target-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

## 构建mingw[加拿大工具链](https://en.wikipedia.org/wiki/Cross_compiler#Canadian_Cross)

| build            | host               | target             |
| :--------------- | :----------------- | :----------------- |
| x86_64-linux-gnu | x86_64-w64-mingw32 | x86_64-w64-mingw32 |

### 19.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=x86_64-w64-mingw32
export TARGET=$HOST
export PREFIX=~/$HOST-native-gcc15
```

### 20.编译安装gcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --enable-multilib --enable-languages=c,c++ --enable-nls --disable-sjlj-exceptions --enable-threads=win32 --prefix=$PREFIX --target=$TARGET --host=$HOST
make -j 20
make install-strip -j 20
```

此时我们执行如下命令：

```shell
cd $PREFIX/bin
file *.dll
```

会得到如下结果：

```log
libatomic-1.dll:   PE32 executable (DLL) (console) Intel 80386 (stripped to external PDB), for MS Windows, 10 sections
libquadmath-0.dll: PE32 executable (DLL) (console) Intel 80386 (stripped to external PDB), for MS Windows, 10 sections
libssp-0.dll:      PE32 executable (DLL) (console) Intel 80386 (stripped to external PDB), for MS Windows, 10 sections
libstdc++-6.dll:   PE32 executable (DLL) (console) Intel 80386 (stripped to external PDB), for MS Windows, 10 sections
```

由此可见，`make install-strip`时安装的dll是x86而非x86_64的，这是由于开启multilib后，gcc的安装脚本会后安装multilib对应的dll,导致32位dll覆盖64位dll。
同时，我们会发现`lib`和`lib32`目录下没有这些dll，这是因为gcc的安装脚本默认将它们安装到了bin目录下。综上所述，dll的安装是完全错误的。
还可以发现，`include`、`lib`和`lib32`目录下都没有libc和sdk文件。故我们需要手动从先前安装的[交叉工具链](#构建mingw交叉工具链)中复制这些文件。

### 21.从交叉工具链中复制所需的库和头文件

这样不但不需要再次编译mingw-w64，而且可以直接复制[编译交叉工具链](#16剥离调试符号到独立符号文件)时生成的调试符号文件，不需要再次剥离调试符号。

```shell
rm *.dll
cd ~/$BUILD-host-$TARGET-target-gcc15/$TARGET
# ldscripts会在后续安装binutils时安装
cp -n lib/* $PREFIX/lib
cp -n lib32/* $PREFIX/lib32
cp -nr include/* $PREFIX/include
```

### 22.为python动态库创建归档文件

在接下来的5步中，我们将构建编译gdb所需的依赖项。具体说明请参见[构建gdb的要求](https://sourceware.org/gdb/current/onlinedocs/gdb.html/Requirements.html#Requirements)。

```shell
cd ~/python-embed
$TARGET-pexports python311.dll > libpython.def
$TARGET-dlltool -D python311.dll -d libpython.def -l libpython.a
```

### 23.编译安装libgmp

```shell
cd ~/gmp
export GMP=~/gmp/install
mkdir build
cd build
# 禁用动态库，否则编译出来的gdb会依赖libgmp.dll
../configure --host=$HOST --prefix=$GMP --disable-shared
make -j 20
make install-strip -j 20
```

### 24.编译安装libexpat

```shell
cd ~/expat/expat
export EXPAT=~/expat/install
mkdir build
cd build
# 此处也需要禁用动态库
../configure --prefix=$EXPAT --host=$HOST --disable-shared
make -j 20
make install-strip -j 20
```

### 25.编译安装libiconv

```shell
cd ~/iconv
export ICONV=~/iconv/install
mkdir build
cd build
# 此处也需要禁用动态库
../configure --prefix=$ICONV --host=$HOST --disable-shared
make -j 20
make install-strip -j 20
```

### 26.编译安装libmpfr

```shell
cd ~/mpfr
export MPFR=~/mpfr/install
mkdir build
cd build
# 此处也需要禁用动态库
../configure --prefix=$MPFR --host=$HOST --with-gmp=$GMP --disable-shared
make -j 20
make install-strip -j 20
```

### 27.编译安装binutils和gdb

要编译带有python支持的gdb就必须在编译gdb时传入python安装信息，但在交叉环境中提供这些信息是困难的。因此我们需要手动将这些信息传递给`configure`脚本。
具体说明请参见[使用交叉编译器编译带有python支持的gdb](https://sourceware.org/gdb/wiki/CrossCompilingWithPythonSupport)。
编写一个python脚本以提供上述信息：

```python
import sys
import os
from gcc_environment import environment

# sys.argv[0] shell脚本路径
# sys.argv[1] binutils/gdb/python-config.py路径
# sys.argv[2:] python脚本所需的参数
def get_config() -> None:
    assert len(sys.argv) >= 3, "Too few args"
    env = environment("")
    python_dir = env.lib_dir_list["python-embed"]
    result_list = {
        "--includes": f"-I{os.path.join(python_dir, 'include')}",
        "--ldflags": f"-L{python_dir} -lpython",
        "--exec-prefix": f"-L{python_dir}",
    }
    option_list = sys.argv[2:]
    for option in option_list:
        if option in result_list:
            print(result_list[option])
            return
    assert False, f'Invalid option list: {" ".join(option_list)}'

if __name__ == "__main__":
    get_config()
```

编写一个shell脚本以转发参数给上述python脚本：

```shell
# 获取当前文件的绝对路径
current_file="$(readlink -f $0)"
# 提取当前文件夹
current_dir="$(dirname $current_file)"
# 将接受到的参数转发给python_config.py
python3 "$current_dir/python_config.py" $@
```

值得注意的是，gdb依赖于c++11提供的条件变量，而win32线程模型仅在Windows Vista和Windows Server 2008之后的系统上支持该功能，即要求_WIN32_WINNT>=0x0600，而默认情况下该条件是不满足的。
因此需要手动设置`CXXFLAGS`来指定Windows版本。否则在编译gdbsupport时将会产生如下错误：

```log
.../std_mutex.h:164:5: 错误： ‘__gthread_cond_t’ does not name a type; did you mean ‘__gthread_once_t’?
  164 |     __gthread_cond_t* native_handle() noexcept { return &_M_cond; }
      |     ^~~~~~~~~~~~~~~~
      |     __gthread_once_t
```

交叉编译带python支持的gdb的所有要求都已经满足了，下面开始编译binutils和gdb：

```shell
cd ~/binutils/build
rm -rf *
../configure --host=$HOST --target=$TARGET --prefix=$PREFIX --disable-werror --with-gmp=$GMP --with-mpfr=$MPFR --with-expat --with-libexpat-prefix=$EXPAT --with-libiconv-prefix=$ICONV --with-system-gdbinit=$PREFIX/share/.gdbinit --with-python=$HOME/toolchains/script/python_config.sh CXXFLAGS=-D_WIN32_WINNT=0x0600
make -j 20
make install-strip -j 20
```

### 28.编译安装pexports

我们在Window下也提供pexports实用工具，下面开始编译pexports：

```shell
cd ~/pexports/build
rm -rf *
../configure --prefix=$PREFIX --host=$HOST
make -j 20
make install-strip -j 20
```

### 29.复制python embed package

```shell
cp ~/python-embed
cp python* $PREFIX/bin
```

### 30.打包工具链

```shell
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export PACKAGE=$HOST-native-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

### 31.使用工具链

在开启multilib后，`lib`和`lib32`目录下会各有一份dll，这也就是为什么不能将dll文件复制到`bin`目录下。
因而在使用时需要将`bin`，`lib`和`lib32`文件夹都添加到PATH环境变量。程序在加载dll时Windows会顺序搜索PATH中的目录，直到找到一个dll可以被加载。
因此同时将`lib`和`lib32`添加到PATH即可实现根据程序体系结构选择相应的dll。
如果将`lib`和`lib32`下的dll分别复制到`System32`和`SysWOW64`目录下，则只需要将`bin`文件夹添加到PATH环境变量，但不推荐这么做。
值得注意的是，.debug文件需要和.dll文件处于同一级目录下，否则调试时需要手动加载符号文件。

## 构建arm独立交叉工具链

| build            | host             | target        |
| :--------------- | :--------------- | :------------ |
| x86_64-linux-gnu | x86_64-linux-gnu | arm-none-eabi |

### 32.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=$BUILD
export TARGET=arm-none-eabi
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
```

### 33.编译binutils和gdb

```shell
cd ~/binutils/build
rm -rf *
export ORIGIN='$$ORIGIN'
../configure --disable-werror --enable-nls --target=$TARGET --prefix=$PREFIX --with-system-gdbinit=$PREFIX/share/.gdbinit LDFLAGS="-Wl,-rpath='$ORIGIN'/../lib64"
make -j 20
make install-strip -j 20
unset ORIGIN
echo "export PATH=$PREFIX/bin:"'$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 34.编译安装gcc

这是一个不使用newlib的完全独立的工具链，故而需要禁用所有依赖宿主系统的库和特性。此时支持的库仅包含libstdc++和libgcc。由于此时禁用了动态库，故不需要再手动剥离调试符号。

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --enable-nls --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++ --disable-threads --disable-hosted-libstdcxx --disable-libstdcxx-verbose --disable-shared --without-headers --disable-libvtv --disable-libsanitizer --disable-libssp --disable-libquadmath --disable-libgomp
make -j 20
make install-strip -j 20
make install-target-libstdc++-v3 install-target-libgcc -j 20
```

### 35.复制库和pretty-printer

编译出的arm-none-eabi-gdb依赖libstdc++，故需要从[gcc本地工具链](#构建gcc本地工具链)中复制一份。同时独立工具链不会安装pretty-printer，故也需要复制一份。

```shell
cd ~/$BUILD-native-gcc15
cp lib64/libstdc++.so.6 $PREFIX/lib64
cp lib64/libgcc_s.so.1 $PREFIX/lib64
cp -r share/gcc-15.0.0 $PREFIX/share
```

### 36.打包工具链

```shell
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export PACKAGE=$HOST-host-$TARGET-target-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

## 构建arm独立加拿大工具链

| build            | host               | target        |
| :--------------- | :----------------- | :------------ |
| x86_64-linux-gnu | x86_64-w64-mingw32 | arm-none-eabi |

### 37.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=x86_64-w64-mingw32
export TARGET=arm-none-eabi
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
```

### 38.准备编译gdb所需的库

请参阅前文构建出[libpython.a](#22为python动态库创建归档文件), [libgmp](#23编译安装libgmp), [libexpat](#24编译安装libexpat), [libiconv](#25编译安装libiconv), [libmpfr](#26编译安装libmpfr)。

### 39.编译安装binutils和gdb

原理请参阅[x86_64-w64-mingw32本地gdb构建](#27编译安装binutils和gdb)。

```shell
cd ~/binutils/build
rm -rf *
../configure --host=$HOST --target=$TARGET --prefix=$PREFIX --disable-werror --with-gmp=$GMP --with-mpfr=$MPFR --with-expat --with-libexpat-prefix=$EXPAT --with-libiconv-prefix=$ICONV --with-system-gdbinit=$PREFIX/share/.gdbinit --with-python=$HOME/toolchains/script/python_config.sh  CXXFLAGS=-D_WIN32_WINNT=0x0600
make -j 20
make install-strip -j 20
```

### 40.编译安装gcc

原理请参阅[arm独立交叉工具链](#34编译安装gcc)。

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --enable-nls --host=$HOST --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++ --disable-threads --disable-hosted-libstdcxx --disable-libstdcxx-verbose --disable-shared --without-headers --disable-libvtv --disable-libsanitizer --disable-libssp --disable-libquadmath --disable-libgomp
make -j 20
make install-strip -j 20
make install-target-libstdc++-v3 install-target-libgcc -j 20
```

### 41.从其他工具链中复制所需库和pretty-printer

从[mingw交叉工具链](#构建mingw交叉工具链)中复制动态库：

```shell
cd ~/$BUILD-host-$HOST-target-gcc15/$HOST
cp lib/libstdc++-6.dll $PREFIX/bin
cp lib/libgcc_s_seh-1.dll $PREFIX/bin
```

从[gcc本地工具链](#构建gcc本地工具链)中复制pretty-printer：

```shell
cd ~/$BUILD-native-gcc15
cp -r share/gcc-15.0.0 $PREFIX/share
```

### 42.打包工具链

```shell
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export PACKAGE=$HOST-host-$TARGET-target-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

## 构建x86_64独立交叉工具链

| build            | host             | target     |
| :--------------- | :--------------- | :--------- |
| x86_64-linux-gnu | x86_64-linux-gnu | x86_64-elf |

具体请参阅[构建arm独立交叉工具链](#构建arm独立交叉工具链)。

### 43.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=$BUILD
export TARGET=x86_64-elf
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
```

### 44.编译binutils和gdb

```shell
cd ~/binutils/build
rm -rf *
export ORIGIN='$$ORIGIN'
../configure --disable-werror --enable-nls --target=$TARGET --prefix=$PREFIX --with-system-gdbinit=$PREFIX/share/.gdbinit LDFLAGS="-Wl,-rpath='$ORIGIN'/../lib64"
make -j 20
make install-strip -j 20
unset ORIGIN
echo "export PATH=$PREFIX/bin:"'$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 45.编译安装gcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --enable-nls --target=$TARGET --prefix=$PREFIX --disable-multilib --enable-languages=c,c++ --disable-threads --disable-hosted-libstdcxx --disable-libstdcxx-verbose --disable-shared --without-headers --disable-libvtv --disable-libsanitizer --disable-libssp --disable-libquadmath --disable-libgomp
make -j 20
make install-strip -j 20
make install-target-libstdc++-v3 install-target-libgcc -j 20
```

### 46.复制库和pretty-printer

```shell
cd ~/$BUILD-native-gcc15
cp lib64/libstdc++.so.6 $PREFIX/lib64
cp lib64/libgcc_s.so.1 $PREFIX/lib64
cp -r share/gcc-15.0.0 $PREFIX/share
```

### 47.打包工具链

```shell
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export PACKAGE=$HOST-host-$TARGET-target-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

## 构建x86_64独立加拿大工具链

| build            | host               | target     |
| :--------------- | :----------------- | :--------- |
| x86_64-linux-gnu | x86_64-w64-mingw32 | x86_64-elf |

### 48.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=x86_64-w64-mingw32
export TARGET=x86_64-elf
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
```

### 49.准备编译gdb所需的库

请参阅前文构建出[libpython.a](#22为python动态库创建归档文件), [libgmp](#23编译安装libgmp), [libexpat](#24编译安装libexpat), [libiconv](#25编译安装libiconv), [libmpfr](#26编译安装libmpfr)。

### 50.编译安装binutils和gdb

原理请参阅[x86_64-w64-mingw32本地gdb构建](#27编译安装binutils和gdb)。

```shell
cd ~/binutils/build
rm -rf *
../configure --host=$HOST --target=$TARGET --prefix=$PREFIX --disable-werror --with-gmp=$GMP --with-mpfr=$MPFR --with-expat --with-libexpat-prefix=$EXPAT --with-libiconv-prefix=$ICONV --with-system-gdbinit=$PREFIX/share/.gdbinit --with-python=$HOME/toolchains/script/python_config.sh  CXXFLAGS=-D_WIN32_WINNT=0x0600
make -j 20
make install-strip -j 20
```

### 51.编译安装gcc

原理请参阅[arm独立交叉工具链](#34编译安装gcc)。

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --enable-nls --host=$HOST --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++ --disable-threads --disable-hosted-libstdcxx --disable-libstdcxx-verbose --disable-shared --without-headers --disable-libvtv --disable-libsanitizer --disable-libssp --disable-libquadmath --disable-libgomp
make -j 20
make install-strip -j 20
make install-target-libstdc++-v3 install-target-libgcc -j 20
```

### 52.从其他工具链中复制所需库和pretty-printer

从[mingw交叉工具链](#构建mingw交叉工具链)中复制动态库：

```shell
cd ~/$BUILD-host-$HOST-target-gcc15/$HOST
cp lib/libstdc++-6.dll $PREFIX/bin
cp lib/libgcc_s_seh-1.dll $PREFIX/bin
```

从[gcc本地工具链](#构建gcc本地工具链)中复制pretty-printer：

```shell
cd ~/$BUILD-native-gcc15
cp -r share/gcc-15.0.0 $PREFIX/share
```

### 53.打包工具链

```shell
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export PACKAGE=$HOST-host-$TARGET-target-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

## 构建到其他x86_64 Linux发行版的交叉工具链

| build            | host             | target                      |
| :--------------- | :--------------- | :-------------------------- |
| x86_64-linux-gnu | x86_64-linux-gnu | x86_64-ubuntu2004-linux-gnu |

值得注意的是，libc版本、种类不同的工具链是不同的工具链，它们具有不同的target平台。为了和本地工具链加以区分，此处修改交叉工具链的vender字段。在vender字段中亦可以添加目标系统的版本以示区分。
值得注意的是，此处目标系统为ubuntu 20.04，使用的libc为glibc 2.30。交叉工具链的glibc要与目标系统匹配。由于x32已经濒临淘汰，故此处不再编译x32的multilib。

### 54.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=$BUILD
export TARGET=x86_64-ubuntu2004-linux-gnu
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
```

### 55.编译gdb

```shell
cd ~/binutils/build
rm -rf *
export ORIGIN='$$ORIGIN'
../configure --disable-werror --enable-nls --target=$TARGET --prefix=$PREFIX --disable-binutils --with-system-gdbinit=$PREFIX/share/.gdbinit LDFLAGS="-Wl,-rpath='$ORIGIN'/../lib64"
make -j 20
make install-strip -j 20
unset ORIGIN
```

### 56.编译binutils

值得注意的是，binutils的一部分会安装到`$PREFIX/$TARGET`目录下，而此目录下的lib64存放的是目标平台的glibc,故不能设置`rpath`。

```shell
cd ~/binutils/build
rm -rf *
../configure --disable-werror --enable-nls --target=$TARGET --prefix=$PREFIX --disable-gdb
make -j 20
make install-strip -j 20
echo "export PATH=$PREFIX/bin:"'$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 57.安装Linux头文件

```shell
cd ~/linux
make ARCH=x86 INSTALL_HDR_PATH=$PREFIX/$TARGET headers_install
```

### 58.编译安装gcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --disable-bootstrap --enable-nls --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++ --disable-shared
make all-gcc -j 20
make install-strip-gcc -j 20
```

### 59.安装glibc头文件

由于当前的工具链尚不完整，故需要手动设置`libc_cv_forced_unwind=yes`，否则会出现：

```log
configure: error: forced unwind support is required
```

glibc头文件安装命令如下：

```shell
cd ~/glibc
mkdir build
cd build
../configure --host=$TARGET --build=$BUILD --prefix=$PREFIX/$TARGET --disable-werror libc_cv_forced_unwind=yes
make install-headers
```

在安装完头文件后，还需要手动新建`include/gnu/stubs.h`文件，若缺少该文件，则无法编译出libgcc。该文件会在安装完整glibc时被覆盖。

```shell
touch $PREFIX/$TARGET/include/gnu/stubs.h
```

### 60.编译安装libgcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --disable-bootstrap --enable-nls --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++ --disable-shared
make all-target-libgcc -j 20
make install-strip-target-gcc -j 20
```

### 61.编译安装32位glibc

值得注意的是，尽管glibc本身不会使用c++编译器，但构建脚本会使用c++编译器进行链接，故c++编译器也需要设置。

```shell
cd ~/glibc/build
rm -rf *
../configure --host=i686-linux-gnu --build=$BUILD --prefix=$PREFIX/$TARGET --disable-werror CC="$TARGET-gcc -m32" CXX="$TARGET-g++ -m32"
make -j 20
make install -j 20
```

### 62.剥离调试符号到单独的符号文件

```shell
cd $PREFIX/$TARGET/lib
$TARGET-strip gconv/*.so
$TARGET-strip audit/*.so
$TARGET-strip ../libexec/getconf/*
$TARGET-strip ../sbin/*
$TARGET-objcopy --only-keep-debug libc-2.30.so libc-2.30.so.debug
$TARGET-objcopy --add-gnu-debuglink=libc-2.30.so.debug libc-2.30.so
# 同理剥离出其他需要的符号文件
$TARGET-strip *.so
```

### 63.修改链接器脚本

此时只有`lib/libc.so`需要修改，该文件的内容如下：

```ldscript
// lib/libc.so
/* GNU ld script
   Use the shared library, but some functions are only in
   the static library, so try that secondarily.  */
OUTPUT_FORMAT(elf32-i386)
GROUP ( /home/luo/x86_64-linux-gnu-host-x86_64-ubuntu2004-linux-gnu-target-gcc15/x86_64-ubuntu2004-linux-gnu/lib/libc.so.6 /home/luo/x86_64-linux-gnu-host-x86_64-ubuntu2004-linux-gnu-target-gcc15/x86_64-ubuntu2004-linux-gnu/lib/libc_nonshared.a  AS_NEEDED ( /home/luo/x86_64-linux-gnu-host-x86_64-ubuntu2004-linux-gnu-target-gcc15/x86_64-ubuntu2004-linux-gnu/lib/ld-linux.so.2 ) )
```

可以看到其中使用的是绝对地址，这会导致移动安装位置后，无法正确链接。故需要修改为使用相对路径：

```ldscript
// lib/libc.so
OUTPUT_FORMAT(elf32-i386)
GROUP (libc.so.6 libc_nonshared.a AS_NEEDED (ld-linux.so.2))
```

### 64.移动lib目录到lib64

由于在此multilib环境下，交叉编译器编译时lib32目录下存放32位multilib而lib目录下存放64位multilib，故需要调整glibc的位置。而ldscript需要始终存放在lib目录下。

```shell
mv $PREFIX/$TARGET/lib $PREFIX/$TARGET/lib32
mkdir $PREFIX/$TARGET/lib
mv $PREFIX/$TARGET/lib32/ldscripts $PREFIX/$TARGET/lib
```

### 65.编译安装64位glibc

```shell
cd ~/glibc/build
rm -rf *
../configure --host=$TARGET --build=$BUILD --prefix=$PREFIX/$TARGET --disable-werror
make -j 20
make install -j 20
```

### 66.剥离调试符号到单独的符号文件

```shell
cd $PREFIX/$TARGET/lib
$TARGET-strip gconv/*.so
$TARGET-strip audit/*.so
$TARGET-strip ../libexec/getconf/*
$TARGET-strip ../sbin/*
$TARGET-objcopy --only-keep-debug libc-2.30.so libc-2.30.so.debug
$TARGET-objcopy --add-gnu-debuglink=libc-2.30.so.debug libc-2.30.so
# 同理剥离出其他需要的符号文件
$TARGET-strip *.so
```

### 67.修改链接器脚本

同理修改`libc.so`，`libm.a`和`libm.so`：

```ldscript
// libc.so
OUTPUT_FORMAT(elf64-x86-64)
GROUP (libc.so.6 libc_nonshared.a AS_NEEDED (ld-linux-x86-64.so.2))
// libm.a
OUTPUT_FORMAT(elf64-x86-64)
GROUP (libm-2.30.a libmvec.a)
// libm.so
OUTPUT_FORMAT(elf64-x86-64)
GROUP (libm.so.6 AS_NEEDED(libmvec_nonshared.a libmvec.so.1))
```

### 68.为multilib建立软链接

```shell
cd $PREFIX/$TARGET/lib
ln -s ../lib32 32
```

### 69.修改asan源文件

在`gcc/libsanitizer/asan/asan_linux.cpp`中默认没有包含`linux/limits.h`文件，这会导致编译的时候缺少`PATH_MAX`宏，故将其修改为：

```c++
// gcc/libsanitizer/asan/asan_linux.cpp
#  include <dlfcn.h>
#  include <fcntl.h>
#  include <limits.h>
#  include <pthread.h>
#  include <stdio.h>
#  include <sys/mman.h>
#  include <sys/resource.h>
#  include <sys/syscall.h>
#  include <sys/time.h>
#  include <sys/types.h>
#  include <unistd.h>
#  include <unwind.h>
#  include <linux/limits.h> // < 添加linux/limits.h头文件
```

### 70.编译完整gcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --disable-bootstrap --enable-nls --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++
make -j 20
make install-strip -j 20
# 单独安装带调试符号的库文件
make install-target-libgcc install-target-libstdc++-v3 install-target-libatomic install-target-libquadmath install-target-libgomp -j 20
```

### 71.剥离调试符号到独立的符号文件

在[第70步](#70编译完整gcc)中我们保留了以下库的调试符号：libgcc libstdc++ libatomic libquadmath libgomp

接下来逐个完成剥离操作：

```shell
# 生成独立的调试符号文件
objcopy --only-keep-debug $PREFIX/lib64/libgcc_s.so.1 $PREFIX/lib64/libgcc_so.1.debug
# 剥离动态库的调试符号
strip $PREFIX/lib64/libgcc_s.so.1
# 关联调试符号和动态库
objcopy --add-gnu-debuglink=$PREFIX/lib64/libgcc_s.so.1.debug $PREFIX/lib64/libgcc_s.so.1
# 重复上述操作直到处理完所有动态库
```

### 72.移动lib目录下的glibc到lib64目录下

lib32目录下是纯净的glibc文件，故以lib32为参照经行文件复制，建议使用python脚本完成：

```python
import shutil
import os
home_dir = os.path.expanduser("~")
lib_prefix = os.path.join(home_dir, "x86_64-linux-gnu-host-x86_64-ubuntu2004-linux-gnu-gcc15", "x86_64-ubuntu2004-linux-gnu")
lib_dir = os.path.join(env.lib_prefix, "lib")
lib32_dir = os.path.join(env.lib_prefix, "lib32")
lib64_dir = os.path.join(env.lib_prefix, "lib64")
for file in os.listdir(lib_dir):
    lib_path = os.path.join(lib_dir, file)
    lib32_path = os.path.join(lib32_dir, file)
    lib64_path = os.path.join(lib64_dir, file)
    if os.path.exists(lib32_path) or file == "ld-linux-x86-64.so.2":
        shutil.move(lib_path, lib64_path)
```

### 73.移动lib32目录下的glibc到lib目录下

lib32目录下是纯净的glibc文件，直接移动即可：

```shell
cd $PREFIX/$TARGET
mov lib32/* lib
```

### 74.从其他工具链中复制所需库

从[x86_64-linux-gnu本地工具链](#构建gcc本地工具链)中复制动态库：

```shell
cd ~/$BUILD-host-$HOST-target-gcc15/$HOST
cp lib64/libstdc++.so.6 $PREFIX/lib64
cp lib64/libgcc_s.so.1 $PREFIX/lib64
```

### 75.打包工具链

```shell
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export PACKAGE=$HOST-host-$TARGET-target-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

## 构建到loongarch64-linux-gnu的交叉工具链

| build            | host             | target                |
| :--------------- | :--------------- | :-------------------- |
| x86_64-linux-gnu | x86_64-linux-gnu | loongarch64-linux-gnu |

值得注意的是，libc版本、种类不同的工具链是不同的工具链，它们具有不同的target平台，此处目标系统使用的libc为glibc 2.39。交叉工具链的glibc要与目标系统匹配。

### 76.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=$BUILD
export TARGET=loongarch64-linux-gnu
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
# Linux头文件架构
export ARCH=loongarch
```

### 77.编译binutils和gdb

```shell
cd ~/binutils/build
rm -rf *
export ORIGIN='$$ORIGIN'
../configure --disable-werror --enable-nls --target=$TARGET --prefix=$PREFIX --disable-gdbserver--with-system-gdbinit=$PREFIX/share/.gdbinit LDFLAGS="-Wl,-rpath='$ORIGIN'/../lib64"
make -j 20
make install-strip -j 20
unset ORIGIN
echo "export PATH=$PREFIX/bin:"'$PATH' >> ~/.bashrc
source ~/.bashrc
```

### 78.安装Linux头文件

```shell
cd ~/linux
make INSTALL_HDR_PATH=$PREFIX/$TARGET headers_install
```

### 79.编译安装gcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --disable-bootstrap --enable-nls --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++ --disable-shared
make all-gcc -j 20
make install-strip-gcc -j 20
```

### 80.安装glibc头文件

```shell
cd ~/glibc
mkdir build
cd build
../configure --host=$TARGET --build=$BUILD --prefix=$PREFIX/$TARGET --disable-werror libc_cv_forced_unwind=yes
make install-headers
touch $PREFIX/$TARGET/include/gnu/stubs.h
```

### 81.编译安装libgcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --disable-bootstrap --enable-nls --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++ --disable-shared
make all-target-libgcc -j 20
make install-strip-target-gcc -j 20
```

### 82.编译安装glibc

```shell
cd ~/glibc/build
rm -rf *
../configure --host=$TARGET --build=$BUILD --prefix=$PREFIX/$TARGET --disable-werror
make -j 20
make install -j 20
```

### 83.修改链接器脚本

需要修改`lib/libc.so`为使用相对路径：

```ldscript
// lib/libc.so
OUTPUT_FORMAT(elf64-loongarch)
GROUP (libc.so.6 libc_nonshared.a AS_NEEDED(ld-linux-loongarch-lp64d.so.1))
```

### 84.编译完整gcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --disable-bootstrap --enable-nls --target=$TARGET --prefix=$PREFIX --enable-multilib --enable-languages=c,c++
make -j 20
make install-strip -j 20
# 单独安装带调试符号的库文件
make install-target-libgcc install-target-libstdc++-v3 install-target-libatomic install-target-libquadmath install-target-libgomp -j 20
```

### 85.从其他工具链中复制所需库

从[x86_64-linux-gnu本地工具链](#构建gcc本地工具链)中复制动态库：

```shell
cd ~/$BUILD-host-$HOST-target-gcc15/$HOST
cp lib64/libstdc++.so.6 $PREFIX/lib64
cp lib64/libgcc_s.so.1 $PREFIX/lib64
```

### 86.修复libgcc的limits.h中MB_LEN_MAX定义不准确问题

对limits.h文件末尾的修改如下：

```c++
// lib/gcc/loongarch64-linux-gnu/15.0.0/include/limits.h
#endif /* _LIMITS_H___ */
#undef MB_LEN_MAX
#define MB_LEN_MAX 16
```

### 87.编译gdbserver

```shell
cd ~/binutils/build
rm -rf *
../configure --prefix=$PREFIX --host=$TARGET --target=$TARGET --disable-werror --disable-binutils --disable-gdb --enable-gdbserver --enable-nls
make -j 20
# 其他工具的体系结构与host不同，覆盖host工具会导致错误，故只安装gdbserver
make install-strip-gdbserver -j 20
```

### 88.打包工具链

```shell
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export PACKAGE=$HOST-host-$TARGET-target-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

## 构建mingw到loongarch64-linux-gnu的加拿大工具链

| build            | host               | target                |
| :--------------- | :----------------- | :-------------------- |
| x86_64-linux-gnu | x86_64-w32-mingw64 | loongarch64-linux-gnu |

值得注意的是，libc版本、种类不同的工具链是不同的工具链，它们具有不同的target平台，此处目标系统使用的libc为glibc 2.39。交叉工具链的glibc要与目标系统匹配。

### 89.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=x86_64-w32-mingw64
export TARGET=loongarch64-linux-gnu
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
# Linux头文件架构
export ARCH=loongarch
```

### 90.编译binutils和gdb

```shell
cd ~/binutils/build
rm -rf *
export ORIGIN='$$ORIGIN'
../configure --disable-werror --disable-nls --target=$TARGET --prefix=$PREFIX --disable-gdbserver --with-gmp=$GMP --with-mpfr=$MPFR --with-expat --with-libexpat-prefix=$EXPAT --with-libiconv-prefix=$ICONV --with-system-gdbinit=$PREFIX/share/.gdbinit --with-python=$HOME/toolchains/script/python_config.sh CXXFLAGS=-D_WIN32_WINNT=0x0600
make -j 20
make install-strip -j 20
```

### 92.编译安装gcc

```shell
cd ~/gcc/build
rm -rf *
../configure --disable-werror --disable-bootstrap --disable-nls --host=$HOST --target=$TARGET --prefix=$PREFIX --disbale-multilib --enable-languages=c,c++
make -j 20
make install-strip -j 20
```

### 93.从交叉工具链复制文件

此工具链所需的linux头文件、glibc等已经在构建交叉工具链时完成构建，只需复制即可。

```shell
export CROSS_PREFIX=~/$BUILD-host-$TARGET-target-gcc15
export SRC_PREFIX=$CROSS_PREFIX/$TARGET
export DST_PREFIX=$PREFIX/$TARGET
# 个别工具链还需要复制lib64，如果目录下有该文件夹则一并复制
# 换而言之，复制除bin外的所有文件夹
cp -rf $SRC_PREFIX/include $DST_PREFIX/include
cp -rf $SRC_PREFIX/lib $DST_PREFIX/lib
# 复制gdbserver
cp $CROSS_PREFIX/bin/gdbserver $PREFIX/bin/gdbserver
```

### 94.打包工具链

```shell
cd ~
cp ~/toolchains/script/.gdbinit $PREFIX/share
export PACKAGE=$HOST-host-$TARGET-target-gcc15
tar -cf $PACKAGE.tar $PACKAGE/
xz -ev9 -T 0 --memlimit=$MEMORY $PACKAGE.tar
```

## 构建到arm-linux-gnueabi的交叉工具链

| build            | host             | target            |
| :--------------- | :--------------- | :---------------- |
| x86_64-linux-gnu | x86_64-linux-gnu | arm-linux-gnueabi |

值得注意的是，libc版本、种类不同的工具链是不同的工具链，它们具有不同的target平台，此处目标系统使用的libc为glibc 2.39。交叉工具链的glibc要与目标系统匹配。

### 95.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=$BUILD
export TARGET=arm-linux-gnueabi
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
# Linux头文件架构
export ARCH=arm
```

### 96.构建工具链

参考[loongarch64-linux-gnu交叉工具链](#构建到loongarch64-linux-gnu的交叉工具链)构建流程完成构建。
值得注意的是，需要修改`lib/libc.so`为：

```ldscript
// lib/libc.so
OUTPUT_FORMAT(elf32-littlearm)
GROUP (libc.so.6 libc_nonshared.a AS_NEEDED (ld-linux.so.3))
```

## 构建mingw到arm-linux-gnueabi的加拿大工具链

| build            | host               | target            |
| :--------------- | :----------------- | :---------------- |
| x86_64-linux-gnu | x86_64-w32-mingw64 | arm-linux-gnueabi |

值得注意的是，libc版本、种类不同的工具链是不同的工具链，它们具有不同的target平台，此处目标系统使用的libc为glibc 2.39。交叉工具链的glibc要与目标系统匹配。

### 97.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=x86_64-w32-mingw64
export TARGET=arm-linux-gnueabi
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
# Linux头文件架构
export ARCH=arm
```

### 98.构建工具链

参考[arm-linux-gnueabi交叉工具链](#构建到arm-linux-gnueabi的交叉工具链)和
[loongarch64-linux-gnu加拿大工具链](#构建mingw到loongarch64-linux-gnu的加拿大工具链)构建流程完成构建。

## 构建到arm-linux-gnueabihf的交叉工具链

| build            | host             | target              |
| :--------------- | :--------------- | :------------------ |
| x86_64-linux-gnu | x86_64-linux-gnu | arm-linux-gnueabihf |

值得注意的是，libc版本、种类不同的工具链是不同的工具链，它们具有不同的target平台，此处目标系统使用的libc为glibc 2.39。交叉工具链的glibc要与目标系统匹配。

### 99.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=$BUILD
export TARGET=arm-linux-gnueabihf
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
# Linux头文件架构
export ARCH=arm
```

### 100.构建工具链

参考[loongarch64-linux-gnu交叉工具链](#构建到loongarch64-linux-gnu的交叉工具链)构建流程完成构建。

## 构建mingw到arm-linux-gnueabihf的加拿大工具链

| build            | host               | target              |
| :--------------- | :----------------- | :------------------ |
| x86_64-linux-gnu | x86_64-w32-mingw64 | arm-linux-gnueabihf |

值得注意的是，libc版本、种类不同的工具链是不同的工具链，它们具有不同的target平台，此处目标系统使用的libc为glibc 2.39。交叉工具链的glibc要与目标系统匹配。

### 101.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=x86_64-w32-mingw64
export TARGET=arm-linux-gnueabihf
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
# Linux头文件架构
export ARCH=arm
```

### 102.构建工具链

参考[arm-linux-gnueabihf交叉工具链](#构建到arm-linux-gnueabihf的交叉工具链)和
[loongarch64-linux-gnu加拿大工具链](#构建mingw到loongarch64-linux-gnu的加拿大工具链)构建流程完成构建。

## 构建到loongarch64-loongnix-linux-gnu的交叉工具链

| build            | host             | target                         |
| :--------------- | :--------------- | :----------------------------- |
| x86_64-linux-gnu | x86_64-linux-gnu | loongarch64-loongnix-linux-gnu |

这是为loongnix操作系统交叉编译所需要的工具链，值得注意的是，loongnix使用的是修改过的Linux 4.19和Glibc 2.28而非主线版本。
故而需要从[loongnix源](https://pkg.loongnix.cn/loongnix/)上下载Linux和Glibc的源代码。

### 103.下载源代码

| 项目  | URL                                                                                  |
| ----- | ------------------------------------------------------------------------------------ |
| Linux | <https://pkg.loongnix.cn/loongnix/pool/main/l/linux/linux_4.19.190.8.22.orig.tar.gz> |
| Glibc | <https://pkg.loongnix.cn/loongnix/pool/main/g/glibc/glibc_2.28.orig.tar.gz>          |

### 104.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=$BUILD
export TARGET=loongarch64-loongnix-linux-gnu
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
# Linux头文件架构
export ARCH=loongarch
```

### 105.构建工具链

参见[loongarch64-linux-gnu工具链](#构建到loongarch64-linux-gnu的交叉工具链)的构建流程。
与loongarch64-linux-gnu工具链不同，此版本的glibc在configure时需要额外增加`--enable-obsolete-rpc`选项。
由于Glibc和Linux内核版本较老旧，此平台不支持`libsanitizer`，故而需要增加`--disable-libsanitizer`选项。
此版本的glibc的动态链接器名为`ld.so.1`，故而链接器脚本需要做如下修改：

```ldscript
// lib/libc.so
OUTPUT_FORMAT(elf64-loongarch)
GROUP (libc.so.6 libc_nonshared.a AS_NEEDED (ld.so.1))
```

同时在使用工具链时需要增加链接选项`-Wl,-dynamic-linker=/lib64/ld.so.1`以设置动态链接器路径。

## 构建mingw到loongarch64-loongnix-linux-gnu的加拿大工具链

| build            | host               | target                         |
| :--------------- | :----------------- | :----------------------------- |
| x86_64-linux-gnu | x86_64-w32-mingw64 | loongarch64-loongnix-linux-gnu |

值得注意的是，libc版本、种类不同的工具链是不同的工具链，它们具有不同的target平台，此处目标系统使用的libc为glibc 2.39。交叉工具链的glibc要与目标系统匹配。

### 106.设置环境变量

```shell
export BUILD=x86_64-linux-gnu
export HOST=x86_64-w32-mingw64
export TARGET=loongarch64-loongnix-linux-gnu
export PREFIX=~/$HOST-host-$TARGET-target-gcc15
# Linux头文件架构
export ARCH=arm
```

### 107.构建工具链

参考[loongarch64-loongnix-linux-gnu交叉工具链](#构建到loongarch64-loongnix-linux-gnu的交叉工具链)和
[loongarch64-linux-gnu加拿大工具链](#构建mingw到loongarch64-linux-gnu的加拿大工具链)构建流程完成构建。

## 后记

其他GCC工具链的编译流程大同小异，此处不再赘述，具体可参照对应的编译脚本。
