CXX ?= c++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -pedantic

ROOT := $(abspath ..)
BUILD_DIR := $(CURDIR)/build
TEST_BIN := $(BUILD_DIR)/shell_stiffness_tests

SHELL_SOURCES := \
	$(ROOT)/src/shell/CsvMatrixIO.cpp \
	$(ROOT)/src/shell/Matrix24.cpp \
	$(ROOT)/src/shell/MatrixCompare.cpp \
	$(ROOT)/src/shell/ShellElementInput.cpp \
	$(ROOT)/src/shell/ShellStiffness.cpp

TEST_SOURCES := \
	$(ROOT)/tests/infra/catch.cpp \
	$(ROOT)/tests/shell_stiffness_tests.cpp

.PHONY: all test list clean help

all: $(TEST_BIN)

$(TEST_BIN): $(SHELL_SOURCES) $(TEST_SOURCES)
	mkdir -p "$(BUILD_DIR)"
	$(CXX) $(CXXFLAGS) -I"$(ROOT)/include" -I"$(ROOT)/tests" \
		$(SHELL_SOURCES) $(TEST_SOURCES) -o "$@"

test: $(TEST_BIN)
	cd "$(ROOT)" && "$(TEST_BIN)"

list: $(TEST_BIN)
	cd "$(ROOT)" && "$(TEST_BIN)" --list-tests

clean:
	rm -f "$(TEST_BIN)"

help:
	@echo "make        编译 Catch2 测试程序"
	@echo "make list   列出所有测试用例"
	@echo "make test   编译（如有需要）并执行全部测试"
	@echo "make clean  删除本目录生成的测试程序"
