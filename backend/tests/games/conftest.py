import asyncio
import os
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema

from backend.app.infra.db import create_schema
from backend.app.infra.settings import Settings
from backend.app.main import create_app

DATABASE_URL = os.environ.get("MLCHESS_TEST_DATABASE_URL")


@pytest.fixture
def pg_app():
    if not DATABASE_URL.startswith("postgresql+asyncpg://"):
        pytest.fail("Integration tests require PostgreSQL/asyncpg")
    schema = "test_a008_" + uuid4().hex
    base = create_async_engine(DATABASE_URL, poolclass=NullPool)
    engine = base.execution_options(schema_translate_map={None: schema})

    async def setup():
        async with base.begin() as connection:
            await connection.execute(CreateSchema(schema))
        await create_schema(engine)

    async def cleanup():
        assert schema.startswith("test_a008_") and len(schema) == 42
        async with base.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await base.dispose()

    asyncio.run(setup())
    app = create_app(
        Settings(
            environment="test", public_origin="http://testserver", dev_auth_enabled=True
        ),
        database_engine=engine,
    )
    try:
        yield app
    finally:
        asyncio.run(cleanup())
