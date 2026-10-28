"""Request-local PII vault. Never persist instances or original input."""

import ipaddress
import re
from collections import Counter


def luhn(value):
    digits = [int(c) for c in value if c.isdigit()]
    return (
        13 <= len(digits) <= 19
        and sum((n * 2 - 9 if n > 4 else n * 2) if i % 2 else n for i, n in enumerate(reversed(digits))) % 10
        == 0
    )


def iban(value):
    text = re.sub(r"\s", "", value).upper()
    if not 15 <= len(text) <= 34:
        return False
    rotated = text[4:] + text[:4]
    return int("".join(str(ord(c) - 55) if c.isalpha() else c for c in rotated)) % 97 == 1


def mynumber(value):
    digits = [int(c) for c in value]
    total = sum(n * w for n, w in zip(reversed(digits[:11]), [2, 3, 4, 5, 6, 7, 2, 3, 4, 5, 6]))
    check = 11 - total % 11
    return digits[-1] == (0 if check >= 10 else check)


def ip(value):
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


DETECTORS = [
    ("EMAIL", re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}"), None),
    ("SECRET", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{16,}|AKIA[A-Z0-9]{16}|ghp_[A-Za-z0-9]{30,})\b"), None),
    ("CNIC", re.compile(r"\b\d{5}-\d{7}-\d\b"), None),
    ("CARD", re.compile(r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"), luhn),
    ("IBAN", re.compile(r"\b[A-Z]{2}\d{2}(?: ?[A-Z0-9]){11,30}\b"), iban),
    ("MYNUMBER", re.compile(r"\b\d{12}\b"), mynumber),
    ("IP", re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"), ip),
    (
        "PHONE",
        re.compile(
            r"(?<![\w\d])(?:\+\d{1,3}[ -]?)?(?:\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}|0\d{3}[ -]?\d{7})(?!\d)"
        ),
        None,
    ),
]
TOKEN = re.compile(r"\[(?:EMAIL|SECRET|CNIC|CARD|IBAN|MYNUMBER|IP|PHONE)_\d+\]")


class BlockedPII(Exception):
    pass


class Vault:
    def __init__(self, mode="reversible", block_categories=None):
        self.mode = mode
        self.block_categories = set(block_categories or [])
        self.values: dict[str, str] = {}
        self.reverse: dict[tuple[str, str], str] = {}
        self.counts: Counter = Counter()

    def redact(self, text: str) -> str:
        if self.mode == "off" and not self.block_categories:
            return text
        spans: list[tuple[int, int, str, str]] = []
        for category, pattern, validator in DETECTORS:
            for m in pattern.finditer(text):
                if validator and not validator(m.group()):
                    continue
                if not any(m.start() < end and m.end() > start for start, end, *_ in spans):
                    spans.append((m.start(), m.end(), category, m.group()))
        if self.mode == "off":
            for _, _, category, _ in spans:
                if category in self.block_categories:
                    raise BlockedPII(category)
            return text
        output, pos = [], 0
        for start, end, category, value in sorted(spans):
            if category in self.block_categories or self.mode == "block":
                raise BlockedPII(category)
            self.counts[category] += 1
            pair = (category, value)
            if pair not in self.reverse:
                index = 1 + sum(c == category for c, _ in self.reverse)
                token = f"[{category}_{index}]"
                self.reverse[pair] = token
                self.values[token] = value
            output.extend(
                [text[pos:start], self.reverse[pair] if self.mode == "reversible" else "[redacted]"]
            )
            pos = end
        output.append(text[pos:])
        return "".join(output)

    def transform(self, value):
        if isinstance(value, str):
            # Protect literal tokens injected by callers from colliding with vault tokens.
            return self.redact(TOKEN.sub("[redacted]", value))
        if isinstance(value, list):
            return [self.transform(v) for v in value]
        if isinstance(value, dict):
            return {k: self.transform(v) for k, v in value.items()}
        return value

    def restore(self, text):
        return TOKEN.sub(lambda m: self.values.get(m.group(), "[redacted]"), text)


class StreamRestorer:
    MAX_TOKEN_LEN = 64

    def __init__(self, vault):
        self.vault = vault
        self.buf = ""

    def feed(self, chunk):
        self.buf += chunk
        start = self.buf.rfind("[")
        if start >= 0 and "]" not in self.buf[start:] and len(self.buf) - start <= self.MAX_TOKEN_LEN:
            safe, self.buf = self.buf[:start], self.buf[start:]
        else:
            safe, self.buf = self.buf, ""
        return self.vault.restore(safe)

    def flush(self):
        value, self.buf = self.vault.restore(self.buf), ""
        return value
