import hashlib
import hmac

import httpx
import respx
from tollgate.notifications import deliver, signature


def test_signature_contract():
    body = b'{"event":"fixture"}'
    expected = hmac.new(b"secret", b"123." + body, hashlib.sha256).hexdigest()
    assert signature("secret", "123", body) == f"t=123,v1={expected}"


@respx.mock
async def test_delivery_pins_validated_ip_and_signs(app, monkeypatch):
    from tollgate import notifications

    async def resolve(host, port):
        return "93.184.216.34"

    monkeypatch.setattr(notifications, "public_address", resolve)
    crypto = app.state.pipeline.providers.crypto
    await app.state.repo.put(
        "webhook",
        "budget",
        {"url": "https://example.com/hook", "enabled": True, "encrypted_secret": crypto.encrypt("secret")},
    )
    await app.state.repo.put(
        "alert",
        "fixture",
        {
            "payload": {"id": "fixture", "type": "customer.degraded"},
            "delivery_status": "pending",
            "attempts": 0,
            "next_attempt": 0,
        },
    )
    route = respx.post("https://93.184.216.34/hook").mock(return_value=httpx.Response(204))
    await deliver(app.state.repo, crypto, "default")
    assert route.called
    assert route.calls[0].request.headers["host"] == "example.com"
    assert "v1=" in route.calls[0].request.headers["x-tollgate-signature"]
    row = await app.state.repo.find("alert", "fixture")
    assert row["delivery_status"] == "delivered" and row["attempts"] == 1
    await deliver(app.state.repo, crypto, "default")
    assert route.call_count == 1
