#include "fem/s4/CsvMatrixIO.hpp"

#include <filesystem>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <string>

namespace fem::s4 {

Matrix24 readMatrix24Csv(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("failed to open matrix CSV: " + path.string());
    }

    Matrix24 matrix;
    std::string line;
    std::size_t row = 0;

    while (std::getline(input, line)) {
        if (line.empty()) {
            continue;
        }
        if (row >= Matrix24::kSize) {
            throw std::runtime_error("matrix CSV has more than 24 rows: " + path.string());
        }

        std::stringstream ss(line);
        std::string cell;
        std::size_t col = 0;
        while (std::getline(ss, cell, ',')) {
            if (col >= Matrix24::kSize) {
                throw std::runtime_error("matrix CSV has more than 24 columns: " + path.string());
            }
            matrix(row, col) = std::stod(cell);
            ++col;
        }

        if (col != Matrix24::kSize) {
            throw std::runtime_error("matrix CSV row does not have 24 columns: " + path.string());
        }
        ++row;
    }

    if (row != Matrix24::kSize) {
        throw std::runtime_error("matrix CSV does not have 24 rows: " + path.string());
    }

    return matrix;
}

void writeMatrix24Csv(const Matrix24& matrix, const std::filesystem::path& path) {
    if (path.has_parent_path()) {
        std::filesystem::create_directories(path.parent_path());
    }

    std::ofstream output(path);
    if (!output) {
        throw std::runtime_error("failed to write matrix CSV: " + path.string());
    }

    output << std::setprecision(17);
    for (std::size_t i = 0; i < Matrix24::kSize; ++i) {
        for (std::size_t j = 0; j < Matrix24::kSize; ++j) {
            if (j > 0) {
                output << ",";
            }
            output << matrix(i, j);
        }
        output << "\n";
    }
}

} // namespace fem::s4

