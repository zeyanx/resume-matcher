from utils.public_text import sanitize_public_resume


def test_public_resume_scrub_removes_sensitive_footer_and_contact_details() -> None:
    raw = """**个人简历**

---

**项目经验**

- 构建推荐系统

---

**参考资料**

- 推荐人：张伟，联系方式：139-0000-0000

---

**声明**

以上信息真实有效。

---

**[签名]**

王超
"""

    cleaned = sanitize_public_resume(raw)

    assert "构建推荐系统" in cleaned
    assert "推荐人" not in cleaned
    assert "139-0000-0000" not in cleaned
    assert "声明" not in cleaned
    assert "签名" not in cleaned
    assert "王超" not in cleaned


def test_public_resume_scrub_redacts_inline_email_and_phone() -> None:
    cleaned = sanitize_public_resume("邮箱：demo@example.com\n电话：13800138000\n项目：检索")

    assert "demo@example.com" not in cleaned
    assert "13800138000" not in cleaned
    assert "项目：检索" in cleaned
