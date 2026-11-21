from __future__ import annotations

from pydantic import BaseModel, Field, StrictInt


class RegisterIn(BaseModel):
    email: str = Field(max_length=254)
    username: str = Field(max_length=32)
    password: str = Field(max_length=128)


class LoginIn(BaseModel):
    identifier: str = Field(max_length=254)
    password: str = Field(max_length=128)


class ProgressIn(BaseModel):
    topic_id: str = Field(max_length=60)
    completed: bool


class UserPatch(BaseModel):
    is_active: bool | None = None
    role: str | None = Field(default=None, max_length=20)


class PasswordReset(BaseModel):
    new_password: str = Field(max_length=128)


class TopicIn(BaseModel):
    module: str = Field(max_length=20)
    level: str = Field(max_length=20)
    title: str = Field(max_length=150)
    summary: str = Field(max_length=2000)
    points: list[str] = Field(max_length=10)
    example: str = Field(max_length=1500)
    exercise: str = Field(max_length=1500)
    answer: str = Field(max_length=1500)
    published: bool = True


class QuestionIn(BaseModel):
    module: str = Field(max_length=20)
    level: str = Field(max_length=20)
    prompt: str = Field(max_length=600)
    options: list[str] = Field(max_length=6)
    correct_index: StrictInt
    explanation: str = Field(max_length=600)
    published: bool = True


class Visibility(BaseModel):
    published: bool
