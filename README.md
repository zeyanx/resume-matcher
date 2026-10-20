# ResumeMatcher

基于多特征融合与语义向量的智能简历岗位匹配系统。

公开演示：https://resume-matcher-zeyanx.streamlit.app/

当前公开演示已开放匹配、技能差距、优化建议、评估实验、FairCV 基础数据审计和数据隐私页面。服务器端反馈收集在
配置持久化 PostgreSQL 与真实隐私联系人之前保持关闭。

阶段 0–8 已完成：上传 PDF、DOCX 或 TXT 简历，预览解析文本，输入岗位 JD，同时计算 TF-IDF 基线、`BAAI/bge-small-zh-v1.5` 语义匹配度、岗位技能覆盖率、经历关键词覆盖率和三特征融合评分。独立页面提供技能差距分析、3–5 条证据化优化建议、Markdown/TXT 报告导出，以及可复现的评估流程与结果页面。

## 文档索引

- `INSTALL.md`：安装、模型准备、运行和故障处理；
- `DEMO_GUIDE.md`：合成数据状态、四个页面和演示流程；
- `data/DATA_CARD.md`：数据来源与证据边界；
- `data/FAIRCV_INTEGRATION.md`：FairCV 学术数据的许可、抽样和敏感字段隔离规则；
- `THESIS_OUTLINE.md`：课程论文大纲；
- `EXPERIMENT_CHAPTER_MATERIAL.md`：实验章节方法、待填结果表和有效性威胁；
- `DEFENSE_DEMO_SCRIPT.md`：一分钟答辩演示脚本；
- `PRIVACY.md`：反馈收集、脱敏、自助删除与离线学习边界；
- `DEPLOYMENT.md`：GitHub、PostgreSQL 和 Streamlit Community Cloud 上线步骤；
- `STAGE8_REPORT.md`：最终验证与打包记录。

## 运行环境

- Windows
- Python 3.10
- Conda 环境：`resume_match`

## 创建环境

在 PowerShell 中进入本目录：

```powershell
conda env create -f environment.yml
conda activate resume_match
```

## 启动网页

```powershell
python -m streamlit run app.py
```

浏览器默认访问 `http://localhost:8501`。

## BGE 模型与离线运行

首次在线使用可以直接在页面中启用 BGE，模型会缓存到：

```text
models_cache/huggingface/
```

若需要准备标准的本地离线模型目录，运行：

```powershell
python scripts\download_bge_model.py
```

模型将保存到：

```text
models_cache/bge-small-zh-v1.5/
```

网页检测到该目录后会自动填入本地路径并默认启用“仅使用本地文件”。也可以通过环境变量配置：

```powershell
$env:RESUME_MATCHER_BGE_PATH="D:\models\bge-small-zh-v1.5"
$env:RESUME_MATCHER_HF_CACHE="D:\models\huggingface-cache"
$env:RESUME_MATCHER_OFFLINE="1"
```

如果模型缺失、网络失败或内存不足，网页会明确提示原因并降级为 TF-IDF，不会伪造 BGE 分数。

## 融合评分与权重实验

融合公式为：

```text
S = α × S_semantic + β × S_skill + γ × S_experience
```

页面初始权重为 `0.5 / 0.3 / 0.2`，配置位于 `config/fusion_weights.json`。该配置明确标记为“未经真实人工标注验证”，不能描述为最优权重。三个权重均可在侧栏调整，但权重和必须等于 1。

运行验证集权重网格搜索：

```powershell
python scripts\run_weight_experiment.py `
  --input data\evaluation\synthetic_fusion_scores.csv `
  --output-dir reports\stage5_synthetic_demo `
  --step 0.1
