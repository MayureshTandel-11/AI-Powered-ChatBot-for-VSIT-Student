"""Shared pytest fixtures for API tests."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.database import Base, get_db
from app.db.models import User
from app.main import app
from app.services.embedding_service import reset_embedding_service
from app.services.retrieval_service import reset_vector_store

TEST_DATABASE_URL = "sqlite://"


@pytest.fixture(autouse=True)
def test_env(tmp_path, monkeypatch):
    """Use isolated lightweight ML backends for all API tests."""
    vector_dir = tmp_path / "vector_store"
    vector_dir.mkdir(exist_ok=True)

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "use_fake_embeddings", True)
    monkeypatch.setattr(settings, "vector_store_directory", str(vector_dir))
    monkeypatch.setattr(settings, "similarity_threshold", 0.05)
    monkeypatch.setattr(settings, "email_dev_mode", True)
    monkeypatch.setattr("app.services.retrieval_service.settings.use_fake_embeddings", True)
    monkeypatch.setattr("app.services.retrieval_service.settings.vector_store_directory", str(vector_dir))
    monkeypatch.setattr("app.services.retrieval_service.settings.similarity_threshold", 0.05)
    monkeypatch.setattr("app.services.embedding_service.settings.use_fake_embeddings", True)

    reset_embedding_service()
    reset_vector_store()
    yield
    reset_embedding_service()
    reset_vector_store()
    get_settings.cache_clear()


@pytest.fixture()
def db_session():
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def student_user(db_session) -> User:
    user = User(
        name="Test Student",
        email="test.student@vsit.edu.in",
        password_hash=hash_password("studentpass"),
        role="student",
    )
    user.email_verified = True
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def admin_user(db_session) -> User:
    user = User(
        name="Test Admin",
        email="admin.user@vsit.edu.in",
        password_hash=hash_password("adminpass1"),
        role="admin",
    )
    user.email_verified = True
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user
