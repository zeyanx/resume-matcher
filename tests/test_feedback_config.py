from utils.feedback_config import load_feedback_settings


def test_collection_is_disabled_without_required_configuration(monkeypatch):
    for name in (
        "ENABLE_FEEDBACK_COLLECTION",
        "FEEDBACK_DATABASE_URL",
        "PRIVACY_CONTACT",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = load_feedback_settings({})
    assert not settings.enabled
    assert "未启用反馈收集" in settings.disabled_reason


def test_collection_requires_database_and_privacy_contact(monkeypatch):
    monkeypatch.setenv("ENABLE_FEEDBACK_COLLECTION", "true")
    monkeypatch.setenv("FEEDBACK_DATABASE_URL", "sqlite:///:memory:")
    monkeypatch.setenv("PRIVACY_CONTACT", "privacy@example.com")
    settings = load_feedback_settings({})
    assert settings.enabled
    assert settings.retention_days == 180
    assert not settings.allow_research_text
