from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.is_dev,
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_session():
    async with async_session() as session:
        yield session


async def init_db():
    """Create tables from ORM models (dev convenience; use Alembic in production)."""
    from backend.db.models import Base
    import sqlalchemy as sa

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Auto-add missing columns to existing tables (dev convenience)
        def _add_missing_columns(sync_conn):
            inspector = sa.inspect(sync_conn)
            for table_name, table in Base.metadata.tables.items():
                if not inspector.has_table(table_name):
                    continue
                existing = {c["name"] for c in inspector.get_columns(table_name)}
                for col in table.columns:
                    if col.name not in existing:
                        col_type = col.type.compile(sync_conn.dialect)
                        default = "DEFAULT ''" if isinstance(col.type, (sa.String, sa.Text)) else ""
                        if isinstance(col.type, (sa.JSON,)):
                            default = ""
                        if isinstance(col.type, (sa.Boolean,)):
                            default = "DEFAULT 1"
                        if isinstance(col.type, (sa.Integer,)):
                            default = "DEFAULT 0"
                        sync_conn.execute(sa.text(
                            f"ALTER TABLE {table_name} ADD COLUMN {col.name} {col_type} {default}"
                        ))

        await conn.run_sync(_add_missing_columns)
