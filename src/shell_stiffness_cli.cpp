#include "shell/CsvMatrixIO.hpp"
#include "shell/MatrixCompare.hpp"
#include "shell/ShellElementInput.hpp"
#include "shell/ShellStiffness.hpp"

#include <cmath>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <stdexcept>

namespace {

double matrixNorm(const shell::Matrix24& matrix) {
    double squaredNorm = 0.0;
    for (std::size_t row = 0; row < shell::Matrix24::kSize; ++row) {
        for (std::size_t col = 0; col < shell::Matrix24::kSize; ++col) {
            squaredNorm += matrix(row, col) * matrix(row, col);
        }
    }
    return std::sqrt(squaredNorm);
}

void writeReport(const std::filesystem::path& path,
                 const shell::ShellElementInput& input,
                 const shell::ShellStiffnessComponents& components,
                 const shell::MatrixError& error) {
    if (path.has_parent_path()) {
        std::filesystem::create_directories(path.parent_path());
    }

    std::ofstream report(path);
    if (!report) {
        throw std::runtime_error("failed to write report: " + path.string());
    }

    report << "# 壳单元刚度验证报告：" << input.sampleId << "\n\n";
    report << "## 样本信息\n";
    report << "- element_type: " << input.elementType << "\n";
    report << "- node_order: " << input.nodeOrder << "\n";
    report << "- dof_order_per_node: x y z rx ry rz\n";
    report << "- E: " << input.youngModulus << "\n";
    report << "- nu: " << input.poissonRatio << "\n";
    report << "- thickness: " << input.thickness << "\n\n";

    report << "## 文件清单\n";
    report << "- Abaqus matrix: " << input.abaqusMatrixPath.string() << "\n";
    report << "- C++ matrix: " << input.cppMatrixPath.string() << "\n\n";

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
        std::cerr << "Usage: shell_stiffness_cli <sample_json> <report_path>\n";
        return 2;
    }

    try {
        const auto input = shell::readShellElementInput(argv[1]);
        const auto components = shell::computeShellElementStiffnessComponents(input);
        shell::writeMatrix24Csv(components.total, input.cppMatrixPath);

        const auto abaqusMatrix = shell::readMatrix24Csv(input.abaqusMatrixPath);
        const auto error = shell::compareMatrix(components.total, abaqusMatrix);
        writeReport(argv[2], input, components, error);

        std::cout << "Shell stiffness flow completed for " << input.sampleId << "\n";
        std::cout << "Frobenius relative error: " << error.frobeniusRelative << "\n";
        std::cout << "Report: " << argv[2] << "\n";
        return 0;
    } catch (const std::exception& ex) {
        std::cerr << "Shell stiffness flow failed: " << ex.what() << "\n";
        return 1;
    }
}
