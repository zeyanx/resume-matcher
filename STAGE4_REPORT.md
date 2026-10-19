# 阶段 4 完成报告：技能提取与差距分析

## 1. 阶段目标

在阶段 3 的多格式解析、TF-IDF 和 BGE 匹配基础上，增加可解释的技能层分析：

- 建立可扩展、版本化的技能词典；
- 支持中英文别名和常用缩写归一化；
- 保护 `Go`、`Java`、`py` 等短英文技能的匹配边界；
- 计算岗位技能覆盖率；
- 展示已匹配技能、缺失技能、简历额外技能和实际命中表达；
- 提供独立的 Streamlit“技能差距分析”页面。

## 2. 本阶段新增或修改文件

- `data/skills.json`：标准技能、类别和同义词词典。
- `utils/skill_extractor.py`：词典验证、文本归一化、边界安全提取和差距计算。
- `pages/2_技能差距分析.py`：独立技能分析页面。
- `tests/test_skill_extractor.py`：词典、同义词、边界和覆盖率单元测试。
- `tests/test_skill_page.py`：独立页面交互冒烟测试。
- `app.py`：主页面新增岗位技能覆盖率和简要差距结果。
- `assets/style.css`：技能标签样式。
- `README.md`、`data/DATA_CARD.md`：功能、定义和数据边界说明。

## 3. 实际运行命令

```powershell
$env:PYTHONIOENCODING='utf-8'
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pytest -q
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m compileall -q app.py models utils tests scripts pages
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pip check
```

网页启动命令：

```powershell
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m streamlit run app.py --server.port 8501
```

## 4. 真实验证结果

- 自动化测试：`46 passed`。
- 已知警告：PyMuPDF 的 5 条 SWIG 类型弃用警告，不影响本阶段功能。
- Python 编译检查：通过。
- Python 依赖一致性检查：`No broken requirements found.`
- Streamlit 健康地址：`http://127.0.0.1:8501/_stcore/health` 返回 HTTP 200 和 `ok`。
- Streamlit 根页面：`http://127.0.0.1:8501/` 返回 HTTP 200。

对仓库中的合成示例进行真实技能链路检查，得到：

- 简历识别技能：Docker、Flask、Git、Linux、MySQL、Python、RESTful API、单元测试；
- JD 识别技能：Django、Docker、Flask、Git、Linux、MySQL、Python、RESTful API；
- 已匹配技能：Docker、Flask、Git、Linux、MySQL、Python、RESTful API；
- 缺失技能：Django；
- 岗位技能覆盖率：`7 / 8 = 87.5%`。

以上结果只用于验证合成样例的程序链路，不是模型在真实招聘数据上的性能指标。

## 5. 尚未完成

- 尚未加入教育、经历、项目、年限等结构化特征。
- 尚未实现多特征融合评分和权重配置。
- 尚无人工标注的真实验证集或测试集。
- 尚未开展真实招聘场景的准确率、召回率、相关性或排序指标评估。

## 6. 常见问题

- **岗位技能显示“未识别”**：JD 没有命中当前词典。可在 `data/skills.json` 中增加标准技能及别名，然后重新运行。
- **技能被漏掉**：检查词典是否包含该写法、缩写或中英文别名。
- **短词误匹配**：英文别名使用字母数字边界，例如 `Go` 不会从 `Django` 或 `Google` 中被提取。
- **覆盖率不能代表胜任力**：它只统计文本中出现的词典技能，不考虑熟练度、年限、上下文否定或项目质量。
- **网页无法打开**：确认启动命令仍在运行，并访问 `http://localhost:8501`；若端口占用，可先结束旧进程或改用其他端口。

## 7. 验收清单

- [x] 技能词典可读取并验证重复名称和别名冲突。
- [x] 中英文同义词归一化为标准技能名。
- [x] 短英文别名具备边界保护。
- [x] 输出已匹配、缺失和额外技能。
- [x] 计算并解释岗位技能覆盖率。
- [x] 独立 Streamlit 页面展示颜色标签和归一化证据。
- [x] 主页面显示技能覆盖率概览。
- [x] 自动化测试、编译、依赖和网页健康检查通过。

## 8. 下一阶段入口

阶段 5 可实现结构化经历特征与多特征融合评分，并继续保留 TF-IDF、BGE 和技能覆盖率三个可解释子分数。融合权重应只在验证集上选择；在没有人工标注数据前，只能将权重标记为演示配置，不能报告真实效果提升。
