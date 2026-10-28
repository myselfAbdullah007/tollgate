"""Honest local benchmark. Run against a demo gateway with unused customer budget.

Use a high-RPM plan for >60 requests in a minute. This is full request latency,
not isolated gateway overhead. The script reports failures separately.
"""
import asyncio
import os
import statistics
import time
import httpx

async def main():
    latencies, failures = [], []
    async with httpx.AsyncClient(base_url=os.getenv('TOLLGATE_BASE_URL', 'http://localhost:8187'), timeout=30) as c:
        for i in range(40):
            start = time.perf_counter()
            r = await c.post('/v1/chat/completions', headers={
                'Authorization': 'Bearer ' + os.getenv('TOLLGATE_API_KEY', 'tg_live_demo_tollgate_local_only'),
                'X-Tollgate-Customer': 'benchmark-local'}, json={
                'model': 'smart', 'max_tokens': 64, 'temperature': 1,
                'messages': [{'role': 'user', 'content': 'Draft a short update.'}]})
            if r.is_success:
                latencies.append((time.perf_counter() - start) * 1000)
            else:
                failures.append(r.status_code)
    if latencies:
        values = sorted(latencies)
        print(f'n={len(values)} p50={statistics.median(values):.2f}ms p95={values[int(.95*(len(values)-1))]:.2f}ms failures={failures}')
    else:
        raise RuntimeError(f'No successful requests: {failures}')

asyncio.run(main())
