#pragma once

#include <array>
#include <filesystem>
#include <string>
#include <vector>

namespace shell {

struct Node {
    int id{};
    std::array<double, 3> coord{};
};

struct ShellElementInput {
    std::string sampleId;
    std::string elementType;
    std::string nodeOrder;
    std::vector<std::string> dofOrderPerNode;
    std::vector<Node> nodes;
    double youngModulus{};
    double poissonRatio{};
    double thickness{};
    std::filesystem::path abaqusMatrixPath;
    std::filesystem::path cppMatrixPath;
};

ShellElementInput readShellElementInput(const std::filesystem::path& path);

} // namespace shell

