# 阶段 1：最小闭环验收记录

## 1. 阶段目标

建立可运行工程骨架，实现 TXT 简历读取、jieba 中文分词、TF-IDF 余弦相似度，以及“上传 TXT + 输入 JD + 显示分数”的 Streamlit 最小闭环。

## 2. 实际完成情况

- 已创建独立 Conda 环境 `resume_match`，Python 版本为 3.10.22。
- 已安装 `requirements.txt` 中的固定依赖。
- 已实现 UTF-8、UTF-8 BOM 和 GB18030 TXT 解析。
- 已实现 2 MB 文件上限、50,000 字符上限、空文件、空白文件、未知编码和空输入处理。
- 已实现 jieba 分词，并将缓存放在项目 `.cache/jieba/`，避免依赖系统临时目录权限。
- 已实现 TF-IDF + 余弦相似度，返回范围为 0–1。
- 已实现中文 Streamlit 单页界面、合成示例载入、文本预览、分数和边界说明。
- 已建立 README、测试、样式、数据卡和后续阶段目录占位。

## 3. 新增或修改的主要文件

- `app.py`
- `models/tfidf_matcher.py`
- `utils/text_preprocessor.py`
- `utils/resume_parser.py`
- `tests/test_app.py`
- `tests/test_resume_parser.py`
- `tests/test_text_preprocessor.py`
- `tests/test_tfidf_matcher.py`
- `data/sample_resumes/sample_resume.txt`
- `data/sample_jds/sample_python_backend.txt`
- `data/DATA_CARD.md`
- `README.md`

## 4. 验证命令

```powershell
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pip check
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m compileall -q app.py models utils tests
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m pytest -q
& "C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe" -m streamlit run app.py
```

## 5. 已确认的测试结果

- `pip check`：无损坏或冲突依赖。
- Python 编译检查：通过。
- 自动化测试：16 项全部通过。
- Streamlit 启动探测：服务成功启动；`/_stcore/health` 返回 HTTP 200 和 `ok`，首页返回 HTTP 200。
- 随手构造的短文本算法检查分数为 0.709297；工程内完整合成示例的分数为 0.416150。二者仅用于验证功能链路，不是模型真实业务性能。

## 6. 常见错误与处理

1. 当前 PowerShell 找不到 `conda`：使用 `C:\ProgramData\miniconda3\Scripts\conda.exe`。
2. `conda run` 在中文 Windows 中回显 UTF-8 测试输出时可能触发 GBK 编码错误：直接调用 `C:\Users\XUSITIAN\.conda\envs\resume_match\python.exe`。
3. jieba 首次运行需要生成缓存：缓存已定向至项目 `.cache/jieba/`。
4. 页面显示空输入警告：必须同时提供有效简历文本和 JD。
5. TF-IDF 分数较低不等于候选人不合格：当前阶段仅比较词项相似度。

## 7. 本阶段验收清单

- [x] Python 3.10 隔离环境
- [x] 项目骨架
- [x] TXT 简历读取
- [x] jieba 分词
- [x] TF-IDF + 余弦相似度
- [x] Streamlit 最小页面
- [x] 合成演示数据
- [x] 输入异常处理
- [x] 单元与页面交互测试
- [x] 编译、依赖与启动探测

## 8. 下一阶段

阶段 2 将在不改变当前 TF-IDF 接口的前提下，为解析器增加 PDF、DOCX 和 TXT 统一入口，完善文件类型校验、解析失败提示和页面文本预览。
