#pragma once

#include <array>
#include <filesystem>
#include <string>
#include <vector>

namespace fem::s4 {

struct Node {
    int id{};
    std::array<double, 3> coord{};
};

struct S4ElementInput {
    std::string sampleId;
    std::string elementType;
    std::string nodeOrder;
    std::vector<std::string> dofOrderPerNode;
    std::vector<Node> nodes;
    double youngModulus{};
    double poissonRatio{};
    double thickness{};
    std::filesystem::path referenceMatrixPath;
    std::filesystem::path implementationMatrixPath;
};

S4ElementInput readS4ElementInput(const std::filesystem::path& path);

} // namespace fem::s4

