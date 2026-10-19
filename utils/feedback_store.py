"""经用户明确同意的反馈存储、删除与人工审核。"""

from __future__ import annotations

import hashlib
import json
import math
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Mapping, Sequence

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    select,
    update,
)
from sqlalchemy.engine import Engine


EMAIL_RE = re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])")
PHONE_RE = re.compile(r"(?<!\d)(?:\+?86[- ]?)?1[3-9]\d{9}(?!\d)")
ID_RE = re.compile(r"(?<!\d)\d{17}[\dXx](?!\d)")
URL_RE = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)
MAX_TEXT_LENGTH = 50_000
MAX_COMMENT_LENGTH = 2_000
ALLOWED_SCORE_NAMES = {"tfidf", "semantic", "skill", "experience", "fusion"}
ALLOWED_REVIEW_STATUSES = {"pending", "approved", "rejected"}


class FeedbackStoreError(RuntimeError):
    """反馈存储或输入校验失败。"""


@dataclass(frozen=True, slots=True)
class FeedbackSubmission:
    relevance_label: int
    helpfulness_rating: int
    feedback_comment: str
    scores: Mapping[str, float | None]
    matched_skills: Sequence[str]
    missing_skills: Sequence[str]
    policy_consent: bool
    research_text_consent: bool = False
    resume_text: str = ""
    jd_text: str = ""
    consent_version: str = "2026-10-19-v1"


@dataclass(frozen=True, slots=True)
class SubmissionReceipt:
    submission_id: str
    deletion_token: str
    split: str


def redact_personal_data(text: str) -> str:
    """尽力删除常见邮箱、手机号、身份证号和网址；不承诺识别所有个人信息。"""
    redacted = ID_RE.sub("[已删除身份证号]", str(text))
    redacted = PHONE_RE.sub("[已删除手机号]", redacted)
    redacted = EMAIL_RE.sub("[已删除邮箱]", redacted)
    redacted = URL_RE.sub("[已删除网址]", redacted)
    return redacted


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _deterministic_split(submission_id: str) -> str:
    bucket = int(hashlib.sha256(submission_id.encode("ascii")).hexdigest()[:8], 16) % 5
    return "test" if bucket == 0 else "validation"


def _safe_json_list(values: Sequence[str]) -> str:
    cleaned = [redact_personal_data(str(value).strip())[:200] for value in values if str(value).strip()]
    return json.dumps(cleaned[:100], ensure_ascii=False)


