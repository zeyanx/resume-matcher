# 阶段 5 完成报告：融合评分与权重实验

## 1. 阶段目标

将 BGE 语义分、技能覆盖率和经历关键词覆盖率统一到 0–1，并实现可解释融合：

```text
S = α × S_semantic + β × S_skill + γ × S_experience
```

同时建立验证集选权重、隔离测试集评估、保存最佳权重和完整对比表的可复现实验链路。

## 2. 新增或修改文件

- `models/experience_matcher.py`：经历、职责和教育关键词提取及覆盖率。
- `data/experience_keywords.json`：版本化经历关键词词典。
- `models/fusion_matcher.py`：子分数验证、融合计算和权重配置加载。
- `config/fusion_weights.json`：`0.5 / 0.3 / 0.2` 初始展示配置，明确标注未经真实验证。
- `evaluation/weight_search.py`：权重网格生成、验证集选择、测试集评估和结果保存。
- `scripts/run_weight_experiment.py`：可直接运行的权重实验入口。
- `data/evaluation/synthetic_fusion_scores.csv`：8 条验证、4 条测试的合成演示分数。
- `data/evaluation/labeled_scores_template.csv`：真实人工标注实验模板。
- `reports/stage5_synthetic_demo/`：合成演示最佳权重和完整权重对比结果。
- `app.py`：增加经历关键词分、融合分、三项可调权重及权重来源说明。
- `tests/test_experience_matcher.py`、`tests/test_fusion_matcher.py`、`tests/test_weight_search.py`：阶段 5 测试。

## 3. 实际运行命令

```powershell
$env:PYTHONIOENCODING='utf-8'
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pytest -q
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m compileall -q app.py models utils tests scripts evaluation pages
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pip check
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" scripts\run_weight_experiment.py --input data\evaluation\synthetic_fusion_scores.csv --output-dir reports\stage5_synthetic_demo --step 0.1
```

## 4. 真实验证结果

- 自动化测试：`60 passed`。
- Python 编译检查：通过。
- 依赖一致性检查：通过。
- Streamlit 健康检查：`http://127.0.0.1:8501/_stcore/health` 返回 HTTP 200 和 `ok`。
- 本地 BGE 模型离线 CPU 推理：成功。

仓库合成简历与合成 JD 的实际程序输出：

- BGE 语义分：`0.894631`；
- 技能覆盖率：`0.875000`；
- 经历关键词覆盖率：`0.285714`；
- 使用界面初始权重 `0.5 / 0.3 / 0.2` 的融合分：`0.766958`；
- 配置验证状态：`false`。

这些数值只验证一组合成文本的计算链路，不是算法性能指标。

## 5. 合成权重实验结果与证据边界

网格步长为 0.1，共比较 66 组合法权重。合成演示数据上：

- 验证集记录：8 条；
- 隔离测试集记录：4 条；
- 按验证集 MAE 选择出的演示权重：`0.0 / 0.6 / 0.4`；
- 验证集 MAE：`0.067000`；
- 测试集 MAE：`0.073333`。

数据状态是 `synthetic_demo`。因此，该权重没有写入默认配置，也不得称为真实最优权重、性能提升或泛化证据。默认页面仍使用明确标记为未验证的 `0.5 / 0.3 / 0.2`。

## 6. 尚未完成

- 尚无 100–200 对真实人工标注的简历–JD 数据。
- 尚未确定可用于正式页面的验证集最优权重。
- 尚未报告真实 Pearson、Spearman、NDCG@5、MRR 或分类指标。
- 尚未实现阶段 6 的优化建议和报告导出。

## 7. 常见问题

- **融合评分不可用**：BGE、技能或经历子分数缺失，或者三个权重之和不等于 1。
- **经历分较低**：该分数只覆盖词典内明确出现的经历或职责关键词，不推断语义上隐含的工作内容。
- **工作年限显示未识别**：这是有意的证据边界；当前实现不从含糊文本猜测年限。
- **合成实验出现语义权重为 0**：这是小型人为演示分数的结果，只说明网格搜索代码可运行，不说明 BGE 无效。
- **替换真实数据**：填写 `labeled_scores_template.csv` 对应字段，保持验证集和测试集分离，再运行实验脚本。

## 8. 验收清单

- [x] 三个子分数统一限制在 0–1。
- [x] 默认权重为 `0.5 / 0.3 / 0.2` 且和为 1。
- [x] 非法分数和非法权重会明确报错。
- [x] 经历或职责关键词覆盖率可解释。
- [x] 工作年限不可靠时明确标记“未识别”。
- [x] 网格搜索只使用验证集选择权重。
- [x] 测试集不参与权重选择。
- [x] 最佳权重和完整对比结果可保存。
- [x] 合成实验结果明确标注，不覆盖生产默认值。
- [x] 主页面展示五项分数和权重来源。

## 9. 下一阶段入口

阶段 6 可实现基于规则、技能差距和模板的 3–5 条简历优化建议，并增加 Markdown/TXT 报告导出。建议必须只基于当前文本证据，不生成简历中不存在的经历、学历或技能。
