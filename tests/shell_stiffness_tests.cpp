#define CATCH_CONFIG_MAIN
#include "infra/catch.hpp"

#include "shell/CsvMatrixIO.hpp"
#include "shell/MatrixCompare.hpp"
#include "shell/ShellElementInput.hpp"
#include "shell/ShellStiffness.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

TEST_CASE("sample matrices can be compared", "[baseline]") {
    const auto input = shell::readShellElementInput("data/abaqus/meta/sample_001.json");
    const auto abaqusMatrix = shell::readMatrix24Csv(input.abaqusMatrixPath);
    const auto cppMatrix = shell::readMatrix24Csv(input.cppMatrixPath);

    REQUIRE(abaqusMatrix.rows() == 24);
    REQUIRE(abaqusMatrix.cols() == 24);
    REQUIRE(cppMatrix.rows() == 24);
    REQUIRE(cppMatrix.cols() == 24);

    const auto error = shell::compareMatrix(cppMatrix, abaqusMatrix);
    REQUIRE(error.frobeniusRelative >= 0.0);
    REQUIRE(error.maxAbsolute >= 0.0);
    REQUIRE(error.maxRelativeEntry >= 0.0);
}

TEST_CASE("sample matrices are symmetric enough for the flow check", "[baseline]") {
    const auto input = shell::readShellElementInput("data/abaqus/meta/sample_001.json");
    const auto cppMatrix = shell::readMatrix24Csv(input.cppMatrixPath);
    REQUIRE(shell::symmetryError(cppMatrix) < 1.0e-12);
}

TEST_CASE("shell implementation assembles physical stiffness components", "[stiffness]") {
    const auto input = shell::readShellElementInput("data/abaqus/meta/sample_001.json");
    const auto components = shell::computeShellElementStiffnessComponents(input);

    REQUIRE(shell::symmetryError(components.membrane) < 1.0e-12);
    REQUIRE(shell::symmetryError(components.bending) < 1.0e-12);
    REQUIRE(shell::symmetryError(components.shear) < 1.0e-12);
    REQUIRE(shell::symmetryError(components.drilling) < 1.0e-12);
    REQUIRE(shell::symmetryError(components.total) < 1.0e-12);

    double largestDiagonal = 0.0;
    for (std::size_t index = 0; index < shell::Matrix24::kSize; ++index) {
        REQUIRE(std::isfinite(components.total(index, index)));
        largestDiagonal = std::max(largestDiagonal, components.total(index, index));
    }
    REQUIRE(largestDiagonal > 1.0e8);
}

TEST_CASE("physical baseline improves on the placeholder matrix", "[stiffness]") {
    const auto input = shell::readShellElementInput("data/abaqus/meta/sample_001.json");
    const auto abaqusMatrix = shell::readMatrix24Csv(input.abaqusMatrixPath);
    const auto cppMatrix = shell::computeShellElementStiffness(input);
    const auto error = shell::compareMatrix(cppMatrix, abaqusMatrix);

    REQUIRE(error.frobeniusRelative < 0.2);
}

TEST_CASE("shell implementation preserves rigid translations", "[stiffness]") {
    const auto input = shell::readShellElementInput("data/abaqus/meta/sample_001.json");
    const auto matrix = shell::computeShellElementStiffness(input);

    for (std::size_t direction = 0; direction < 3; ++direction) {
        double largestResidual = 0.0;
        for (std::size_t row = 0; row < shell::Matrix24::kSize; ++row) {
            double residual = 0.0;
            for (std::size_t node = 0; node < 4; ++node) {
                residual += matrix(row, node * 6 + direction);
            }
            largestResidual = std::max(largestResidual, std::abs(residual));
        }
        REQUIRE(largestResidual < 1.0e-6);
    }
}

TEST_CASE("shell implementation rejects invalid material input", "[stiffness]") {
    auto input = shell::readShellElementInput("data/abaqus/meta/sample_001.json");
    input.poissonRatio = 0.5;
    REQUIRE_THROWS_AS(shell::computeShellElementStiffness(input), std::runtime_error);
}
