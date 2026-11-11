"""Validate pull-only Compose configuration without starting containers."""

import json
import os
import subprocess
from pathlib import Path


def main():
    root = Path(__file__).resolve().parents[1]
    # Synthetic test values only. Never print rendered configuration or load .env.
    values = {
        "TOLLGATE_IMAGE": "example/tollgate:0.2.0",
        "TOLLGATE_DASHBOARD_IMAGE": "example/tollgate-dashboard:0.2.0",
        "TOLLGATE_DATABASE_URL": "postgresql+asyncpg://test:test@database.invalid/tollgate",
        "TOLLGATE_REDIS_URL": "redis://redis.invalid:6379/0",
        "TOLLGATE_ADMIN_EMAIL": "test@example.invalid",
        "TOLLGATE_ADMIN_PASSWORD": "distribution-test-only",
        "TOLLGATE_MASTER_KEY": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
    }
    env = {k: v for k, v in os.environ.items() if not k.startswith(("TOLLGATE_", "COMPOSE_"))}
    env.update(values)
    command = [
        "docker", "compose", "--env-file", os.devnull,
        "-f", str(root / "deploy/compose.images.yml"), "--profile", "dashboard",
        "config", "--format", "json",
    ]
    rendered = subprocess.run(command, env=env, capture_output=True, text=True, check=True)
    config = json.loads(rendered.stdout)
    assert config["name"] == "tollgate"
    services = config["services"]
    assert set(services) == {"gateway", "worker", "migrate", "dashboard"}
    for service in services.values():
        assert "image" in service and "build" not in service
        assert not service.get("volumes"), "Deployment must not require source mounts"
    for name, command_name in [("gateway", "serve"), ("worker", "worker"), ("migrate", "migrate")]:
        service = services[name]
        assert service["image"] == values["TOLLGATE_IMAGE"]
        assert service["command"] == [command_name]
        assert service["environment"]["TOLLGATE_DEMO"] == "false"
        assert service["environment"]["TOLLGATE_DATABASE_URL"] == values["TOLLGATE_DATABASE_URL"]
        assert service["environment"]["TOLLGATE_REDIS_URL"] == values["TOLLGATE_REDIS_URL"]
        if name != "migrate":
            assert service["depends_on"]["migrate"]["condition"] == "service_completed_successfully"
    assert services["worker"]["healthcheck"]["test"][0] == "CMD"
    assert services["migrate"]["healthcheck"]["disable"]
    assert services["dashboard"]["profiles"] == ["dashboard"]
    for name in ("gateway", "dashboard"):
        assert services[name]["ports"][0]["host_ip"] == "127.0.0.1"
    for key in values:
        missing = env.copy()
        missing.pop(key)
        result = subprocess.run(command, env=missing, capture_output=True, text=True, check=False)
        assert result.returncode != 0 and key in result.stderr, key
    print("PASS: pull-only services, shared backend image, external stores, startup ordering,")
    print("      worker health, optional dashboard, loopback ports, and 7 required settings")


if __name__ == "__main__":
    main()
