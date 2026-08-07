#include "shell/Matrix24.hpp"

#include <stdexcept>

namespace shell {

Matrix24::Matrix24() = default;

double& Matrix24::operator()(std::size_t row, std::size_t col) {
    if (row >= kSize || col >= kSize) {
        throw std::out_of_range("Matrix24 index out of range");
    }
    return data_[row * kSize + col];
}

double Matrix24::operator()(std::size_t row, std::size_t col) const {
    if (row >= kSize || col >= kSize) {
        throw std::out_of_range("Matrix24 index out of range");
    }
    return data_[row * kSize + col];
}

std::size_t Matrix24::rows() const {
    return kSize;
}

std::size_t Matrix24::cols() const {
    return kSize;
}

} // namespace shell

