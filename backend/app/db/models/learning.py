import datetime as dt
import uuid
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, Level, ProgressStatus, QuestionType, TimestampMixin, UUIDMixin


class Quiz(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "quizzes"
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    level: Mapped[Level] = mapped_column(Enum(Level, native_enum=False, length=20), default=Level.beginner)
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)   # None = untimed
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)


class Question(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "questions"
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    type: Mapped[QuestionType] = mapped_column(Enum(QuestionType, native_enum=False, length=20))
    prompt: Mapped[str] = mapped_column(Text)
    explanation: Mapped[str] = mapped_column(Text, default="")
    correct_answer: Mapped[str | None] = mapped_column(String(255), nullable=True)   # numerical/practical answers
    tolerance: Mapped[float | None] = mapped_column(Float, nullable=True)
    marks: Mapped[int] = mapped_column(Integer, default=1)
    options: Mapped[list["QuestionOption"]] = relationship(cascade="all, delete-orphan")


class QuestionOption(UUIDMixin, Base):
    __tablename__ = "question_options"
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)   # never sent to students before submission


class QuizAttempt(UUIDMixin, Base):
    __tablename__ = "quiz_attempts"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    quiz_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quizzes.id", ondelete="CASCADE"), index=True)
    started_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    submitted_at: Mapped[dt.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_marks: Mapped[int | None] = mapped_column(Integer, nullable=True)


class QuizAnswer(UUIDMixin, Base):
    __tablename__ = "quiz_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)
    attempt_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("quiz_attempts.id", ondelete="CASCADE"), index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("questions.id", ondelete="CASCADE"))
    selected_option_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("question_options.id"), nullable=True)
    answer_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)


class StudentProgress(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "student_progress"
    __table_args__ = (UniqueConstraint("user_id", "topic_id"),)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    status: Mapped[ProgressStatus] = mapped_column(Enum(ProgressStatus, native_enum=False, length=20), default=ProgressStatus.not_started)


class TerminalHistory(UUIDMixin, Base):
    __tablename__ = "terminal_history"
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    command: Mapped[str] = mapped_column(String(500))
    output: Mapped[str] = mapped_column(Text, default="")
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AuditLog(UUIDMixin, Base):
    __tablename__ = "audit_logs"
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(80), index=True)          # e.g. user.login_failed, quiz.publish
    entity: Mapped[str | None] = mapped_column(String(80), nullable=True)
    detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
