#pragma once

#include "shell/Matrix24.hpp"

namespace shell {

struct MatrixError {
    double frobeniusRelative{};
    double maxAbsolute{};
    double maxRelativeEntry{};
    double symmetryError{};
};

MatrixError compareMatrix(const Matrix24& actual, const Matrix24& expected);
double symmetryError(const Matrix24& matrix);

} // namespace shell