```

脚本只使用 `validation` 切分选择权重，然后在隔离的 `test` 切分上评估一次。仓库提供的数据被明确标记为 `synthetic_demo`，只验证实验流程，不能作为真实性能或生产最优权重证据。

## 优化建议与报告导出

在主页面完成匹配后，进入“简历优化建议”页面，可以：

- 从主页面同步简历和 JD，也可以直接粘贴文本；
- 生成 3–5 条带依据、优先级和具体行动的建议；
- 对缺失技能使用“若确实掌握再补充证据”的条件表达；
- 下载 UTF-8 Markdown 报告或带 BOM 的 TXT 报告；
- 在报告中查看生成时间、各项得分、技能差距、经历关键词、建议和算法说明。
- 对建议给出 1–5 分满意度，并多选真正有帮助的建议项；未配置反馈数据库时表单可见但不可提交。

建议由本地确定性规则和模板生成，不调用大语言模型 API。报告不附带完整简历或 JD 正文，以减少不必要的个人信息复制。
生成结果保留在当前会话中，评分交互不会让建议消失。只有状态为 `approved` 的建议学习策略才会改变排序；
默认 `config/suggestion_policy.json` 是未学习的规则基线。

## 评估实验

### FairCV + 公开中文 JD 人工标注基准

`data/test_cases.csv` 包含 60 份 FairCV 合成简历、300 条公开中文 JD 和 300 个固定配对，
按简历查询分组为 20% validation / 80% test。300 条均已完成人工标注，其中 validation 60 条、
test 240 条。评估页面只筛选已标注记录，实时展示标签分布、权重搜索、
TF-IDF/BGE/融合评分对比、分类别指标和误差案例。
详细来源、许可、标注规则和复现命令见 `data/BENCHMARK_CARD.md`。

首页提供 5 份 FairCV 合成示例的一键加载入口。仓库只保存源行号，页面运行时读取简历并移除个人及受保护字段。

完整评估入口：

```powershell
python evaluation\evaluate.py `
  --input data\test_cases.csv `
  --human-labeled-only `
  --output-dir reports\faircv_human_labeled `
  --seed 42 `
  --weight-step 0.1 `
  --classification-threshold 0.5
