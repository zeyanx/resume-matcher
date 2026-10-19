# 阶段 0：需求确认与环境检查

## 1. 阶段目标

本阶段只完成需求边界、运行环境、依赖基线、工程结构、数据方案和阶段 1 验收标准的确认，不实现 Streamlit 页面或匹配算法。

项目最终目标是完成一个可在 Windows、PyCharm 和 Python 3.10 环境中运行的中文简历—岗位匹配系统，并提供可复现的算法实验、网页演示、报告导出和 ZIP 工程。

## 2. 当前环境检查结果

- 当前工作区在检查前仅有 `work/` 和 `outputs/`，没有既有项目代码或数据。
- 系统命令 `python` 当前指向 Python 3.14.8，不符合项目指定的 Python 3.10。
- Miniconda 已安装在 `C:\ProgramData\miniconda3`，版本为 26.7.1，但当前 PowerShell 没有把 `conda` 加入 PATH。
- 当前已有 Conda 环境中没有 `resume_match`。
- 系统全局 Python 3.14 环境没有安装本项目需要的 Streamlit、PyMuPDF、python-docx、jieba、scikit-learn、PyTorch、Transformers、sentence-transformers、pandas、NumPy、SciPy、Plotly、Matplotlib 和 pytest。
- Git 2.53.0.windows.3 可用。

结论：必须创建隔离的 Python 3.10 环境，不能直接使用当前全局 Python 3.14。

## 3. Conda 环境创建命令

请在 PowerShell 中进入本项目目录后执行：

```powershell
Set-Location "C:\Users\XUSITIAN\Documents\Codex\2026-10-19\new-chat\ResumeMatcher"
& "C:\ProgramData\miniconda3\Scripts\conda.exe" env create -f environment.yml
& "C:\ProgramData\miniconda3\Scripts\conda.exe" run -n resume_match python --version
& "C:\ProgramData\miniconda3\Scripts\conda.exe" run -n resume_match python -m pip check
```

若希望在当前 PowerShell 中使用 `conda activate`：

```powershell
& "C:\ProgramData\miniconda3\shell\condabin\conda-hook.ps1"
conda activate resume_match
```

在 PyCharm 中选择解释器时，应选择：

```text
C:\ProgramData\miniconda3\envs\resume_match\python.exe
```

如果 Conda 将环境创建到用户环境目录，应以以下命令输出的实际路径为准：

```powershell
& "C:\ProgramData\miniconda3\Scripts\conda.exe" env list
```

## 4. 依赖策略

- `requirements.txt` 固定阶段 0 的兼容版本，便于复现。
- `environment.yml` 固定 Python 3.10，并通过 pip 安装同一份依赖清单，避免维护两套版本。
- 选择 `scikit-learn 1.7.2`、`SciPy 1.15.3` 和 `NumPy 2.2.6`，是因为后续版本已逐步停止支持 Python 3.10。
- BGE 方案采用 `sentence-transformers`、`transformers` 和 `torch`，不从头训练模型。
- 阶段 1 创建环境后必须执行 `python -m pip check` 和导入检查。若实际解析器或模型出现兼容问题，应以可复现的实测结果调整版本并记录原因。
- 默认先保证 CPU 可运行。是否安装 CUDA 版 PyTorch，应根据实际显卡、驱动和 CUDA 状态单独决定，不能预设。

## 5. 总体实施计划

1. 阶段 1：TXT 简历、jieba、TF-IDF 和最简 Streamlit 闭环。
2. 阶段 2：PDF、DOCX、TXT 统一解析与异常处理。
3. 阶段 3：BGE 语义匹配、模型缓存、离线加载和降级说明。
4. 阶段 4：技能词典、同义词归一化、技能覆盖率和缺口分析。
5. 阶段 5：多特征融合、验证集权重搜索和权重结果保存。
6. 阶段 6：规则化优化建议与 Markdown/TXT 报告导出。
7. 阶段 7：相关性、NDCG@5、MRR、可选分类指标、消融实验和图表。
8. 阶段 8：全量验证、README、ZIP、论文素材和一分钟演示脚本。

## 6. 计划中的最终工程结构

```text
ResumeMatcher/
├── app.py
├── requirements.txt
├── environment.yml
├── README.md
├── .gitignore
├── pages/
│   ├── 1_智能匹配分析.py
│   ├── 2_技能差距分析.py
│   └── 3_简历优化建议.py
├── models/
│   ├── __init__.py
│   ├── tfidf_matcher.py
│   ├── bge_matcher.py
│   └── fusion_matcher.py
├── utils/
│   ├── __init__.py
│   ├── text_preprocessor.py
│   ├── resume_parser.py
│   ├── skill_extractor.py
│   ├── suggestion.py
│   └── report_exporter.py
├── data/
│   ├── DATA_CARD.md
│   ├── skills.json
│   ├── sample_resumes/
│   ├── sample_jds/
│   ├── jd_corpus/
│   ├── resumes/
│   └── test_cases.csv
├── evaluation/
│   ├── __init__.py
│   └── evaluate.py
├── tests/
│   ├── test_parser.py
│   ├── test_skill_extractor.py
│   └── test_matchers.py
├── reports/
│   └── .gitkeep
└── assets/
    └── style.css
```

