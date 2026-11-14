"""Runs migrations. The database URL comes from the settings module, never from alembic.ini."""

from logging.config import fileConfig

from alembic import context

from tessera.config import Settings
from tessera.data.db import Base, create_db_engine

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def run_migrations() -> None:
    engine = create_db_engine(Settings())
    with engine.connect() as connection:
        context.configure(
            connection=connection,
            # Lets `alembic revision --autogenerate` compare the tables in code with the database.
            target_metadata=Base.metadata,
            # SQLite can't change most table definitions in place; batch mode rebuilds the table.
            render_as_batch=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