```

评估代码支持 Pearson、Spearman、NDCG@5、MRR、Accuracy、Precision、Recall、F1、MAE、RMSE，以及 TF-IDF、BGE、融合评分、去除技能后的融合模型对比。还支持验证集权重搜索、消融、分类别结果、错误案例和 PNG 图表。

输入文件标记为 `synthetic_demo` 时，程序会拒绝生成相关性、排序、分类指标和指标图。
`--human-labeled-only` 会忽略 `pending_human` 行，但不会改变原有 validation/test 切分。
当前结果是人工标注的“合成简历—公开 JD”固定基准结果，不代表真实招聘准确率。

## 运行测试

```powershell
python -m pytest -q
python -m compileall -q app.py models utils tests scripts evaluation pages
python -m pip check
```

## 公开部署与用户反馈学习

项目已经支持公开部署所需的自愿反馈闭环，但默认关闭服务器端收集。普通匹配不会保存简历或 JD。
只有部署者配置远程数据库、真实隐私联系人并显式开启收集后，用户才能主动提交反馈。

建议在 Streamlit Community Cloud 的 Secrets 中配置：

```toml
ENABLE_FEEDBACK_COLLECTION = true
FEEDBACK_DATABASE_URL = "postgresql+psycopg2://USER:PASSWORD@HOST:5432/DATABASE?sslmode=require"
PRIVACY_CONTACT = "privacy@example.com"
DATA_RETENTION_DAYS = 180
ALLOW_RESEARCH_TEXT = false
CONSENT_VERSION = "2026-10-19-v1"
```

不要提交真实 `.streamlit/secrets.toml`。完整上线检查见 `DEPLOYMENT.md`，数据规则见 `PRIVACY.md`。

反馈默认只保存派生分数与人工标签；建议反馈另存满意度、所选有用建议类别和上下文派生特征；
保存脱敏简历/JD 需要用户第二次单独授权。每条反馈都会生成删除码。

管理员先运行 `scripts/review_feedback.py` 人工审核。匹配反馈由 `scripts/learn_from_feedback.py` 生成候选融合权重；
建议反馈使用 `scripts/review_feedback.py --feedback-type suggestion ...` 审核，再由
`scripts/learn_suggestions_from_feedback.py` 训练 Logistic Regression“有用建议”分类器并生成候选排序策略。
两条学习流程都至少需要 30 条审核通过的记录并保留独立测试集，且不会自动覆盖线上配置。
建议候选策略人工复核后，使用 `scripts/publish_suggestion_policy.py <候选文件> --confirm-reviewed` 发布。

## FairCV 基础数据

项目可按需读取 [OhMyKing/FairCV](https://huggingface.co/datasets/OhMyKing/FairCV) 作为课程研究中的
公平性审计和鲁棒性测试基础数据。该数据是模拟生成的，数据卡声明仅限学术研究并禁止商业用途；
它包含年龄、性别、户口、婚姻、政治面貌和残障等敏感属性，且没有真实录用标签。

因此本项目不会用 FairCV 直接学习融合权重。敏感属性仅保留在独立的聚合审计通道，进入匹配器前会从
文本中删除。完整数据不写入仓库或线上容器。离线可复现抽样命令：

```powershell
python scripts\prepare_faircv_baseline.py --sample-size 500 --seed 42
```

输出保存在被 Git 忽略的 `data/external/faircv/`。公开页面每次最多临时读取 100 条，只显示聚合计数。

这里直接调用环境中的 Python，可以避开部分中文 Windows 终端中 `conda run` 回显 UTF-8 测试输出时发生的 GBK 编码错误。

## 打包

打包脚本会排除本地模型、缓存、日志和 `data/private/`，并校验 ZIP 内容：

```powershell
python scripts\package_project.py --output ResumeMatcher_final.zip
```

脚本同时生成 `.sha256` 校验文件。交付 ZIP 内的 `PACKAGE_MANIFEST.json` 记录每个文件的大小和 SHA-256。

## 当前功能边界

- 支持带文本层的 PDF、DOCX，以及 UTF-8、UTF-8 BOM、GB18030 编码的 TXT。
- TXT 文件上限为 2 MB，PDF/DOCX 文件上限为 10 MB，解析文本上限为 50,000 个字符。
- PDF 最多解析 100 页；扫描件不会隐式 OCR，而是提示用户先完成 OCR。
- DOCX 同时提取正文段落和表格单元格文本；不支持旧版 `.doc`。
- BGE 对长文本按最多 800 字符分块，分别编码后取均值并再次归一化，减少直接截断造成的信息损失。
- BGE 原始余弦相似度被限制在 0–1 后用于页面百分比展示；页面同时保留原始余弦值。
- 技能提取使用 `data/skills.json` 中的版本化词典；支持中英文别名归一化，并对 `Go`、`Java`、`py` 等短英文别名做字母数字边界保护。
- 岗位技能覆盖率定义为“简历与 JD 共同技能数 ÷ JD 中识别出的技能数”；JD 未命中词典时显示“未识别”，不展示虚假的 0% 结论。
- 技能词典可直接扩展，但词典法只识别文本中明确出现的技能，不推断熟练度、使用年限、项目深度或隐含能力。
- 经历分数使用 `data/experience_keywords.json` 中的职责、教育和经历关键词覆盖率；不可靠的工作年限统一显示为“未识别”，不会从文本中猜测。
- 融合评分只有在 BGE、技能和经历三个子分数都可用，且权重和为 1 时才计算。
- 默认融合权重仅为界面初始展示值；真实权重必须使用独立人工标注验证集选择，并在隔离测试集上报告。
- 优化建议不会把缺失技能、经历或估算指标写成候选人已有事实；用户仍需逐条核实后再修改简历。
- 正式评估指标只有在数据不含 `synthetic_demo` 状态时才会落盘；真实数据必须保持验证集和测试集隔离。
- TF-IDF 分数表示词项相似度，不代表录用概率。
- 示例简历和示例 JD 均为合成数据，不代表真实个人或企业。
- FairCV 仅用于学术公平性审计和鲁棒性测试，不是人工相关性标签或真实性能证据。
- 普通匹配不会保存用户上传的简历正文；只有部署者开启研究文本选项且用户单独授权时，才保存自动脱敏文本。
