from alembic import context

with context.config.attributes["engine"].begin() as connection:
    context.configure(connection=connection)
    context.run_migrations()
