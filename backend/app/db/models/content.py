import uuid
from typing import Any

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, Level, TimestampMixin, UUIDMixin


class Module(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "modules"
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="")
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True)


class Topic(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("module_id", "slug"),)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(80))
    title: Mapped[str] = mapped_column(String(150))
    level: Mapped[Level] = mapped_column(Enum(Level, native_enum=False, length=20), default=Level.beginner)
    position: Mapped[int] = mapped_column(Integer, default=0)


class LearningMaterial(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "learning_materials"
    topic_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    level: Mapped[Level] = mapped_column(Enum(Level, native_enum=False, length=20), default=Level.beginner)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False)


class Algorithm(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "algorithms"
    __table_args__ = (UniqueConstraint("module_id", "slug"),)
    module_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("modules.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    rules: Mapped[list[Any]] = mapped_column(JSONB, default=list)
    implemented: Mapped[bool] = mapped_column(Boolean, default=False)   # True only when an engine + tests exist
