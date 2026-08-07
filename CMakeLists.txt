cmake_minimum_required(VERSION 3.16)
project(requirement2_stiffness_workflow LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(stiffness_core
    src/shell/CsvMatrixIO.cpp
    src/shell/Matrix24.cpp
    src/shell/MatrixCompare.cpp
    src/shell/ShellElementInput.cpp
    src/shell/ShellStiffness.cpp
)
target_include_directories(stiffness_core PUBLIC include)

add_executable(stiffness_cli src/shell_stiffness_cli.cpp)
target_link_libraries(stiffness_cli PRIVATE stiffness_core)

add_executable(stiffness_tests tests/infra/catch.cpp tests/shell_stiffness_tests.cpp)
target_include_directories(stiffness_tests PRIVATE tests)
target_link_libraries(stiffness_tests PRIVATE stiffness_core)
