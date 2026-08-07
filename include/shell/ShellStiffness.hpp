#pragma once

#include "shell/Matrix24.hpp"
#include "shell/ShellElementInput.hpp"

namespace shell {

struct ShellStiffnessComponents {
    Matrix24 membrane;
    Matrix24 bending;
    Matrix24 shear;
    Matrix24 drilling;
    Matrix24 total;
};

// 正式物理基线：四节点赖斯纳－明德林壳，包含膜、弯曲、
// 选择性减缩剪切和钻转罚刚度，并转换到全局坐标系。
ShellStiffnessComponents computeShellElementStiffnessComponents(const ShellElementInput& input);
Matrix24 computeShellElementStiffness(const ShellElementInput& input);

} // namespace shell
