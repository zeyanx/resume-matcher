# 公开部署指南

## 1. 准备 GitHub 仓库

将项目提交到 GitHub。`models_cache/`、`.streamlit/secrets.toml`、本地数据库、私有数据和运行报告
已经在 `.gitignore` 中排除；提交前仍应检查一次仓库内容。

## 2. 准备持久化 PostgreSQL

创建可通过互联网访问、强制 TLS 的 PostgreSQL 数据库。不要使用 Streamlit 容器本地 SQLite 作为
生产反馈库，因为应用重启或重新部署后本地文件可能丢失。

## 3. 在 Streamlit Community Cloud 部署

选择 GitHub 仓库、分支和入口文件 `app.py`。在 Advanced settings > Secrets 中填写
`.streamlit/secrets.toml.example` 所列变量。真实数据库密码绝不能提交到 GitHub。

只有以下条件全部满足时反馈表才会出现：

- `ENABLE_FEEDBACK_COLLECTION = true`
- `FEEDBACK_DATABASE_URL` 可连接
- `PRIVACY_CONTACT` 已替换为真实联系人

建议先保持 `ALLOW_RESEARCH_TEXT = false`，只收集派生分数与人工标签。

## 4. 上线前检查

- 公开访问主页并完成一次不提交反馈的匹配。
- 使用测试记录提交反馈，保存删除码并验证自助删除。
- 确认数据库启用 TLS、最小权限账户、备份和保留期清理。
- 确认页面展示真实隐私联系人和适用的正式隐私政策。
- 不要把合成演示数据描述成真实模型效果。

## 5. 审核与离线学习

使用 `scripts/review_feedback.py` 审核记录，再运行 `scripts/learn_from_feedback.py`。学习结果输出到
`reports/feedback_learning/`，不会修改 `config/fusion_weights.json`，必须人工复核后才能决定是否发布。
建议通过数据库平台的计划任务定期执行 `python scripts/review_feedback.py purge`；新反馈提交时应用也会
尝试清理一次过期记录。
