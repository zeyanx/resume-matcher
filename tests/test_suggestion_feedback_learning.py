"""建议满意度离线学习与候选策略测试。"""

import json

from evaluation.suggestion_feedback_learning import (
    save_candidate_policy,
    train_suggestion_policy,
)
from models.suggestion_policy import load_suggestion_policy


def make_rows(count: int = 40):
    kinds = ["missing_skills", "missing_sections", "skill_evidence"]
    rows = []
    for index in range(count):
        helpful = ["missing_skills"] if index % 3 else ["skill_evidence"]
        rows.append(
            {
                "submission_id": f"row-{index}",
                "split": "test" if index % 5 == 0 else "validation",
                "satisfaction_rating": 5 if index % 2 else 4,
                "suggestion_kinds_json": json.dumps(kinds),
                "suggestion_priorities_json": json.dumps(["高", "中", "中"]),
                "helpful_kinds_json": json.dumps(helpful),
                "skill_coverage": 0.4 + (index % 4) * 0.1,
                "experience_score": 0.5,
                "missing_skill_count": 2,
                "missing_experience_count": 1,
                "resume_length": 500,
                "jd_length": 300,
            }
        )
    return rows


def test_learning_creates_candidate_without_auto_approval(tmp_path):
    result = train_suggestion_policy(make_rows(), minimum_records=30)
    assert result.submission_count == 40
    assert result.training_item_count == 96
    assert result.test_item_count == 24
    assert set(result.kind_weights) == {
        "missing_skills",
        "missing_sections",
        "skill_evidence",
    }
    candidate_path, metrics_path = save_candidate_policy(result, tmp_path, 30)
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    assert candidate["status"] == "candidate_not_applied"
    assert metrics_path.is_file()
    assert load_suggestion_policy(candidate_path).kind_weights == {}


def test_loader_only_applies_approved_policy(tmp_path):
    path = tmp_path / "approved.json"
    path.write_text(
        json.dumps(
            {
                "version": "learned-v1",
                "status": "approved",
                "source": "reviewed test",
                "learned_from": 40,
                "minimum_approved_records": 30,
                "kind_weights": {"missing_skills": 1.2},
            }
        ),
        encoding="utf-8",
    )
    policy = load_suggestion_policy(path)
    assert policy.version == "learned-v1"
    assert policy.kind_weights == {"missing_skills": 1.2}