与原建议相比增加 `data/DATA_CARD.md`，用于记录数据来源、许可状态、合成数据标记、人工标注方法和划分规则。Streamlit 的首页由 `app.py` 承担，其余三个文件组成四个功能页面。

## 7. 数据准备方案

### 7.1 岗位 JD

- 目标数量为 200–500 条，覆盖 5–8 类岗位。
- 优先级：合法公开数据集或允许访问的公开页面，其次是人工整理，最后才是明确标记的合成 JD。
- 每条数据保留 `jd_id`、岗位类别、标题、职责、要求、技能、地点、可选薪资、来源、获取日期、许可或使用说明。
- 不绕过登录、验证码、反爬或访问控制。

### 7.2 合成简历

- 目标数量为 50–100 份。
- 所有记录明确标记 `is_synthetic=true`，使用虚拟姓名、虚拟组织和可追溯的生成配置。
- 每类岗位覆盖优秀、中等、偏弱等不同匹配水平，但这些分级不能替代人工相关性标注。

### 7.3 人工标注样本

- 目标数量为 100–200 个简历—JD 配对。
- 使用 0、1、2、3 四级相关性标签。
- 在数据层面明确区分 `validation` 和 `test`，只用验证集选择融合权重，测试集只用于最终报告。
- 保留 `annotation_note`，记录打分依据；条件允许时采用两人独立标注并报告一致性。
- 在人工标注完成前，只能生成待标注模板和功能演示数据，不得声称得到真实模型性能。

### 7.4 数据隐私

- 演示工程默认不包含未经授权的真实简历。
- 上传文本只在当前会话中处理，不写入日志；如后续增加持久化，必须提供显式开关和删除机制。
- 报告和截图不得泄露姓名、电话、邮箱、身份证号等个人信息。

## 8. 阶段 1 验收条件

- 已创建并实际使用 `resume_match` Python 3.10 环境。
- `python -m pip check` 无依赖冲突，核心依赖可以导入。
- 项目骨架、`.gitignore`、README 初稿和测试目录已建立。
- TXT 文件可读取，空文件、非 UTF-8 文本和超长文本有明确处理。
- jieba 分词结果可测试、可复现。
- TF-IDF + 余弦相似度返回范围明确的分数，并覆盖空输入、相同文本、无共同词等测试。
- Streamlit 页面可以上传 TXT、输入 JD 并显示 TF-IDF 分数。
- 至少执行 Python 编译检查、单元测试和一次 Streamlit 启动探测。
- 不包含 PDF/DOCX、BGE、融合评分等后续阶段功能。

## 9. 当前风险与处理原则

1. **Python 版本不匹配**：全局 Python 为 3.14.8；必须使用独立 Python 3.10 环境。
2. **Conda 未加入 PATH**：阶段 1 可直接使用 `C:\ProgramData\miniconda3\Scripts\conda.exe`，无需修改系统 PATH。
3. **依赖版本漂移**：先使用当前兼容基线，安装后以 `pip check`、导入检查和测试结果为准，不把“可解析”当作“已验证”。
4. **PyTorch 体积较大**：阶段 1 的 TF-IDF 最小闭环无需加载 BGE；环境创建可能仍需下载 PyTorch，必要时可在阶段 3 前再安装语义模型依赖。
5. **BGE 首次下载需要网络**：阶段 3 将记录缓存目录、模型快照和离线加载方法，并提供显式降级提示。
6. **数据真实性边界**：合成简历、演示配对和人工标注测试集必须分开，演示结果不得包装成真实实验结论。
7. **排序指标的数据结构**：NDCG@5 和 MRR 需要同一查询对应多个候选简历或 JD；数据构建时必须保留查询分组，不能把无分组的独立配对直接用于排序指标。
8. **权重数据泄漏**：融合权重只能在验证集选择，不能在测试集上搜索后再报告测试结果。
9. **个人信息保护**：默认使用合成或已获授权且去标识化的数据。

## 10. 阶段 0 验收结论

- 已明确项目范围和阶段边界。
- 已确认本机需要新建 Python 3.10 环境。
- 已形成 `requirements.txt` 和 `environment.yml` 初稿。
- Conda 对 `environment.yml` 的试解析成功，计划创建 Python 3.10.22 环境，未实际安装。
- pip 按 Windows x64、CPython 3.10 目标对除 jieba 外的完整依赖进行了模拟解析，未发现版本冲突。
- `jieba 0.42.1` 仅提供源码包，已单独完成构建元数据模拟检查；正常环境安装时将由 pip 构建 wheel。
- 已确定最终目录结构、数据方案和阶段 1 验收标准。
- 尚未创建 Conda 环境、安装依赖或实现任何业务代码；这些操作留待阶段 1。
