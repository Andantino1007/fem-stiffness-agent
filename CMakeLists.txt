cmake_minimum_required(VERSION 3.16)
project(fem_matrix_multi_agent_workflow LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_library(s4_stiffness_core
    src/fem/s4/CsvMatrixIO.cpp
    src/fem/s4/Matrix24.cpp
    src/fem/s4/MatrixCompare.cpp
    src/fem/s4/S4ElementInput.cpp
    src/fem/s4/S4Stiffness.cpp
)
target_include_directories(s4_stiffness_core PUBLIC include)

add_executable(s4_stiffness_cli src/cli/s4_stiffness_cli.cpp)
target_link_libraries(s4_stiffness_cli PRIVATE s4_stiffness_core)

add_executable(s4_stiffness_tests tests/infra/catch.cpp tests/s4_stiffness_tests.cpp)
target_include_directories(s4_stiffness_tests PRIVATE tests)
target_link_libraries(s4_stiffness_tests PRIVATE s4_stiffness_core)
