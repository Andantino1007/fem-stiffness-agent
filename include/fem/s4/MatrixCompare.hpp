#pragma once

#include "fem/s4/Matrix24.hpp"

namespace fem::s4 {

struct MatrixError {
    double frobeniusRelative{};
    double maxAbsolute{};
    double maxRelativeEntry{};
    double symmetryError{};
};

MatrixError compareMatrix(const Matrix24& actual, const Matrix24& expected);
double symmetryError(const Matrix24& matrix);

} // namespace fem::s4

