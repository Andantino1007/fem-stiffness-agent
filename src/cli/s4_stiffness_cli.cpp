#include "fem/s4/CsvMatrixIO.hpp"
#include "fem/s4/MatrixCompare.hpp"
#include "fem/s4/S4ElementInput.hpp"
#include "fem/s4/S4Stiffness.hpp"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

namespace {

double matrixNorm(const fem::s4::Matrix24& matrix) {
    double squaredNorm = 0.0;
    for (std::size_t row = 0; row < fem::s4::Matrix24::kSize; ++row) {
        for (std::size_t col = 0; col < fem::s4::Matrix24::kSize; ++col) {
            squaredNorm += matrix(row, col) * matrix(row, col);
        }
    }
    return std::sqrt(squaredNorm);
}

void writeReport(const std::filesystem::path& path,
                 const fem::s4::S4ElementInput& input,
                 const fem::s4::S4StiffnessComponents& components,
                 const fem::s4::MatrixError& error) {
    if (path.has_parent_path()) {
        std::filesystem::create_directories(path.parent_path());
    }

    std::ofstream report(path);
    if (!report) {
        throw std::runtime_error("failed to write report: " + path.string());
    }

    report << "# S4 单元刚度验证报告：" << input.sampleId << "\n\n";
    report << "## 样本信息\n";
    report << "- element_type: " << input.elementType << "\n";
    report << "- node_order: " << input.nodeOrder << "\n";
    report << "- dof_order_per_node: x y z rx ry rz\n";
    report << "- E: " << input.youngModulus << "\n";
    report << "- nu: " << input.poissonRatio << "\n";
    report << "- thickness: " << input.thickness << "\n\n";

    report << "## 文件清单\n";
    report << "- Reference matrix: " << input.referenceMatrixPath.string() << "\n";
    report << "- Implementation matrix: " << input.implementationMatrixPath.string() << "\n\n";

    report << "## 分量 Frobenius 范数\n";
    report << "- membrane: " << matrixNorm(components.membrane) << "\n";
    report << "- bending: " << matrixNorm(components.bending) << "\n";
    report << "- shear: " << matrixNorm(components.shear) << "\n";
    report << "- drilling: " << matrixNorm(components.drilling) << "\n";
    report << "- total: " << matrixNorm(components.total) << "\n\n";

    report << "## 误差指标\n";
    report << "- Frobenius relative error: " << error.frobeniusRelative << "\n";
    report << "- max absolute error: " << error.maxAbsolute << "\n";
    report << "- max relative entry error: " << error.maxRelativeEntry << "\n";
    report << "- symmetry error: " << error.symmetryError << "\n\n";

    report << "## 指标说明\n";
    report << "逐项最大相对误差可能被 Abaqus 接近零的条目放大；"
              "Frobenius 相对误差用于衡量矩阵整体差异。\n";
}

} // namespace

int main(int argc, char** argv) {
    if (argc < 3) {
        std::cerr << "Usage: s4_stiffness_cli <sample_json> <report_path>\n";
        return 2;
    }

    try {
        const auto input = fem::s4::readS4ElementInput(argv[1]);
        const auto components = fem::s4::computeS4StiffnessComponents(input);
        fem::s4::writeMatrix24Csv(components.total, input.implementationMatrixPath);

        const auto referenceMatrix = fem::s4::readMatrix24Csv(input.referenceMatrixPath);
        const auto error = fem::s4::compareMatrix(components.total, referenceMatrix);
        writeReport(argv[2], input, components, error);

        std::cout << "S4 stiffness flow completed for " << input.sampleId << "\n";
        std::cout << "Frobenius relative error: " << error.frobeniusRelative << "\n";
        std::cout << "Report: " << argv[2] << "\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "S4 stiffness flow failed: " << ex.what() << "\n";
        return 1;
    }
}
