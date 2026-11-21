"""Importing this package registers every table on Base.metadata (needed by Alembic)."""
from .users import Role, User, RefreshToken
from .content import Module, Topic, LearningMaterial, Algorithm
from .simulations import Simulation, SimulationRun, SimulationResult, SimulationStep, ComparisonSession
from .learning import (Quiz, Question, QuestionOption, QuizAttempt, QuizAnswer,
                       StudentProgress, TerminalHistory, AuditLog)

__all__ = ["Role", "User", "RefreshToken", "Module", "Topic", "LearningMaterial", "Algorithm", "Simulation",
           "SimulationRun", "SimulationResult", "SimulationStep", "ComparisonSession", "Quiz", "Question",
           "QuestionOption", "QuizAttempt", "QuizAnswer", "StudentProgress", "TerminalHistory", "AuditLog"]
