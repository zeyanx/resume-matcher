# 阶段 7 完成报告：评估实验与可视化

## 1. 阶段目标

- 建立统一的 `evaluation/evaluate.py` 评估入口；
- 支持 TF-IDF、BGE、融合评分和去除技能特征后的融合模型；
- 实现 Pearson、Spearman、NDCG@5、MRR 和可选二分类指标；
- 完成验证集权重搜索、消融、分类别结果、随机种子记录和错误案例分析；
- 真实数据到位时保存 CSV、JSON 和 PNG 图表；
- 没有真实人工标注时，不输出虚构的性能指标。

## 2. 新增或修改文件

- `evaluation/evaluate.py`：完整评估、指标、消融、分类别、错误案例和图表生成代码。
- `data/evaluation/synthetic_evaluation_scores.csv`：明确标记的流程测试数据。
- `pages/4_评估实验.py`：读取落盘结果并展示证据状态。
- `app.py`：新增 TF-IDF/BGE/融合评分柱状图和语义/技能/经历/关键词雷达图。
- `tests/test_evaluate.py`：切分隔离、指标边界和结果落盘测试。
- `tests/test_evaluation_page.py`：评估页面冒烟测试。
- `reports/stage7_synthetic_demo/`：当前合成状态下的空白指标模板、权重搜索演示、配置与运行摘要。
- `README.md`、`data/DATA_CARD.md`：评估运行方法和证据边界。

## 3. 实际运行命令

```powershell
$env:PYTHONIOENCODING='utf-8'
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pytest -q
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" evaluation\evaluate.py --input data\evaluation\synthetic_evaluation_scores.csv --output-dir reports\stage7_synthetic_demo --seed 42 --weight-step 0.1 --classification-threshold 0.5
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m compileall -q app.py models utils tests scripts evaluation pages
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pip check
```

## 4. 验证结果

- 自动化测试：`74 passed`。
- 已知警告：PyMuPDF 的 5 条 SWIG 类型弃用警告，不影响阶段 7 功能。
- 固定数据切分检查：12 条验证记录、12 条测试记录。
- 岗位类别：Python 后端、数据分析、产品经理。
- 查询组：6。
- 随机种子记录：42。
- Streamlit 主页面柱状图和雷达图代码已接入。
- 评估页面可读取报告状态并在指标为空时给出明确说明。

## 5. 当前实验结论

**尚未形成有效实验结论。**

当前只有标记为 `synthetic_demo` 的流程测试数据，因此：

- `metrics.csv` 只包含字段表头；
- `ablation_results.csv` 只包含字段表头；
- `category_metrics.csv` 只包含字段表头；
- `error_cases.csv` 只包含字段表头；
- 不生成 Pearson、Spearman、NDCG@5、MRR 或分类指标数值；
- 不生成基于合成标签的指标图；
- `best_config.json` 的正式 `weights` 为 `null`；
- `run_summary.json` 记录 `metrics_generated=false`。

合成数据仍会验证权重搜索程序并输出 `demo_grid_search_weights` 和 `weight_search.csv`，但这些只能证明程序链路工作，不能用于论文、答辩性能结论或页面默认权重。

## 6. 已实现但等待真实数据的指标

- Pearson 相关系数；
- Spearman 相关系数；
- 按 `query_id` 分组的 NDCG@5；
- 相关标签阈值为 2 的 MRR；
- 预测阈值可配置的 Accuracy、Precision、Recall、F1；
- MAE 和 RMSE；
- 分岗位类别指标；
- 融合与去除技能特征的消融对比；
- 按绝对误差排序的错误案例；
- 算法指标、消融误差和分类别融合误差 PNG 图表。

## 7. 常见问题

- **评估页面没有指标**：这是当前正确行为，因为数据是 `synthetic_demo`。
- **如何生成正式指标**：准备真实人工标注 CSV，保留固定的 `validation` 和 `test`，将 `data_status` 改为真实数据版本标识后运行评估。
- **为什么测试集不参与选权重**：权重只在验证集按 MAE 选择，测试集只用于最终一次评估，避免数据泄漏。
- **相关系数为空**：样本过少、真实标签为常量或预测为常量时，相关系数没有定义，程序返回空值而不是伪造 0。
- **NDCG/MRR 如何分组**：使用 `query_id` 表示同一 JD 下待排序的多份简历。
- **主页面图表与实验图表区别**：主页面展示单个当前案例的分数组成；实验图表比较固定测试集上的算法指标。

## 8. 验收清单

- [x] `evaluation/evaluate.py` 可独立运行。
- [x] 支持四种算法对比。
- [x] 实现 Pearson、Spearman、NDCG@5 和 MRR。
- [x] 实现 Accuracy、Precision、Recall 和 F1。
- [x] 验证集和测试集严格分离。
- [x] 保存权重搜索、配置、运行摘要和待填结果表。
- [x] 实现消融、分类别和错误案例代码。
- [x] 记录随机种子和数据切分策略。
- [x] 合成数据状态下拒绝输出正式指标和指标图。
- [x] 主页面新增算法柱状图和多维雷达图。
- [x] 独立评估页面展示当前证据状态。

## 9. 下一步

阶段 8 将进行完整工程验证、README 与环境说明复核、演示数据说明、ZIP 打包及内容校验，并生成论文大纲、实验章节素材和答辩演示脚本。所有材料将继续明确区分真实运行结果、合成数据和待完成的人工标注工作；不会用合成指标填补实验结论。
