"""Exercise a running Compose stack with only the built-in mock provider."""
import asyncio
import json
import uuid
import httpx


async def main():
    async with httpx.AsyncClient(base_url='http://localhost:8187', timeout=20) as c:
        ready = (await c.get('/readyz')).json()
        assert ready['storage'] == 'postgres' and ready['fast_path'] == 'redis', ready
        r = await c.post('/admin/v1/auth/login', json={'email': 'admin@tollgate.local', 'password': 'tollgate-demo-2026'})
        r.raise_for_status()
        c.headers['X-Tollgate-Admin'] = '1'
        suffix = "".join(chr(97 + int(c, 16)) for c in uuid.uuid4().hex)
        alias = 'smoke-' + suffix
        r = await c.post('/admin/v1/tenants/default/aliases', json={'name': alias, 'allow_degrade': True,
            'tiers': [['mock/outage', 'mock/backup'], ['mock/balanced'], ['mock/economy']]})
        r.raise_for_status()
        alias_id = r.json()['id']
        try:
            r = await c.post('/v1/chat/completions', headers={
                'Authorization': 'Bearer tg_live_demo_tollgate_local_only', 'X-Tollgate-Customer': 'smoke-' + suffix},
                json={'model': alias, 'stream': True, 'messages': [{'role': 'user', 'content': 'Email smoke@example.com'}]})
            r.raise_for_status()
            assert r.headers['x-tollgate-model-served'] == 'mock/backup'
            assert 'smoke@example.com' in r.text and '[EMAIL_' not in r.text and '[DONE]' in r.text
            for _ in range(40):
                rows = (await c.get('/admin/v1/tenants/default/logs', params={'customer': 'smoke-' + suffix})).json()['items']
                if rows:
                    break
                await asyncio.sleep(.1)
            assert len(rows) == 1 and rows[0]['fallback_count'] == 1
            assert 'smoke@example.com' not in json.dumps(rows)
            print('PASS: PostgreSQL/Redis readiness, stream restoration, forced fallback, durable worker ledger, no prompt PII')
        finally:
            await c.delete('/admin/v1/tenants/default/aliases/' + alias_id)

asyncio.run(main())
