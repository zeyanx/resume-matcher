# FairCV 基础数据接入说明

> 配对基准、人工标注和权重实验的最新说明见 `data/BENCHMARK_CARD.md`。

来源：https://huggingface.co/datasets/OhMyKing/FairCV

FairCV 是用于简历筛选偏见研究的中文模拟简历数据集。数据卡当前报告约 144 万条记录、约 6.32 GB，
包含岗位、技能等级、招聘类型，以及年龄、性别、户口、婚姻、政治面貌和残障等敏感人口统计字段。

## 本项目的使用边界

- 只用于学术公平性审计、覆盖度检查和鲁棒性压力测试；
- 不作为真实录用结果或人工相关性标签；
- 不直接用于学习融合权重；
- 敏感属性仅用于聚合公平性审计，不进入匹配模型；
- 不把完整数据集或抽样数据提交到公开仓库、交付 ZIP 或线上应用；
- 数据卡声明仅限学术研究并禁止商业用途，且当前缺少标准机器可读许可证。

使用 `scripts/prepare_faircv_baseline.py` 可按固定种子抽样。输出位于被 Git 忽略的
`data/external/faircv/`，同时生成来源、时间、种子和 SHA-256 清单。

```powershell
python scripts\prepare_faircv_baseline.py --sample-size 500 --seed 42
```

公开网页中的“基础数据与公平性”页面只读取最多 100 条临时样本并展示聚合分布，不显示或保存单条简历。
