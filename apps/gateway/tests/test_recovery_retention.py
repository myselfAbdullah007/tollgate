"""Snapshot ordering and bounded retention, without external services."""

import json
from unittest.mock import AsyncMock

import pytest
from tollgate.db import now, uid
from tollgate.worker import RECONCILE_EVENT_LIMIT, reconcile


class SnapshotRedis:
    def __init__(self, entries, after_read=None):
        self.entries = entries
        self.after_read = after_read
        self.committed = None
        self.locked = False

    async def set(self, *args, **kwargs):
        self.locked = True
        return True

    async def xrange(self, key, *, count):
        captured = self.entries[:count]
        if self.after_read:
            await self.after_read()
        return captured

    async def scan_iter(self, **kwargs):
        for key in ():
            yield key

    async def eval(self, script, key_count, *args):
        if "for i=2" in script:
            self.committed = dict(zip(args[2::2], args[3::2]))
        self.locked = False
        return 1


async def event_for(app):
    event = (await app.state.repo.logs())[0].copy()
    event.update(id=uid(), customer_id="retention-audit", created_at=now(), cost=123)
    return event


@pytest.mark.parametrize("commit_during_read", [False, True])
async def test_stream_snapshot_precedes_sql_and_deduplicates_delivery(app, commit_during_read):
    event = await event_for(app)

    async def commit():
        await app.state.repo.write_event(event)

    redis = SnapshotRedis(
        [("1-0", {"event": json.dumps(event)}), ("2-0", {"event": json.dumps(event)})],
        after_read=commit if commit_during_read else None,
    )
    fast = type("Fast", (), {"redis": redis})()
    assert await reconcile(app.state.repo, fast)
    key = f"spend:default:retention-audit:{event['created_at'][:7]}"
    assert redis.committed[key] == 123
    assert not redis.locked


async def test_rollup_snapshot_does_not_return_entire_ledger_identity_set(app):
    event = await event_for(app)
    await app.state.repo.write_event(event)
    totals, identities = await app.state.repo.ledger_snapshot([event])
    assert identities == {(event["id"], event["created_at"])}
    assert totals[f"default:retention-audit:{event['created_at'][:7]}"] == 123
    _, identities = await app.state.repo.ledger_snapshot([])
    assert not identities


async def test_oversized_backlog_defers_without_rewriting_counters_or_clearing_recovery():
    redis = SnapshotRedis([("1-0", {})] * (RECONCILE_EVENT_LIMIT + 1))
    repo = type(
        "Repo",
        (),
        {
            "recovery_records": AsyncMock(return_value=[]),
            "ledger_snapshot": AsyncMock(),
            "delete": AsyncMock(),
        },
    )()
    assert await reconcile(repo, type("Fast", (), {"redis": redis})()) is False
    repo.ledger_snapshot.assert_not_awaited()
    repo.delete.assert_not_awaited()
    assert redis.committed is None and not redis.locked
