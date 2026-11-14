"""Database engine and sessions, built from the settings module."""

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from tessera.config import Settings


class Base(DeclarativeBase):
    """Parent class of every table. T-017 and T-018 add the tables."""


def create_db_engine(settings: Settings) -> Engine:
    engine = create_engine(
        settings.database_url.get_secret_value(),
        # FastAPI serves requests from several threads; SQLite must allow that.
        connect_args={"check_same_thread": False},
    )
    event.listen(engine, "connect", _enable_foreign_keys)
    return engine


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine)


def _enable_foreign_keys(dbapi_connection, _connection_record) -> None:
    # SQLite ignores foreign keys unless each new connection switches them on.
    dbapi_connection.execute("PRAGMA foreign_keys = ON")
