import argparse
import asyncio
import base64
import os

from .config import Settings
from .db import Database
from .fastpath import FastPath
from .repository import Repository


def main():
    parser = argparse.ArgumentParser(prog="tollgate")
    parser.add_argument(
        "command",
        choices=[
            "serve",
            "worker",
            "migrate",
            "seed",
            "key",
            "reset-password",
            "rotate-master-key",
            "validate-config",
        ],
    )
    parser.add_argument(
        "--maintenance", action="store_true", help="Confirm gateway and worker are stopped for key rotation"
    )
    parser.add_argument("--file", default="config/bootstrap.example.yaml")
    args = parser.parse_args()
    if args.command == "key":
        print("TOLLGATE_MASTER_KEY=" + base64.b64encode(os.urandom(32)).decode())
        return
    if args.command == "validate-config":
        from pathlib import Path

        import yaml

        from .schemas import Bootstrap

        body = Bootstrap.model_validate(yaml.safe_load(Path(args.file).read_text()))
        print(
            f"Valid configuration: {len(body.plans)} plans, {len(body.aliases)} aliases. No changes applied."
        )
        return
    settings = Settings()
    settings.validate_secrets()
    if args.command == "serve":
        import uvicorn

        from .main import create_app

        uvicorn.run(create_app(settings), host="0.0.0.0", port=settings.port)
        return

    async def run():
        db = Database(settings.database_url)
        try:
            if args.command == "migrate":
                from .seed import seed

                await db.migrate()
                await seed(Repository(db), settings)
            elif args.command == "seed":
                from .seed import seed

                await db.migrate()
                await seed(Repository(db), settings)
            elif args.command == "reset-password":
                from .maintenance import reset_password

                await reset_password(Repository(db), settings.admin_email)
            elif args.command == "rotate-master-key":
                if not args.maintenance:
                    raise RuntimeError("Stop only Tollgate gateway and worker, then pass --maintenance")
                from .maintenance import rotate_master_key

                await rotate_master_key(db, settings)
            else:
                from .worker import run_worker

                fast = FastPath(settings.redis_url)
                try:
                    await run_worker(Repository(db), fast)
                finally:
                    if fast.redis:
                        await fast.redis.aclose()
        finally:
            await db.engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    main()
