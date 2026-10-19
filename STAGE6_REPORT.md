# 阶段 6 完成报告：优化建议与报告导出

## 1. 阶段目标

- 基于规则、技能差距和模板生成 3–5 条具体建议；
- 不依赖大语言模型 API；
- 不生成简历中不存在的经历、技能或指标；
- 支持 Markdown 和 TXT 分析报告导出；
- 报告包含生成时间、各项得分、技能差距、经历关键词、建议和算法说明。

## 2. 新增或修改文件

- `models/suggestion.py`：建议数据结构与确定性规则引擎。
- `utils/report_exporter.py`：文本签名、Markdown/TXT 渲染和安全文件名。
- `pages/3_简历优化建议.py`：建议展示、报告预览和下载页面。
- `app.py`：保存与当前简历、JD 绑定的最近分析结果，供建议页面安全复用。
- `tests/test_suggestion.py`：建议数量、条件措辞和防止估造指标测试。
- `tests/test_report_exporter.py`：报告必备内容、纯文本转换、签名和文件名测试。
- `tests/test_suggestion_page.py`：页面生成及双格式下载冒烟测试。
- `README.md`：补充阶段 6 使用说明和边界。

## 3. 实际运行命令

```powershell
$env:PYTHONIOENCODING='utf-8'
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pytest -q
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m compileall -q app.py models utils tests scripts evaluation pages
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pip check
```

网页启动命令：

```powershell
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m streamlit run app.py --server.port 8501
```

## 4. 真实验证结果

- 自动化测试：`68 passed`。
- 已知警告：PyMuPDF 的 5 条 SWIG 类型弃用警告，不影响阶段 6 功能。
- Python 编译检查：通过。
- 依赖一致性检查：`No broken requirements found.`
- Streamlit 健康检查：HTTP 200 和 `ok`。
- Markdown 与 TXT 下载控件页面测试：通过。

对仓库内合成简历与合成 JD 实际运行建议引擎：

- 建议数量：4；
- 高优先级：核对并处理岗位缺失技能；
- 高优先级：补强与岗位职责对应的经历证据；
- 中优先级：补充可核实的结果证据；
- 中优先级：把已匹配职责写成证据链；
- Markdown 报告长度：1,081 个字符；
- TXT 报告长度：1,048 个字符；
- 导出内容包含完整原始简历：否。

以上检查只验证程序行为和合成样例输出，不代表建议能提高真实录用概率。

## 5. 防止虚构的实现边界

- 缺失技能建议明确使用“若你确实使用过”并要求补充真实证据；否则作为学习方向，不写成已掌握。
- 缺失经历建议使用条件表达；没有相关经历时明确要求不要虚构。
- 未检测到数字时，只建议在存在可核实记录的情况下补充，不生成任何数值。
- 不可靠工作年限继续显示“未识别”，不从含糊文本推断。
- 建议页面用文本 SHA-256 摘要校验最近分析结果；文本变化后不会复用旧 BGE 或融合分。
- 导出报告不写入完整简历或 JD 正文。

## 6. 尚未完成

- 尚未实现阶段 7 的正式评估指标和图表。
- 尚无真实人工标注测试集，不能报告真实相关性或排序性能。
- 尚未对建议质量进行人工评分或用户研究。
- 当前报告只支持 Markdown/TXT，不包含 PDF 或 Word 导出。

## 7. 常见问题

- **报告缺少 BGE 或融合分**：先在主页面对相同文本完成一次匹配，再进入建议页面；文本不同则旧结果不会被复用。
- **建议提到缺失技能**：这不是让用户声称已掌握；页面会要求只有在确有经历时才补充证据。
- **下载 TXT 出现乱码**：系统生成的 TXT 使用 UTF-8 BOM；请用支持 UTF-8 的编辑器打开。
- **建议少于预期**：规则引擎固定补足至少 3 条、最多 5 条；若异常可运行测试定位。
- **主页面内容更新后建议仍是旧文本**：点击“从主页面同步最新文本”。

## 8. 验收清单

- [x] 输出 3–5 条具体建议。
- [x] 每条建议包含标题、行动、依据和优先级。
- [x] 不调用大语言模型 API。
- [x] 缺失技能和经历使用条件措辞。
- [x] 不生成虚假数字、年限或项目。
- [x] 支持 Markdown 下载。
- [x] 支持 TXT 下载。
- [x] 报告包含生成时间、分数、差距、建议和算法说明。
- [x] 报告不附带完整原始简历或 JD。
- [x] 文本变化时阻止复用旧分析结果。

## 9. 下一阶段入口

阶段 7 可建立 `evaluation/evaluate.py`，在真实人工标注数据到位后计算 Pearson、Spearman、NDCG@5、MRR 和可选分类指标，并生成算法对比、雷达图、权重实验、消融实验和分类别结果。若数据仍未完成标注，只能验证评估代码和明确标记的合成演示流程，不能报告真实性能。
