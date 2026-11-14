from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from tessera.config import Settings
from tessera.data.db import create_db_engine, create_session_factory

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"


def test_upgrade_head_on_a_fresh_database(env):
    # `env` points DATABASE_URL at a new, empty SQLite file for this test.
    config = Config(ALEMBIC_INI)

    command.upgrade(config, "head")

    head = ScriptDirectory.from_config(config).get_current_head()
    with create_session_factory(create_db_engine(Settings()))() as session:
        version = session.execute(
            text("SELECT version_num FROM alembic_version")
        ).scalar_one()
    assert version == head


def test_sessions_have_foreign_keys_switched_on(env):
    with create_session_factory(create_db_engine(Settings()))() as session:
        assert session.execute(text("PRAGMA foreign_keys")).scalar_one() == 1
