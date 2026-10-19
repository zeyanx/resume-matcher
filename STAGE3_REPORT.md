# 阶段 3：BGE 语义匹配验收记录

## 1. 阶段目标

实现 `BAAI/bge-small-zh-v1.5` 语义向量匹配、模型缓存、首次在线下载、本地离线加载和明确的失败降级方案。

## 2. 实际完成情况

- 新增 `models/bge_matcher.py`。
- 新增 BGE 长文本分块、文档向量聚合和余弦相似度计算。
- Streamlit 使用 `st.cache_resource` 缓存模型，页面重跑时不重复加载。
- 页面同时展示 TF-IDF 与 BGE 匹配度。
- 页面展示推理设备、文本分块数和原始余弦值。
- 新增在线下载及本地保存脚本 `scripts/download_bge_model.py`。
- 支持页面参数和环境变量指定本地模型、缓存目录和离线模式。
- 模型不可用时保留 TF-IDF 结果，并明确显示降级原因。

## 3. 模型缓存与离线方案

默认在线模型：

```text
BAAI/bge-small-zh-v1.5
```

Hugging Face 缓存目录：

```text
models_cache/huggingface/
```

标准离线模型目录：

```text
models_cache/bge-small-zh-v1.5/
```

下载命令：

```powershell
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" scripts\download_bge_model.py
```

本机已实际执行下载，并成功保存标准离线副本。模型目录被 `.gitignore` 排除，不会误提交到代码仓库；打包时是否附带模型应根据 ZIP 体积要求单独决定。

## 4. 长文本处理

- 每块最多 800 个字符。
- 最多处理 64 个文本块。
- 每个文本块单独生成归一化向量。
- 文档向量由文本块向量取均值后再次归一化得到。
- 文档级匹配使用余弦相似度。
- 页面百分比使用限制在 0–1 范围内的值，同时展示原始余弦值。

## 5. 运行与验证命令

```powershell
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pytest -q
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m compileall -q app.py models utils tests scripts
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pip check
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m streamlit run app.py
```

## 6. 真实运行验证

- 模型：`BAAI/bge-small-zh-v1.5`。
- 加载方式：本地目录、强制离线。
- 本地离线模型大小：约 91.8 MB。
- 推理设备：CPU。
- 工程内合成示例 TF-IDF：41.61%。
- 工程内合成示例 BGE：89.46%。
- BGE 原始余弦值：0.894631。
- 文本分块：简历 1 块、JD 1 块。
- Streamlit 页面交互验证：0 个页面异常，两个指标均成功生成。

以上数字仅证明模型下载、离线加载、推理和页面展示链路正常，不能作为真实招聘数据上的模型性能结论。

## 7. 自动化测试

测试覆盖：

- 相关文本与无关文本的分数顺序；
- 文本分块长度和块数限制；
- 空输入；
- 零向量；
- 本地模型目录解析；
- 离线配置解析；
- 原有 PDF、DOCX、TXT、TF-IDF 和页面流程回归。

最终回归结果：38 项测试全部通过；另有 5 条来自 PyMuPDF SWIG 类型的弃用警告，不影响当前功能。

## 8. 常见错误与处理

1. 首次下载失败：检查网络后重试，或运行下载脚本准备本地目录。
2. 离线模式找不到模型：确认本地目录中包含配置、分词器和模型权重文件。
3. Windows 不支持缓存符号链接：不影响模型使用，但缓存可能额外占用磁盘空间。
4. 内存不足：关闭其他占用内存的程序，使用 CPU，并减少同时处理的文本长度。
5. 模型异常时页面只显示 TF-IDF：这是显式降级行为，不代表 BGE 得分为零。

## 9. 本阶段验收清单

- [x] BGE 模型封装
- [x] 文本向量与余弦相似度
- [x] 长文本分块
- [x] Streamlit 模型缓存
- [x] 首次在线下载脚本
- [x] 本地离线加载
- [x] 环境变量配置
- [x] 失败降级提示
- [x] 真实模型下载
- [x] CPU 离线推理
- [x] 页面双指标展示

## 10. 下一阶段

阶段 4 将设计技能词典与同义词体系，实现技能提取、已匹配技能、缺失技能、技能覆盖率和页面可视化。
