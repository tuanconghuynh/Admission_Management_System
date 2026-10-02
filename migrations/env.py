from alembic import context
from app.core.config import settings
from app.db.session import engine
from app.db.base import Base
import app.models

if context.is_offline_mode():
    raise RuntimeError("This baseline inspects legacy data; run migrations with a database connection")
def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

connection = context.config.attributes.get("connection")
if connection is not None:
    migrate(connection)
else:
    with engine.connect() as connection:
        migrate(connection)
