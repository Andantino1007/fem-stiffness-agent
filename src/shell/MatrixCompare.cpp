#include "shell/MatrixCompare.hpp"

#include <algorithm>
#include <cmath>

namespace shell {

double symmetryError(const Matrix24& matrix) {
    double numerator = 0.0;
    double denominator = 0.0;

    for (std::size_t i = 0; i < Matrix24::kSize; ++i) {
        for (std::size_t j = 0; j < Matrix24::kSize; ++j) {
            const double diff = matrix(i, j) - matrix(j, i);
            numerator += diff * diff;
            denominator += matrix(i, j) * matrix(i, j);
        }
    }

    if (denominator == 0.0) {
        return numerator == 0.0 ? 0.0 : std::sqrt(numerator);
    }
    return std::sqrt(numerator) / std::sqrt(denominator);
}

MatrixError compareMatrix(const Matrix24& actual, const Matrix24& expected) {
    MatrixError error;
    double diffNormSquared = 0.0;
    double expectedNormSquared = 0.0;
    constexpr double eps = 1.0e-12;

    for (std::size_t i = 0; i < Matrix24::kSize; ++i) {
        for (std::size_t j = 0; j < Matrix24::kSize; ++j) {
            const double diff = actual(i, j) - expected(i, j);
            const double absDiff = std::abs(diff);
            diffNormSquared += diff * diff;
            expectedNormSquared += expected(i, j) * expected(i, j);
            error.maxAbsolute = std::max(error.maxAbsolute, absDiff);
            error.maxRelativeEntry =
                std::max(error.maxRelativeEntry, absDiff / std::max(std::abs(expected(i, j)), eps));
        }
    }

    if (expectedNormSquared == 0.0) {
        error.frobeniusRelative = std::sqrt(diffNormSquared);
    } else {
        error.frobeniusRelative = std::sqrt(diffNormSquared) / std::sqrt(expectedNormSquared);
    }
    error.symmetryError = symmetryError(actual);
    return error;
}

} // namespace shell

