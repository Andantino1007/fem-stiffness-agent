#pragma once

#include <array>
#include <cstddef>

namespace fem::s4 {

class Matrix24 {
public:
    static constexpr std::size_t kSize = 24;

    Matrix24();

    double& operator()(std::size_t row, std::size_t col);
    double operator()(std::size_t row, std::size_t col) const;

    std::size_t rows() const;
    std::size_t cols() const;

private:
    std::array<double, kSize * kSize> data_{};
};

} // namespace fem::s4

