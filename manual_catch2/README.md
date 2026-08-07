# 手动编译和运行 Catch2

这个目录用于独立练习本项目的 C++ 测试流程。它不会使用项目原有的
`build/verification`，编译结果只放在本目录的 `build/` 中。

它复用以下现有文件：

- `../src/shell/`：待测试的壳单元 C++ 实现；
- `../include/shell/`：对应头文件；
- `../tests/shell_stiffness_tests.cpp`：项目编写的 6 个测试用例；
- `../tests/infra/catch.cpp` 和 `catch.hpp`：项目内置的 Catch2 v3.0.1。

因此不需要下载或安装 Catch2，但需要电脑上有支持 C++17 的编译器。

## 1. 进入练习目录

在项目根目录打开终端，然后执行：

```bash
cd manual_catch2
```

检查编译器是否存在：

```bash
c++ --version
```

macOS 通常使用 Apple Clang。如果提示找不到命令，可先安装 Xcode Command Line Tools：

```bash
xcode-select --install
```

## 2. 从零开始编译

先删除本目录以前生成的测试程序：

```bash
make clean
```

然后编译：

```bash
make
```

成功后会得到：

```text
manual_catch2/build/shell_stiffness_tests
```

编译命令做了三件事：

1. 使用 `-std=c++17` 编译壳单元实现；
2. 编译内置的 Catch2 和测试用例；
3. 把所有目标代码链接成一个可以直接运行的测试程序。

## 3. 查看和运行测试

列出测试用例：

```bash
make list
```

运行全部测试：

```bash
make test
```

正常结果应类似：

```text
All tests passed (43 assertions in 6 test cases)
```

`make test` 会先判断源码是否比测试程序新。如果源码修改过，它会自动重新编译。

也可以直接运行二进制。由于测试数据路径以项目根目录为基准，需要这样执行：

```bash
cd ..
./manual_catch2/build/shell_stiffness_tests
```

## 4. 只运行部分测试

测试用例带有 `[baseline]` 和 `[stiffness]` 标签。在项目根目录执行：

```bash
./manual_catch2/build/shell_stiffness_tests '[baseline]'
./manual_catch2/build/shell_stiffness_tests '[stiffness]'
```

显示每个成功断言的详细信息：

```bash
./manual_catch2/build/shell_stiffness_tests --success
```

查看 Catch2 的全部命令行选项：

```bash
./manual_catch2/build/shell_stiffness_tests --help
```

## 5. 尝试修改或新增测试

测试源文件是：

```text
tests/shell_stiffness_tests.cpp
```

一个最小测试的写法如下：

```cpp
TEST_CASE("我的测试名称", "[practice]") {
    const int actual = 1 + 1;
    REQUIRE(actual == 2);
}
```

保存后回到练习目录运行：

```bash
make test
```

Catch2 中常用的宏：

- `TEST_CASE(...)`：定义测试用例；
- `REQUIRE(condition)`：条件失败时，立即停止当前测试用例；
- `CHECK(condition)`：条件失败后，继续检查当前测试用例的其他断言；
- `REQUIRE_THROWS_AS(expression, Type)`：检查表达式是否抛出指定异常。

## 6. 完整练习流程

每次想从头体验一遍时运行：

```bash
cd manual_catch2
make clean
make
make list
make test
```

如果只想快速验证最新代码，直接运行：

```bash
cd manual_catch2
make test
```

## 常见问题

### 修改源码后是否必须手动清理？

一般不需要。`make test` 会根据文件修改时间重新编译。想确认是完全从零编译时，才运行
`make clean && make test`。

### Catch2 是预编译库吗？

不是。本项目保存了 Catch2 的源码。执行 `make` 时，`tests/infra/catch.cpp` 会和项目源码、
测试源码一起被编译并链接到 `shell_stiffness_tests` 中。

### 为什么不能随便在任意目录直接运行二进制？

现有测试使用了 `data/abaqus/...` 这样的相对路径，因此运行时工作目录必须是项目根目录。
`make test` 已经自动处理了这一点。
