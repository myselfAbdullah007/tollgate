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
    parser.add_argument("command", choices=["serve", "worker", "migrate", "seed", "key"])
    args = parser.parse_args()
    if args.command == "key":
        print("TOLLGATE_MASTER_KEY=" + base64.b64encode(os.urandom(32)).decode())
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
