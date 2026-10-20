"""证据化简历建议生成测试。"""

from models.experience_matcher import calculate_experience_match
from models.suggestion import generate_resume_suggestions
from utils.skill_extractor import analyze_skill_gap


def test_suggestions_are_actionable_and_do_not_claim_missing_skill() -> None:
    resume = "技能：Python、Flask、MySQL。项目经历：完成后端开发和测试。"
    jd = "要求 Python、Django、Docker；负责软件开发、测试、部署和文档维护。"
    skills = analyze_skill_gap(resume, jd)
    experience = calculate_experience_match(resume, jd)
    suggestions = generate_resume_suggestions(resume, jd, skills, experience)

    assert 3 <= len(suggestions) <= 5
    skill_suggestion = next(item for item in suggestions if "缺失技能" in item.title)
    assert "Django" in skill_suggestion.action
    assert "若你确实使用过" in skill_suggestion.action
    assert "不要直接写成已掌握" in skill_suggestion.action


def test_missing_numbers_produces_truthful_measurement_advice() -> None:
    resume = "技能：Python。项目经历：完成接口开发。"
    jd = "要求 Python，负责接口开发和测试。"
    suggestions = generate_resume_suggestions(
        resume,
        jd,
        analyze_skill_gap(resume, jd),
        calculate_experience_match(resume, jd),
    )
    measurement = next(item for item in suggestions if item.title == "补充可核实的结果证据")
    assert "若有可核实记录" in measurement.action
    assert "不要估造指标" in measurement.action


def test_suggestions_have_fallbacks_when_no_gap_exists() -> None:
    resume = "求职意向：开发。教育背景：本科。技能：Python。项目经历：软件开发和测试，共2个项目。"
    jd = "本科，要求 Python，负责软件开发和测试。"
    suggestions = generate_resume_suggestions(
        resume,
        jd,
        analyze_skill_gap(resume, jd),
        calculate_experience_match(resume, jd),
    )
    assert 3 <= len(suggestions) <= 5
    assert len({item.title for item in suggestions}) == len(suggestions)


def test_approved_kind_weights_can_change_suggestion_order() -> None:
    resume = "技能：Python。项目经历：完成接口开发。"
    jd = "要求 Python、Docker，负责接口开发、部署和测试。"
    skills = analyze_skill_gap(resume, jd)
    experience = calculate_experience_match(resume, jd)
    baseline = generate_resume_suggestions(resume, jd, skills, experience)
    reranked = generate_resume_suggestions(
        resume,
        jd,
        skills,
        experience,
        kind_weights={"missing_skills": 0.5, "missing_experience": 1.5},
    )
    assert baseline[0].kind == "missing_skills"
    assert reranked[0].kind == "missing_experience"
