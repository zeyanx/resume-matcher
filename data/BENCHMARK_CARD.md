# FairCV 简历—公开 JD 配对基准

## 当前状态

- 固定种子：`20261019`
- FairCV 合成简历：60 份，覆盖 12 个岗位、5 个技能水平
- 公开中文 JD：300 条，每条只用于一个配对
- 配对：300 条；每份简历对应 5 个 JD
- 固定切分：验证集 60 条（12 个简历查询），测试集 240 条（48 个简历查询）
- 标签状态：`pending_human`

`data/test_cases.csv` 已包含 TF-IDF、BGE、技能覆盖和经历覆盖子分数，但
`relevance_label` 故意留空。模型分数只用于构造难度不同的候选池，不能当作人工标签。
因此当前不能报告 Spearman、NDCG@5、MRR 或“最优融合权重”。

## 数据来源

1. 合成简历：[OhMyKing/FairCV](https://huggingface.co/datasets/OhMyKing/FairCV)。
   数据卡限定学术研究使用并禁止商业使用；项目只保存源行号，完整简历在标注或演示时按行读取，
   受保护属性进入匹配器前会被移除。
2. 中文 JD：
   [wangzihaogithub/job-educational-parser-dataset-08-0-0805](https://huggingface.co/datasets/wangzihaogithub/job-educational-parser-dataset-08-0-0805)，
   使用 `default/test/2w_0716.csv`，数据集页面标注 Apache-2.0。

`data/test_cases.csv` 保存 JD 正文和两个来源的源行号，便于复核；不会把 FairCV 简历正文复制进仓库。

## 人工标注流程

1. 打开 Streamlit 的“人工标注”页面。
2. 每条同时阅读合成简历和 JD，按以下规则标注：
   - 0：核心岗位方向、主要技能和经历均不匹配；
   - 1：仅有少量通用技能或可迁移经历；
   - 2：岗位方向一致且覆盖主要要求，但有明显缺口；
   - 3：岗位方向、核心技能和主要经历高度一致。
3. 使用匿名代号，保存后定期下载 CSV。
4. 建议两名标注者独立完成，再对分歧样本复核并标为 `human_adjudicated`。
5. 只有所有标签均为 `human_labeled` 或 `human_adjudicated` 后，才能运行正式评估。

## 运行命令

```powershell
python evaluation\evaluate.py `
  --input data\test_cases_annotated.csv `
  --output-dir reports\faircv_human_labeled `
  --weight-step 0.1
```

权重只在 validation 切分上按 Spearman 最高选择；并列时依次比较 MAE、RMSE。
test 切分只用于最终一次评估。生成的结论仅适用于“FairCV 合成简历 + 此公开 JD 样本”，
不能外推为真实招聘准确率或录用概率。

## 复现与本地外部文件

`scripts/prepare_matching_benchmark.py` 负责重建配对集；
`scripts/score_benchmark_bge.py` 负责批量计算 BGE 分数。
完整抽取文本和原始 JD CSV 位于被 Git 忽略的 `data/external/`，不会进入公开仓库。

## 技能词典

`scripts/expand_skills_from_faircv.py` 扫描本地已抽取样本，并仅从人工审核的候选技能表中补词。
本次实际扫描 560 份去重简历，而不是 FairCV 全量约 6GB 数据；精确词频和新增项见
`data/skills_faircv_corpus_report.json`。
