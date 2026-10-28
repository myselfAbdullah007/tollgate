import pytest
from httpx import ASGITransport, AsyncClient
from tollgate.config import Settings
from tollgate.main import create_app


@pytest.fixture
async def app(tmp_path):
    app = create_app(Settings(demo=True, database_url=f"sqlite+aiosqlite:///{tmp_path}/test.db"))
    async with app.router.lifespan_context(app):
        yield app


@pytest.fixture
async def client(app):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def admin(client):
    r = await client.post(
        "/admin/v1/auth/login", json={"email": "admin@tollgate.local", "password": "tollgate-demo-2026"}
    )
    assert r.status_code == 200
    client.headers["X-Tollgate-Admin"] = "1"
    return client


@pytest.fixture
def auth():
    return {
        "Authorization": "Bearer tg_live_demo_tollgate_local_only",
        "X-Tollgate-Customer": "test_customer",
    }
