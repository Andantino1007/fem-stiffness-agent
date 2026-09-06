#define CATCH_CONFIG_MAIN
#include "infra/catch.hpp"

#include "fem/s4/CsvMatrixIO.hpp"
#include "fem/s4/MatrixCompare.hpp"
#include "fem/s4/S4ElementInput.hpp"
#include "fem/s4/S4Stiffness.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

TEST_CASE("sample matrices can be compared", "[baseline]") {
    const auto input = fem::s4::readS4ElementInput("data/reference/abaqus/metadata/sample_001.json");
    const auto referenceMatrix = fem::s4::readMatrix24Csv(input.referenceMatrixPath);
    const auto implementationMatrix = fem::s4::readMatrix24Csv(input.implementationMatrixPath);

    REQUIRE(referenceMatrix.rows() == 24);
    REQUIRE(referenceMatrix.cols() == 24);
    REQUIRE(implementationMatrix.rows() == 24);
    REQUIRE(implementationMatrix.cols() == 24);

    const auto error = fem::s4::compareMatrix(implementationMatrix, referenceMatrix);
    REQUIRE(error.frobeniusRelative >= 0.0);
    REQUIRE(error.maxAbsolute >= 0.0);
    REQUIRE(error.maxRelativeEntry >= 0.0);
}

TEST_CASE("sample matrices are symmetric enough for the flow check", "[baseline]") {
    const auto input = fem::s4::readS4ElementInput("data/reference/abaqus/metadata/sample_001.json");
    const auto implementationMatrix = fem::s4::readMatrix24Csv(input.implementationMatrixPath);
    REQUIRE(fem::s4::symmetryError(implementationMatrix) < 1.0e-12);
}

TEST_CASE("S4 implementation assembles physical stiffness components", "[stiffness]") {
    const auto input = fem::s4::readS4ElementInput("data/reference/abaqus/metadata/sample_001.json");
    const auto components = fem::s4::computeS4StiffnessComponents(input);

    REQUIRE(fem::s4::symmetryError(components.membrane) < 1.0e-12);
    REQUIRE(fem::s4::symmetryError(components.bending) < 1.0e-12);
    REQUIRE(fem::s4::symmetryError(components.shear) < 1.0e-12);
    REQUIRE(fem::s4::symmetryError(components.drilling) < 1.0e-12);
    REQUIRE(fem::s4::symmetryError(components.total) < 1.0e-12);

    double largestDiagonal = 0.0;
    for (std::size_t index = 0; index < fem::s4::Matrix24::kSize; ++index) {
        REQUIRE(std::isfinite(components.total(index, index)));
        largestDiagonal = std::max(largestDiagonal, components.total(index, index));
    }
    REQUIRE(largestDiagonal > 1.0e8);
}

TEST_CASE("physical baseline improves on the placeholder matrix", "[stiffness]") {
    const auto input = fem::s4::readS4ElementInput("data/reference/abaqus/metadata/sample_001.json");
    const auto referenceMatrix = fem::s4::readMatrix24Csv(input.referenceMatrixPath);
    const auto implementationMatrix = fem::s4::computeS4Stiffness(input);
    const auto error = fem::s4::compareMatrix(implementationMatrix, referenceMatrix);

    REQUIRE(error.frobeniusRelative < 0.2);
}

TEST_CASE("S4 implementation preserves rigid translations", "[stiffness]") {
    const auto input = fem::s4::readS4ElementInput("data/reference/abaqus/metadata/sample_001.json");
    const auto matrix = fem::s4::computeS4Stiffness(input);

    for (std::size_t direction = 0; direction < 3; ++direction) {
        double largestResidual = 0.0;
        for (std::size_t row = 0; row < fem::s4::Matrix24::kSize; ++row) {
            double residual = 0.0;
            for (std::size_t node = 0; node < 4; ++node) {
                residual += matrix(row, node * 6 + direction);
            }
            largestResidual = std::max(largestResidual, std::abs(residual));
        }
        REQUIRE(largestResidual < 1.0e-6);
    }
}

TEST_CASE("S4 implementation accepts a warped quadrilateral", "[stiffness][warped]") {
    const auto input = fem::s4::readS4ElementInput("data/reference/abaqus/metadata/s4_train_003_node_down.json");
    const auto matrix = fem::s4::computeS4Stiffness(input);

    REQUIRE(fem::s4::symmetryError(matrix) < 1.0e-12);
    double largestAbsolute = 0.0;
    for (std::size_t row = 0; row < fem::s4::Matrix24::kSize; ++row) {
        for (std::size_t col = 0; col < fem::s4::Matrix24::kSize; ++col) {
            REQUIRE(std::isfinite(matrix(row, col)));
            largestAbsolute = std::max(largestAbsolute, std::abs(matrix(row, col)));
        }
    }
    REQUIRE(largestAbsolute > 0.0);
}

TEST_CASE("S4 implementation rejects invalid material input", "[stiffness]") {
    auto input = fem::s4::readS4ElementInput("data/reference/abaqus/metadata/sample_001.json");
    input.poissonRatio = 0.5;
    REQUIRE_THROWS_AS(fem::s4::computeS4Stiffness(input), std::runtime_error);
}
