import pytest

from utils.feedback_store import (
    FeedbackStore,
    FeedbackStoreError,
    FeedbackSubmission,
    redact_personal_data,
)


def build_submission(**changes):
    values = {
        "relevance_label": 2,
        "helpfulness_rating": 4,
        "feedback_comment": "请联系 test@example.com 或 13800138000",
        "scores": {
            "tfidf": 0.3,
            "semantic": 0.7,
            "skill": 0.5,
            "experience": 0.4,
            "fusion": 0.58,
        },
        "matched_skills": ["Python"],
        "missing_skills": ["Docker"],
        "policy_consent": True,
        "research_text_consent": False,
        "resume_text": "张三 13800138000 test@example.com https://example.com",
        "jd_text": "需要 Python",
    }
    values.update(changes)
    return FeedbackSubmission(**values)


@pytest.fixture()
def store(tmp_path):
    feedback_store = FeedbackStore(f"sqlite:///{tmp_path / 'feedback.db'}")
    feedback_store.initialize()
    return feedback_store


def test_rejects_submission_without_explicit_consent(store):
    with pytest.raises(FeedbackStoreError, match="明确同意"):
        store.submit(build_submission(policy_consent=False))


def test_default_submission_does_not_store_resume_or_jd(store):
    receipt = store.submit(build_submission())
    records = store.list_records()
    assert receipt.split in {"validation", "test"}
    assert len(records) == 1
    assert records[0]["resume_text_redacted"] is None
    assert records[0]["jd_text_redacted"] is None
    assert records[0]["review_status"] == "pending"
    assert "test@example.com" not in records[0]["feedback_comment"]
    assert "13800138000" not in records[0]["feedback_comment"]


def test_separate_text_consent_stores_only_redacted_text(store):
    store.submit(build_submission(research_text_consent=True))
    record = store.list_records()[0]
    assert "13800138000" not in record["resume_text_redacted"]
    assert "test@example.com" not in record["resume_text_redacted"]
    assert "https://example.com" not in record["resume_text_redacted"]
    assert "[已删除手机号]" in record["resume_text_redacted"]


def test_deletion_token_removes_only_matching_record(store):
    first = store.submit(build_submission())
    store.submit(build_submission(relevance_label=3))
    assert not store.delete_by_token("wrong-token")
    assert store.delete_by_token(first.deletion_token)
    assert len(store.list_records()) == 1
    assert not store.delete_by_token(first.deletion_token)


def test_only_approved_complete_rows_are_available_for_learning(store):
    receipt = store.submit(build_submission())
    assert store.approved_learning_rows() == []
    assert store.set_review_status(receipt.submission_id, "approved")
    rows = store.approved_learning_rows()
    assert len(rows) == 1
    assert rows[0]["relevance_label"] == 2


def test_redaction_covers_common_identifiers():
    text = "身份证 11010519491231002X，邮箱 a.b+c@example.cn，手机 +86 13912345678。"
    redacted = redact_personal_data(text)
    assert "11010519491231002X" not in redacted
    assert "a.b+c@example.cn" not in redacted
    assert "13912345678" not in redacted
