import pytest

from backend.app.infra.settings import Settings


@pytest.fixture
def settings(tmp_path):
    return Settings(
        environment="test",
        public_origin="http://testserver",
        dev_auth_enabled=True,
        database_url="sqlite+aiosqlite:///" + (tmp_path / "coach.db").as_posix(),
        database_auto_create=True,
    )
