# 融合权重实验数据

`synthetic_fusion_scores.csv` 是明确标记为 `synthetic_demo` 的流程演示数据，不是人工标注的真实招聘数据，也不能用于声称算法性能或生产最优权重。

`synthetic_evaluation_scores.csv` 同样只用于验证完整评估接口、固定切分和字段结构。评估程序检测到 `synthetic_demo` 后，不会把 Pearson、Spearman、NDCG@5、MRR、分类指标或指标图保存为实验结果；相关 CSV 只保留表头，并记录“尚未形成有效实验结论”。

CSV 字段：

- `case_id`：唯一案例编号；
- `split`：只允许 `validation` 或 `test`；
- `relevance_label`：0–3 相关性标签；
- `semantic_score`、`skill_score`、`experience_score`：0–1 子分数；
- `data_status`：数据状态，例如 `synthetic_demo` 或未来的人工标注版本号。

网格搜索只允许使用 `validation` 选择权重，随后才在 `test` 上评估一次。真实实验应替换为独立人工标注数据，并保留标注说明、来源和版本。
