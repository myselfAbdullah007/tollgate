.PHONY: install dev api dashboard test check key demo compose integration stop
install:
	python3 -m venv .venv
	.venv/bin/pip install -r apps/gateway/requirements-dev.lock
	.venv/bin/pip install --no-deps -e 'apps/gateway[dev]'
	npm ci --prefix apps/dashboard
key:
	@python3 -c "import base64,os; print('TOLLGATE_MASTER_KEY=' + base64.b64encode(os.urandom(32)).decode())"
api:
	TOLLGATE_DEMO=true .venv/bin/tollgate serve
dashboard:
	npm run dev --prefix apps/dashboard
dev:
	python3 scripts/dev.py
demo: dev
test:
	.venv/bin/pytest apps/gateway/tests -q
check:
	.venv/bin/ruff check --config apps/gateway/pyproject.toml apps/gateway
	.venv/bin/mypy --config-file apps/gateway/pyproject.toml apps/gateway/src
	npm run lint --prefix apps/dashboard
	npm run typecheck --prefix apps/dashboard
compose:
	docker compose --env-file .env -f deploy/docker-compose.yml up -d --build
integration:
	TEST_REDIS_URL=redis://localhost:63987/15 TEST_DATABASE_URL=postgresql+asyncpg://tollgate:tollgate-local-only@localhost:55487/tollgate .venv/bin/pytest apps/gateway/tests -q
stop:
	docker compose -f deploy/docker-compose.yml stop