class FeedbackStore:
    """SQLAlchemy 后端；支持本地 SQLite 测试和远程 PostgreSQL 生产库。"""

    def __init__(self, database_url: str, retention_days: int = 180) -> None:
        if not database_url.strip():
            raise FeedbackStoreError("反馈数据库地址为空。")
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        try:
            self.engine: Engine = create_engine(
                database_url,
                pool_pre_ping=True,
                connect_args=connect_args,
            )
        except Exception as exc:  # SQLAlchemy 的驱动异常类型随后端变化
            raise FeedbackStoreError("无法创建反馈数据库连接。") from exc
        self.retention_days = min(max(int(retention_days), 1), 3650)
        self.metadata = MetaData()
        self.feedback = Table(
            "user_feedback",
            self.metadata,
            Column("submission_id", String(36), primary_key=True),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("split", String(16), nullable=False),
            Column("relevance_label", Integer, nullable=False),
            Column("helpfulness_rating", Integer, nullable=False),
            Column("feedback_comment", Text, nullable=False, default=""),
            Column("tfidf_score", Float, nullable=True),
            Column("semantic_score", Float, nullable=True),
            Column("skill_score", Float, nullable=True),
            Column("experience_score", Float, nullable=True),
            Column("fusion_score", Float, nullable=True),
            Column("matched_skills_json", Text, nullable=False),
            Column("missing_skills_json", Text, nullable=False),
            Column("research_text_consent", Integer, nullable=False),
            Column("resume_text_redacted", Text, nullable=True),
            Column("jd_text_redacted", Text, nullable=True),
            Column("consent_version", String(64), nullable=False),
            Column("review_status", String(16), nullable=False),
            Column("deletion_token_hash", String(64), nullable=False, unique=True),
        )

    def initialize(self) -> None:
        try:
            self.metadata.create_all(self.engine)
        except Exception as exc:
            raise FeedbackStoreError("无法初始化反馈数据库。") from exc

    @staticmethod
    def _validated_scores(scores: Mapping[str, float | None]) -> dict[str, float | None]:
        cleaned: dict[str, float | None] = {name: None for name in ALLOWED_SCORE_NAMES}
        for name, value in scores.items():
            if name not in ALLOWED_SCORE_NAMES or value is None:
                continue
            numeric = float(value)
            if not math.isfinite(numeric) or not 0 <= numeric <= 1:
                raise FeedbackStoreError(f"{name} 分数必须在 0 到 1 之间。")
            cleaned[name] = numeric
        return cleaned

    def submit(self, submission: FeedbackSubmission) -> SubmissionReceipt:
        if not submission.policy_consent:
            raise FeedbackStoreError("提交前必须明确同意数据使用说明。")
        if submission.relevance_label not in range(4):
            raise FeedbackStoreError("实际匹配程度必须是 0 到 3。")
        if submission.helpfulness_rating not in range(1, 6):
            raise FeedbackStoreError("结果帮助程度必须是 1 到 5。")
        scores = self._validated_scores(submission.scores)
        submission_id = str(uuid.uuid4())
        deletion_token = secrets.token_urlsafe(24)
        store_text = bool(submission.research_text_consent)
        values = {
            "submission_id": submission_id,
            "created_at": datetime.now(timezone.utc),
            "split": _deterministic_split(submission_id),
            "relevance_label": submission.relevance_label,
            "helpfulness_rating": submission.helpfulness_rating,
            "feedback_comment": redact_personal_data(submission.feedback_comment)[:MAX_COMMENT_LENGTH],
            "tfidf_score": scores["tfidf"],
            "semantic_score": scores["semantic"],
            "skill_score": scores["skill"],
            "experience_score": scores["experience"],
            "fusion_score": scores["fusion"],
            "matched_skills_json": _safe_json_list(submission.matched_skills),
            "missing_skills_json": _safe_json_list(submission.missing_skills),
            "research_text_consent": int(store_text),
            "resume_text_redacted": (
                redact_personal_data(submission.resume_text)[:MAX_TEXT_LENGTH] if store_text else None
            ),
            "jd_text_redacted": (
                redact_personal_data(submission.jd_text)[:MAX_TEXT_LENGTH] if store_text else None
            ),
            "consent_version": submission.consent_version[:64],
            "review_status": "pending",
            "deletion_token_hash": _token_hash(deletion_token),
        }
        try:
            with self.engine.begin() as connection:
                connection.execute(self.feedback.insert().values(**values))
        except Exception as exc:
            raise FeedbackStoreError("反馈保存失败，请稍后重试。") from exc
        return SubmissionReceipt(submission_id, deletion_token, values["split"])

    def delete_by_token(self, deletion_token: str) -> bool:
        token = deletion_token.strip()
        if len(token) < 16:
            return False
        try:
            with self.engine.begin() as connection:
                result = connection.execute(
                    delete(self.feedback).where(self.feedback.c.deletion_token_hash == _token_hash(token))
                )
                return bool(result.rowcount)
        except Exception as exc:
            raise FeedbackStoreError("删除请求执行失败，请联系隐私联系人。") from exc

    def purge_expired(self) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=self.retention_days)
        try:
            with self.engine.begin() as connection:
                result = connection.execute(delete(self.feedback).where(self.feedback.c.created_at < cutoff))
                return int(result.rowcount or 0)
        except Exception as exc:
            raise FeedbackStoreError("过期数据清理失败。") from exc

    def set_review_status(self, submission_id: str, status: str) -> bool:
        if status not in ALLOWED_REVIEW_STATUSES:
            raise FeedbackStoreError("审核状态必须是 pending、approved 或 rejected。")
        try:
            with self.engine.begin() as connection:
                result = connection.execute(
                    update(self.feedback)
                    .where(self.feedback.c.submission_id == submission_id)
                    .values(review_status=status)
                )
                return bool(result.rowcount)
        except Exception as exc:
            raise FeedbackStoreError("反馈审核状态更新失败。") from exc

    def list_records(self, status: str | None = None, limit: int = 100) -> list[dict[str, object]]:
        query = select(self.feedback)
        if status is not None:
            if status not in ALLOWED_REVIEW_STATUSES:
                raise FeedbackStoreError("未知审核状态。")
            query = query.where(self.feedback.c.review_status == status)
        query = query.order_by(self.feedback.c.created_at.desc()).limit(min(max(limit, 1), 1000))
        try:
            with self.engine.connect() as connection:
                return [dict(row) for row in connection.execute(query).mappings()]
        except Exception as exc:
            raise FeedbackStoreError("无法读取反馈记录。") from exc

    def approved_learning_rows(self) -> list[dict[str, object]]:
        required = (
            self.feedback.c.semantic_score.is_not(None)
            & self.feedback.c.skill_score.is_not(None)
            & self.feedback.c.experience_score.is_not(None)
        )
        query = select(self.feedback).where(
            (self.feedback.c.review_status == "approved") & required
        )
        try:
            with self.engine.connect() as connection:
                return [dict(row) for row in connection.execute(query).mappings()]
        except Exception as exc:
            raise FeedbackStoreError("无法读取已审核训练记录。") from exc
