# 壳单元数据集划分

`shell_stiffness.json` 是多样本验证的唯一划分清单。

- `train`：Agent 可以查看诊断并据此规划、修改和筛选候选补丁。
- `test`：只用于检查泛化和最终验收，不应把逐项诊断提供给 Developer。

同一个样本不能同时出现在两个集合中。当前只有一个真实 Abaqus 导出样本，已放入训练集；
测试集为空时，批量验证会明确输出 `test_ready=false`，不会伪造测试集通过结论。

新增真实基准后，把对应元数据路径加入 `test`，例如：

```json
{
  "schema_version": 1,
  "train": [
    "data/abaqus/meta/sample_001.json"
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

最终验收要求测试集非空：

```bash
python -m shell_agent verify-dataset --require-test
```
