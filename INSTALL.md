# 安装与运行说明

## 1. 系统要求

- Windows 10 或 Windows 11；
- Conda 或 Miniconda；
- 建议至少 8 GB 内存；
- BGE 首次下载需要网络，完成后可离线运行。

本项目锁定 Python 3.10 和 `requirements.txt` 中的依赖版本。

## 2. 创建环境

在 PowerShell 中进入 `ResumeMatcher` 目录：

```powershell
conda env create -f environment.yml
conda activate resume_match
```

如果环境已经存在，只需：

```powershell
conda activate resume_match
python -m pip install -r requirements.txt
python -m pip check
```

## 3. 准备 BGE 模型

首次联网下载并保存到项目本地目录：

```powershell
python scripts\download_bge_model.py
```

模型默认保存到 `models_cache/bge-small-zh-v1.5/`。该目录体积较大，不包含在交付 ZIP 中。

如果无法下载，可以先关闭页面侧栏中的“启用 BGE 语义匹配”，其余 TF-IDF、技能、经历、建议和报告功能仍可使用。融合评分依赖 BGE，因此会显示不可用。

## 4. 启动网页

```powershell
python -m streamlit run app.py
```

浏览器访问：`http://localhost:8501`

若端口被占用：

```powershell
python -m streamlit run app.py --server.port 8502
```

## 5. 运行测试与编译检查

```powershell
$env:PYTHONIOENCODING="utf-8"
python -m pytest -q
python -m compileall -q app.py models utils tests scripts evaluation pages
python -m pip check
```

## 6. 运行评估流程

当前仓库只有合成流程数据，运行后不会生成正式性能指标：

```powershell
python evaluation\evaluate.py `
  --input data\evaluation\synthetic_evaluation_scores.csv `
  --output-dir reports\stage7_synthetic_demo `
  --seed 42
```

真实评估必须使用人工标注数据，保持 `validation` 和 `test` 分离，并将 `data_status` 写为真实数据版本，而不是 `synthetic_demo`。

## 7. 隐私和数据边界

- 普通匹配的上传内容只在当前 Streamlit 会话中处理；
- 导出报告不包含完整简历或 JD 正文；
- 不要把私人简历放入公开仓库或交付 ZIP；
- `data/private/`、模型缓存、日志和本地缓存会被打包脚本排除。

若要公开部署并启用自愿反馈，请按 `DEPLOYMENT.md` 配置远程 PostgreSQL、真实隐私联系人和
Streamlit Secrets。缺少任一必要配置时反馈收集会保持关闭。建议默认保持
`ALLOW_RESEARCH_TEXT = false`，只收集派生分数和人工标签。
