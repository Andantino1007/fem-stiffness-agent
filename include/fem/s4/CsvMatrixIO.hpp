#pragma once

#include "fem/s4/Matrix24.hpp"

#include <filesystem>

namespace fem::s4 {

Matrix24 readMatrix24Csv(const std::filesystem::path& path);
void writeMatrix24Csv(const Matrix24& matrix, const std::filesystem::path& path);

} // namespace fem::s4

