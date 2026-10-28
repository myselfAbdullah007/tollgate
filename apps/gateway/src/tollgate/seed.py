import random
from datetime import UTC, datetime, timedelta

from .db import uid
from .security import digest, passwords


async def seed(repo, settings):
    if not await repo.find("user", settings.admin_email, "global"):
        await repo.put(
            "user",
            settings.admin_email,
            {
                "password_hash": passwords.hash(settings.admin_password or "tollgate-demo-2026"),
                "role": "owner",
            },
            "global",
        )
    if await repo.find("tenant", "default", "global"):
        return
    await repo.put(
        "tenant", "default", {"display_name": "Acme workspace", "rpm": 1000, "default_plan": "Pro"}, "global"
    )
    for name, budget, rpm in [("Free", 5, 20), ("Pro", 50, 60), ("Business", 250, 180)]:
        await repo.put(
            "plan",
            name,
            {
                "monthly_budget": budget * 1000000,
                "rpm": rpm,
                "degradation": [{"at": 0.8, "tier": 1}, {"at": 0.95, "tier": 2}],
                "on_exhausted": "block",
                "overage_cap": 0,
                "pii_mode": "reversible",
                "pii_block_categories": ["CARD"],
            },
        )
    for name in ["smart", "fast", "clinical-summary"]:
        await repo.put(
            "alias",
            name,
            {
                "allow_degrade": name != "clinical-summary",
                "tiers": [["mock/premium", "mock/backup"], ["mock/balanced"], ["mock/economy"]]
                if name != "fast"
                else [["mock/balanced", "mock/economy"]],
            },
        )
    if settings.demo:
        key = "tg_live_demo_tollgate_local_only"
        await repo.put(
            "key",
            "Local development",
            {"key_hash": digest(key), "prefix": key[:16], "revoked_at": None, "last_used_at": None},
        )
        customers = [
            ("cus_acme", "Acme Inc.", "Pro", 0.46),
            ("cus_linear", "Linear Labs", "Business", 0.28),
            ("cus_notion", "Notion Studio", "Pro", 0.87),
            ("cus_vercel", "Vercel Team", "Business", 0.61),
            ("cus_orbit", "Orbit Design", "Free", 0.97),
            ("cus_figma", "Figma Collective", "Pro", 0.33),
            ("cus_atlas", "Atlas Health", "Business", 0.15),
            ("cus_nova", "Nova Analytics", "Pro", 0.72),
        ]
        rng = random.Random(42)
        for external, display, plan, ratio in customers:
            await repo.put(
                "customer", external, {"display_name": display, "plan": plan, "budget_override": None}
            )
            budget = {"Free": 5, "Pro": 50, "Business": 250}[plan] * 1000000
            total = int(budget * ratio)
            weights = [rng.randint(30, 100) * (1 + i // 8) for i in range(28)]
            costs = [total * weight // sum(weights) for weight in weights]
            costs[-1] += total - sum(costs)
            for i in range(28):
                stamp = datetime.now(UTC) - timedelta(hours=(27 - i) * 12)
                # Keep illustrative data inside the current billing period.
                stamp = max(stamp, datetime.now(UTC).replace(day=1, hour=0, minute=0, second=0))
                tier = 2 if ratio >= 0.95 else 1 if ratio >= 0.8 else 0
                await repo.write_event(
                    {
                        "id": uid(),
                        "tenant_id": "default",
                        "customer_id": external,
                        "alias": "smart" if i % 3 else "fast",
                        "tier_served": tier,
                        "provider": "mock",
                        "model": ["mock/premium", "mock/balanced", "mock/economy"][tier],
                        "status": "success",
                        "http_status": 200,
                        "input_tokens": rng.randint(100, 1900),
                        "output_tokens": rng.randint(100, 800),
                        "tokens_estimated": True,
                        "cost": costs[i],
                        "latency_ms": rng.randint(120, 900),
                        "ttft_ms": rng.randint(30, 100),
                        "cache_hit": i % 7 == 0,
                        "fallback_count": 0,
                        "pii_counts": {"EMAIL": 1} if i % 3 == 0 else {},
                        "error_code": None,
                        "created_at": stamp.isoformat(),
                        "demo_seed": True,
                    }
                )
    if settings.bootstrap_file:
        import yaml

        with open(settings.bootstrap_file) as f:
            config = yaml.safe_load(f)
        for kind, plural in [("plan", "plans"), ("alias", "aliases")]:
            for row in config.get(plural, []):
                await repo.put(kind, row["name"], {k: v for k, v in row.items() if k != "name"})
