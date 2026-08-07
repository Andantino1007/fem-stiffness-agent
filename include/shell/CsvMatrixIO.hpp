#pragma once

#include "shell/Matrix24.hpp"

#include <filesystem>

namespace shell {

Matrix24 readMatrix24Csv(const std::filesystem::path& path);
void writeMatrix24Csv(const Matrix24& matrix, const std::filesystem::path& path);

} // namespace shell

