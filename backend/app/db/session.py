from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import get_database_url


@lru_cache
def get_engine():
    return create_engine(get_database_url(), pool_pre_ping=True)


@lru_cache
def _factory():
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def new_session():
    return _factory()()


def get_db():
    """FastAPI dependency: one session per request, always closed."""
    db = new_session()
    try:
        yield db
    finally:
        db.close()
