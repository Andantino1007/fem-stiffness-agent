#include "shell/ShellElementInput.hpp"

#include <fstream>
#include <regex>
#include <stdexcept>

namespace shell {
namespace {

std::string readText(const std::filesystem::path& path) {
    std::ifstream input(path);
    if (!input) {
        throw std::runtime_error("failed to open input JSON: " + path.string());
    }
    return {std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>()};
}

std::string matchString(const std::string& text, const std::string& key) {
    const std::regex pattern("\"" + key + "\"\\s*:\\s*\"([^\"]*)\"");
    std::smatch match;
    if (!std::regex_search(text, match, pattern)) {
        throw std::runtime_error("missing string field: " + key);
    }
    return match[1].str();
}

double matchNumber(const std::string& text, const std::string& key) {
    const std::regex pattern("\"" + key + "\"\\s*:\\s*(-?[0-9]+(?:\\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)");
    std::smatch match;
    if (!std::regex_search(text, match, pattern)) {
        throw std::runtime_error("missing numeric field: " + key);
    }
    return std::stod(match[1].str());
}

} // namespace

ShellElementInput readShellElementInput(const std::filesystem::path& path) {
    const std::string text = readText(path);

    ShellElementInput result;
    result.sampleId = matchString(text, "sample_id");
    result.elementType = matchString(text, "element_type");
    result.nodeOrder = matchString(text, "node_order");
    result.youngModulus = matchNumber(text, "E");
    result.poissonRatio = matchNumber(text, "nu");
    result.thickness = matchNumber(text, "thickness");
    result.abaqusMatrixPath = matchString(text, "abaqus_matrix");
    result.cppMatrixPath = matchString(text, "cpp_matrix");
    result.dofOrderPerNode = {"x", "y", "z", "rx", "ry", "rz"};

    const std::regex nodePattern(
        "\\{\"id\"\\s*:\\s*([0-9]+)\\s*,\\s*\"coord\"\\s*:\\s*\\[\\s*"
        "(-?[0-9]+(?:\\.[0-9]+)?)\\s*,\\s*"
        "(-?[0-9]+(?:\\.[0-9]+)?)\\s*,\\s*"
        "(-?[0-9]+(?:\\.[0-9]+)?)\\s*\\]\\s*\\}");

    for (std::sregex_iterator it(text.begin(), text.end(), nodePattern), end; it != end; ++it) {
        Node node;
        node.id = std::stoi((*it)[1].str());
        node.coord = {std::stod((*it)[2].str()), std::stod((*it)[3].str()), std::stod((*it)[4].str())};
        result.nodes.push_back(node);
    }

    if (result.nodes.size() != 4) {
        throw std::runtime_error("shell element input requires exactly 4 nodes");
    }
    if (result.thickness <= 0.0) {
        throw std::runtime_error("thickness must be positive");
    }
    if (result.youngModulus <= 0.0) {
        throw std::runtime_error("E must be positive");
    }

    return result;
}

} // namespace shell
