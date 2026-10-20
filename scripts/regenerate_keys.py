
import asyncio
import hashlib
import secrets
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select
from gateway.database.connection import AsyncSessionLocal
from gateway.database.models import ApiClient


async def regenerate_keys():
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for client_name in (
                "alice-dev-client",
                "bob-premium-client",
            ):
                client = await session.scalar(
                    select(ApiClient).where(
                        ApiClient.name == client_name
                    )
                )

                if client is None:
                    print(f"Client not found: {client_name}")
                    continue

                # Generate a fresh key with a unique lookup prefix.
                prefix = f"gk_{secrets.token_hex(4)}"
                secret = secrets.token_urlsafe(32)
                api_key = f"{prefix}.{secret}"

                client.key_prefix = prefix
                client.key_hash = hashlib.sha256(
                    api_key.encode("utf-8")
                ).hexdigest()

                print(f"\nClient: {client.name}")
                print(f"New API key (save securely): {api_key}")

    print("\nKey updates committed successfully.")


if __name__ == "__main__":
    asyncio.run(regenerate_keys())
