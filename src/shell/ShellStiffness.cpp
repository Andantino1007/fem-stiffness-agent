#include "shell/ShellStiffness.hpp"

#include <algorithm>
#include <array>
#include <cmath>
#include <stdexcept>
#include <string>

namespace shell {
namespace {

constexpr std::size_t kNodeCount = 4;
constexpr std::size_t kDofPerNode = 6;
constexpr std::size_t kElementDof = kNodeCount * kDofPerNode;
constexpr double kShearCorrection = 5.0 / 6.0;
constexpr double kDrillingPenalty = 0.0085;
constexpr double kGeometryTolerance = 1.0e-12;

using Vector3 = std::array<double, 3>;
using Matrix2 = std::array<std::array<double, 2>, 2>;
using Matrix3 = std::array<std::array<double, 3>, 3>;
using BMatrix2 = std::array<std::array<double, kElementDof>, 2>;
using BMatrix3 = std::array<std::array<double, kElementDof>, 3>;

struct LocalGeometry {
    std::array<std::array<double, 2>, kNodeCount> coordinates{};
    std::array<Vector3, 3> basis{};
};

struct ShapeData {
    std::array<double, kNodeCount> values{};
    std::array<double, kNodeCount> dNdx{};
    std::array<double, kNodeCount> dNdy{};
    double detJ{};
};

Vector3 subtract(const Vector3& left, const Vector3& right) {
    return {left[0] - right[0], left[1] - right[1], left[2] - right[2]};
}

double dot(const Vector3& left, const Vector3& right) {
    return left[0] * right[0] + left[1] * right[1] + left[2] * right[2];
}

Vector3 cross(const Vector3& left, const Vector3& right) {
    return {
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    };
}

double norm(const Vector3& value) {
    return std::sqrt(dot(value, value));
}

Vector3 normalize(const Vector3& value, const char* label) {
    const double length = norm(value);
    if (!std::isfinite(length) || length <= kGeometryTolerance) {
        throw std::runtime_error(std::string("invalid shell geometry: ") + label);
    }
    return {value[0] / length, value[1] / length, value[2] / length};
}

Vector3 nodeCoordinate(const Node& node) {
    return {node.coord[0], node.coord[1], node.coord[2]};
}

void validateInput(const ShellElementInput& input) {
    if (input.nodes.size() != kNodeCount) {
        throw std::runtime_error("shell stiffness requires exactly 4 nodes");
    }
    if (!std::isfinite(input.youngModulus) || input.youngModulus <= 0.0) {
        throw std::runtime_error("Young's modulus must be positive and finite");
    }
    if (!std::isfinite(input.poissonRatio) || input.poissonRatio <= -1.0 || input.poissonRatio >= 0.5) {
        throw std::runtime_error("Poisson ratio must be in (-1, 0.5)");
    }
    if (!std::isfinite(input.thickness) || input.thickness <= 0.0) {
        throw std::runtime_error("shell thickness must be positive and finite");
    }
}

LocalGeometry buildLocalGeometry(const ShellElementInput& input) {
    const Vector3 origin = nodeCoordinate(input.nodes[0]);
    const Vector3 edge12 = subtract(nodeCoordinate(input.nodes[1]), origin);
    const Vector3 edge14 = subtract(nodeCoordinate(input.nodes[3]), origin);

    LocalGeometry geometry;
    geometry.basis[0] = normalize(edge12, "node 1 and node 2 coincide");
    geometry.basis[2] = normalize(cross(edge12, edge14), "nodes are collinear");
    geometry.basis[1] = normalize(cross(geometry.basis[2], geometry.basis[0]), "local y axis is invalid");

    double characteristicLength = 0.0;
    for (std::size_t node = 0; node < kNodeCount; ++node) {
        const Vector3 relative = subtract(nodeCoordinate(input.nodes[node]), origin);
        geometry.coordinates[node] = {dot(relative, geometry.basis[0]), dot(relative, geometry.basis[1])};
        characteristicLength = std::max(characteristicLength, norm(relative));
        const double outOfPlane = std::abs(dot(relative, geometry.basis[2]));
        if (outOfPlane > 1.0e-9 * std::max(1.0, characteristicLength)) {
            throw std::runtime_error("shell stiffness implementation currently requires a planar quadrilateral");
        }
    }
    return geometry;
}

ShapeData evaluateShape(const LocalGeometry& geometry, double xi, double eta) {
    ShapeData shape;
    shape.values = {
        0.25 * (1.0 - xi) * (1.0 - eta),
        0.25 * (1.0 + xi) * (1.0 - eta),
        0.25 * (1.0 + xi) * (1.0 + eta),
        0.25 * (1.0 - xi) * (1.0 + eta),
    };
    const std::array<double, kNodeCount> dNdxi = {
        -0.25 * (1.0 - eta),
        0.25 * (1.0 - eta),
        0.25 * (1.0 + eta),
        -0.25 * (1.0 + eta),
    };
    const std::array<double, kNodeCount> dNdeta = {
        -0.25 * (1.0 - xi),
        -0.25 * (1.0 + xi),
        0.25 * (1.0 + xi),
        0.25 * (1.0 - xi),
    };

    double dxDxi = 0.0;
    double dyDxi = 0.0;
    double dxDeta = 0.0;
    double dyDeta = 0.0;
    for (std::size_t node = 0; node < kNodeCount; ++node) {
        dxDxi += dNdxi[node] * geometry.coordinates[node][0];
        dyDxi += dNdxi[node] * geometry.coordinates[node][1];
        dxDeta += dNdeta[node] * geometry.coordinates[node][0];
        dyDeta += dNdeta[node] * geometry.coordinates[node][1];
    }

    shape.detJ = dxDxi * dyDeta - dyDxi * dxDeta;
    if (!std::isfinite(shape.detJ) || shape.detJ <= kGeometryTolerance) {
        throw std::runtime_error("shell element Jacobian must be positive; check node order and geometry");
    }

    for (std::size_t node = 0; node < kNodeCount; ++node) {
        shape.dNdx[node] = (dyDeta * dNdxi[node] - dyDxi * dNdeta[node]) / shape.detJ;
        shape.dNdy[node] = (-dxDeta * dNdxi[node] + dxDxi * dNdeta[node]) / shape.detJ;
    }
    return shape;
}

Matrix3 planeStressMatrix(double coefficient, double poissonRatio) {
    Matrix3 matrix{};
    matrix[0][0] = coefficient;
    matrix[0][1] = coefficient * poissonRatio;
    matrix[1][0] = coefficient * poissonRatio;
    matrix[1][1] = coefficient;
    matrix[2][2] = coefficient * (1.0 - poissonRatio) * 0.5;
    return matrix;
}

template <std::size_t StrainSize>
void addBtDB(Matrix24& stiffness,
             const std::array<std::array<double, kElementDof>, StrainSize>& matrixB,
             const std::array<std::array<double, StrainSize>, StrainSize>& material,
             double scale) {
    for (std::size_t row = 0; row < kElementDof; ++row) {
        for (std::size_t col = 0; col < kElementDof; ++col) {
            double value = 0.0;
            for (std::size_t i = 0; i < StrainSize; ++i) {
                for (std::size_t j = 0; j < StrainSize; ++j) {
                    value += matrixB[i][row] * material[i][j] * matrixB[j][col];
                }
            }
            stiffness(row, col) += scale * value;
        }
    }
}

void addDrillingPenalty(Matrix24& stiffness, const ShapeData& shape, double scale) {
    std::array<double, kElementDof> matrixB{};
    for (std::size_t node = 0; node < kNodeCount; ++node) {
        const std::size_t base = node * kDofPerNode;
        matrixB[base + 5] = shape.values[node];
    }
    for (std::size_t row = 0; row < kElementDof; ++row) {
        for (std::size_t col = 0; col < kElementDof; ++col) {
            stiffness(row, col) += scale * matrixB[row] * matrixB[col];
        }
    }
}

Matrix24 addMatrices(const Matrix24& left, const Matrix24& right) {
    Matrix24 result;
    for (std::size_t row = 0; row < kElementDof; ++row) {
        for (std::size_t col = 0; col < kElementDof; ++col) {
            result(row, col) = left(row, col) + right(row, col);
        }
    }
    return result;
}

Matrix24 transformToGlobal(const Matrix24& local, const LocalGeometry& geometry) {
    std::array<std::array<double, kElementDof>, kElementDof> transform{};
    for (std::size_t node = 0; node < kNodeCount; ++node) {
        const std::size_t base = node * kDofPerNode;
        for (std::size_t localAxis = 0; localAxis < 3; ++localAxis) {
            for (std::size_t globalAxis = 0; globalAxis < 3; ++globalAxis) {
                transform[base + localAxis][base + globalAxis] = geometry.basis[localAxis][globalAxis];
                transform[base + 3 + localAxis][base + 3 + globalAxis] =
                    geometry.basis[localAxis][globalAxis];
            }
        }
    }

    Matrix24 global;
    for (std::size_t row = 0; row < kElementDof; ++row) {
        for (std::size_t col = 0; col < kElementDof; ++col) {
            double value = 0.0;
            for (std::size_t localRow = 0; localRow < kElementDof; ++localRow) {
                if (transform[localRow][row] == 0.0) {
                    continue;
                }
                for (std::size_t localCol = 0; localCol < kElementDof; ++localCol) {
                    value += transform[localRow][row] * local(localRow, localCol) * transform[localCol][col];
                }
            }
            global(row, col) = value;
        }
    }
    return global;
}

ShellStiffnessComponents computeLocalComponents(const ShellElementInput& input, const LocalGeometry& geometry) {
    ShellStiffnessComponents components;
    const double elasticDenominator = 1.0 - input.poissonRatio * input.poissonRatio;
    const Matrix3 membraneMaterial =
        planeStressMatrix(input.youngModulus * input.thickness / elasticDenominator, input.poissonRatio);
    const Matrix3 bendingMaterial = planeStressMatrix(
        input.youngModulus * std::pow(input.thickness, 3) / (12.0 * elasticDenominator), input.poissonRatio);
    const double shearModulus = input.youngModulus / (2.0 * (1.0 + input.poissonRatio));
    Matrix2 shearMaterial{};
    // Abaqus S4 对齐：仅降低横向剪切 gamma_xz/gamma_yz 的有效本构刚度。
    const double transverseShearStiffness = (2.0 / 3.0) * kShearCorrection * shearModulus * input.thickness;
    shearMaterial[0][0] = transverseShearStiffness;
    shearMaterial[1][1] = transverseShearStiffness;

    constexpr double gauss = 0.57735026918962576451;
    const std::array<std::array<double, 2>, 4> integrationPoints = {
        std::array<double, 2>{-gauss, -gauss},
        std::array<double, 2>{gauss, -gauss},
        std::array<double, 2>{gauss, gauss},
        std::array<double, 2>{-gauss, gauss},
    };

    const ShapeData membraneAssumed = evaluateShape(geometry, 0.0, 0.0);
    for (const auto& point : integrationPoints) {
        const ShapeData shape = evaluateShape(geometry, point[0], point[1]);
        BMatrix3 membraneB{};
        BMatrix3 bendingB{};
        for (std::size_t node = 0; node < kNodeCount; ++node) {
            const std::size_t base = node * kDofPerNode;
            membraneB[0][base] = shape.dNdx[node];
            membraneB[1][base + 1] = shape.dNdy[node];
            membraneB[2][base] = shape.dNdy[node];
            membraneB[2][base + 1] = shape.dNdx[node];

            bendingB[0][base + 4] = shape.dNdx[node];
            bendingB[1][base + 3] = -shape.dNdy[node];
            bendingB[2][base + 3] = -shape.dNdx[node];
            bendingB[2][base + 4] = shape.dNdy[node];
        }
        // 膜内 assumed-strain：仅投影 gamma_xy 的寄生双线性扰动，保留 eps_x/eps_y 基本拉伸项。
        for (std::size_t node = 0; node < kNodeCount; ++node) {
            const std::size_t base = node * kDofPerNode;
            membraneB[2][base] = membraneAssumed.dNdy[node];
            membraneB[2][base + 1] = membraneAssumed.dNdx[node];
        }
        addBtDB(components.membrane, membraneB, membraneMaterial, shape.detJ);
        addBtDB(components.bending, bendingB, bendingMaterial, shape.detJ);
        addDrillingPenalty(
            components.drilling, shape, kDrillingPenalty * shearModulus * input.thickness * shape.detJ);
    }

    // 横向剪切改用同一 shearB 的 2x2 积分，以保留 uz 相邻耦合结构。
    for (const auto& point : integrationPoints) {
        const ShapeData shape = evaluateShape(geometry, point[0], point[1]);
        BMatrix2 shearB{};
        for (std::size_t node = 0; node < kNodeCount; ++node) {
            const std::size_t base = node * kDofPerNode;
            shearB[0][base + 2] = shape.dNdx[node];
            shearB[0][base + 4] = shape.values[node];
            shearB[1][base + 2] = shape.dNdy[node];
            shearB[1][base + 3] = -shape.values[node];
        }
        addBtDB(components.shear, shearB, shearMaterial, shape.detJ);
    }

    components.total = addMatrices(addMatrices(components.membrane, components.bending),
                                   addMatrices(components.shear, components.drilling));
    return components;
}

} // namespace

ShellStiffnessComponents computeShellElementStiffnessComponents(const ShellElementInput& input) {
    validateInput(input);
    const LocalGeometry geometry = buildLocalGeometry(input);
    const ShellStiffnessComponents local = computeLocalComponents(input, geometry);

    ShellStiffnessComponents global;
    global.membrane = transformToGlobal(local.membrane, geometry);
    global.bending = transformToGlobal(local.bending, geometry);
    global.shear = transformToGlobal(local.shear, geometry);
    global.drilling = transformToGlobal(local.drilling, geometry);
    global.total = transformToGlobal(local.total, geometry);
    return global;
}

Matrix24 computeShellElementStiffness(const ShellElementInput& input) {
    return computeShellElementStiffnessComponents(input).total;
}

} // namespace shell
