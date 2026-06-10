"""Create or promote an admin user."""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import User


async def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote an admin user")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Admin")
    args = parser.parse_args()

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == args.email))
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                email=args.email,
                hashed_password=hash_password(args.password),
                full_name=args.name,
                is_admin=True,
            )
            db.add(user)
            action = "created"
        else:
            user.is_admin = True
            user.hashed_password = hash_password(args.password)
            action = "updated"

        await db.commit()
        print(f"Admin user {action}: {args.email}")


if __name__ == "__main__":
    asyncio.run(main())
