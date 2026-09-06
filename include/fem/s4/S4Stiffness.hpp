#pragma once

#include "fem/s4/Matrix24.hpp"
#include "fem/s4/S4ElementInput.hpp"

namespace fem::s4 {

struct S4StiffnessComponents {
    Matrix24 membrane;
    Matrix24 bending;
    Matrix24 shear;
    Matrix24 drilling;
    Matrix24 total;
};

// 正式物理基线：四节点赖斯纳－明德林壳，包含膜、弯曲、
// 选择性减缩剪切和钻转罚刚度，并转换到全局坐标系。
S4StiffnessComponents computeS4StiffnessComponents(const S4ElementInput& input);
Matrix24 computeS4Stiffness(const S4ElementInput& input);

} // namespace fem::s4
