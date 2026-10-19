# 阶段 2：多格式简历解析验收记录

## 1. 阶段目标

在不改变 TF-IDF 匹配接口的前提下，为网页增加 PDF、DOCX、TXT 统一解析入口、解析文本预览、文件信息展示和面向用户的异常提示。

## 2. 实际完成情况

- 新增统一入口 `parse_resume_bytes(content, filename)`。
- TXT 支持 UTF-8、UTF-8 BOM 和 GB18030。
- PDF 使用 PyMuPDF 提取文本层，并返回页数。
- DOCX 使用 python-docx 提取正文段落和表格单元格。
- 网页上传控件已支持 `.pdf`、`.docx`、`.txt`。
- 解析成功后显示文件格式、字符数和 PDF 页数。
- 提取后的文本可在网页中预览和人工修正，再参与 TF-IDF 匹配。

## 3. 文件与文本限制

- TXT 最大 2 MB。
- PDF、DOCX 最大 10 MB。
- PDF 最多 100 页。
- 解析后文本最多 50,000 个字符。
- 旧版 `.doc` 不在支持范围内。

## 4. 异常处理

已覆盖以下情况：

- 空文件和空白 TXT；
- 未知 TXT 编码；
- 不支持的扩展名；
- 扩展名与实际内容不一致；
- 损坏的 PDF 或 DOCX；
- 加密 PDF；
- 没有文本层的扫描型 PDF；
- 超过文件大小、页数或字符数限制。

扫描型 PDF 当前不会自动 OCR，页面会提示用户先进行 OCR，避免把空文本误判为低匹配度。

## 5. 运行与验证命令

```powershell
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pytest -q
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m compileall -q app.py models utils tests
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pip check
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m streamlit run app.py
```

## 6. 验证结果

- Python 编译检查：通过。
- 依赖检查：无损坏或冲突依赖。
- 自动化测试：25 项全部通过。
- Streamlit 健康检查：HTTP 200，返回 `ok`。
- 页面交互冒烟测试继续通过。
- PyMuPDF 在 Python 3.10 下产生 SWIG 类型弃用警告，但不影响本阶段功能。

## 7. 当前解析边界

- PDF 必须具有可提取文本层。
- 暂不集成 OCR，避免额外模型、体积和不透明识别误差。
- DOCX 文本框、SmartArt 和嵌入对象不保证可被 python-docx 提取。
- 不支持传统二进制 `.doc`，用户需要先另存为 `.docx` 或 `.pdf`。
- 解析结果不写入磁盘或日志。

## 8. 本阶段验收清单

- [x] PDF 解析
- [x] DOCX 解析
- [x] TXT 解析
- [x] 统一解析接口
- [x] 文件格式与内容校验
- [x] 空文本和扫描件提示
- [x] 加密文件提示
- [x] 文件、页数和字符数限制
- [x] 页面文本预览
- [x] 解析信息展示
- [x] 自动化测试
- [x] 编译、依赖和服务健康检查

## 9. 下一阶段

阶段 3 将实现 `BAAI/bge-small-zh-v1.5` 语义向量匹配、`st.cache_resource` 模型缓存、在线下载与本地离线加载方案，并在模型不可用时提供明确的降级提示。
