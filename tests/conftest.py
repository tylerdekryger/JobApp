from urllib.parse import urlparse

import psycopg
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base


def _ensure_database_exists(database_url: str) -> None:
    plain_url = database_url.replace("+psycopg", "")
    parsed = urlparse(plain_url)
    db_name = parsed.path.lstrip("/")
    admin_dsn = parsed._replace(path="/postgres").geturl()

    conn = psycopg.connect(admin_dsn, autocommit=True)
    try:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (db_name,)).fetchone()
        if not exists:
            conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        conn.close()


@pytest.fixture(scope="session")
def engine():
    settings = get_settings()
    _ensure_database_exists(settings.test_database_url)
    eng = create_engine(settings.test_database_url)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    connection = engine.connect()
    outer_transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    outer_transaction.rollback()
    connection.close()
