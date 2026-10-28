import base64
import os

import pytest
from hypothesis import given
from hypothesis import strategies as st
from tollgate.redaction import BlockedPII, StreamRestorer, Vault, iban, luhn, mynumber
from tollgate.security import Crypto, digest, new_key, passwords, verify_password


@pytest.mark.parametrize(
    "text,category",
    [
        ("Email ali@example.com", "EMAIL"),
        ("Call 0300-1234567", "PHONE"),
        ("ID 35202-1234567-1", "CNIC"),
        ("Card 4111 1111 1111 1111", "CARD"),
        ("IBAN GB82WEST12345698765432", "IBAN"),
        ("IP 192.168.1.10", "IP"),
        ("sk-abcdefghijklmnopqrstuvwxyz", "SECRET"),
        ("ID 123456789018", "MYNUMBER"),
    ],
)
def test_detectors_roundtrip(text, category):
    v = Vault()
    redacted = v.redact(text)
    assert f"[{category}_1]" in redacted
    assert v.restore(redacted) == text


def test_repeated_value_and_order():
    v = Vault()
    assert v.redact("a@x.com b@y.com a@x.com") == "[EMAIL_1] [EMAIL_2] [EMAIL_1]"
    assert v.counts["EMAIL"] == 3


def test_unknown_token_and_injection():
    v = Vault()
    assert v.restore("[EMAIL_7]") == "[redacted]"
    value = v.transform("[EMAIL_1] ali@example.com")
    assert value == "[redacted] [EMAIL_1]"


def test_modes_and_block():
    assert Vault("off").redact("a@x.com") == "a@x.com"
    assert Vault("mask").redact("a@x.com") == "[redacted]"
    with pytest.raises(BlockedPII):
        Vault("reversible", ["CARD"]).redact("4111 1111 1111 1111")
    with pytest.raises(BlockedPII):
        Vault("block").redact("a@x.com")


def test_structured_tool_arguments():
    v = Vault()
    out = v.transform(
        {
            "messages": [
                {
                    "content": [{"type": "text", "text": "a@x.com"}],
                    "tool_calls": [{"function": {"arguments": '{"email":"a@x.com"}'}}],
                }
            ]
        }
    )
    assert "a@x.com" not in str(out)
    assert len(v.values) == 1


@given(st.lists(st.integers(min_value=1, max_value=90), min_size=1, max_size=50))
def test_stream_random_chunk_boundaries(sizes):
    v = Vault()
    source = "Hello ali@example.com, call 0300-1234567. Use [brackets] and [EMAIL_99]. End ["
    redacted = v.redact(source)
    expected = v.restore(redacted)
    restorer, out, offset = StreamRestorer(v), [], 0
    for size in sizes:
        out.append(restorer.feed(redacted[offset : offset + size]))
        offset += size
    out.append(restorer.feed(redacted[offset:]))
    out.append(restorer.flush())
    assert "".join(out) == expected


def test_every_single_split():
    v = Vault()
    redacted = v.redact("Draft to ali@example.com and a@x.com then [EMAIL_7]")
    for i in range(len(redacted) + 1):
        r = StreamRestorer(v)
        assert r.feed(redacted[:i]) + r.feed(redacted[i:]) + r.flush() == v.restore(redacted)


def test_checksums():
    assert luhn("4111111111111111")
    assert not luhn("4111111111111112")
    assert iban("GB82WEST12345698765432")
    assert not iban("GB83WEST12345698765432")
    assert mynumber("123456789018")
    assert not mynumber("123456789019")


def test_crypto_keys_passwords():
    crypto = Crypto(base64.b64encode(os.urandom(32)).decode())
    encrypted = crypto.encrypt("sk-secret")
    assert "sk-secret" not in encrypted and crypto.decrypt(encrypted) == "sk-secret"
    assert crypto.encrypt("sk-secret") != encrypted
    raw = new_key()
    assert raw.startswith("tg_live_") and raw not in digest(raw)
    encoded = passwords.hash("good-password")
    assert verify_password(encoded, "good-password") and not verify_password(encoded, "bad")
