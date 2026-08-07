# 壳单元数据集划分

`shell_stiffness.json` 是多样本验证的唯一划分清单。

- `train`：智能体可以查看诊断并据此规划和修改代码。
- `validation`：用于筛选候选补丁和防止训练集过拟合。
- `test`：锁定后只用于一次性最终验收，不把逐项诊断提供给开发智能体。

同一个样本不能同时出现在多个集合中。当前只有一个真实 Abaqus 导出样本，已放入训练集；验证集和测试集尚为空。批量验证会明确输出未就绪状态，不会伪造泛化验收结论。

新增真实基准后，把对应元数据路径加入 `test`，例如：

```json
{
  "schema_version": 1,
  "train": [
    "data/abaqus/meta/sample_001.json"
  ],
  "validation": [
    "data/abaqus/meta/sample_050.json"
  ],
  "test": [
    "data/abaqus/meta/sample_101.json"
  ]
}
```

运行全部已配置样本：

```bash
python -m shell_agent verify-dataset
```

最终验收要求验证集、测试集和测试锁全部就绪：

```bash
python -m shell_agent verify-dataset --require-test
```

验证数据集规划：

```bash
python -m shell_agent validate-data-plan \
  data/datasets/plans/example_train_batch.json
```

真实 Abaqus 产物通过校验后登记：

```bash
python -m shell_agent register-sample \
  --meta data/abaqus/meta/sample_002.json \
  --split train
```

检查最终测试集锁：

```bash
python -m shell_agent check-test-lock
```

测试样本登记时会重建 `test-lock.json`。严格批量验收同时要求验证集非空、测试集非空且测试集文件哈希与锁一致。
