
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))



import asyncio
import hashlib
import os
import secrets

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from gateway.database.models import (
    ApiClient,
    Plan,
    RateLimitPolicy,
    RouteDefinition,
    User,
)


DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not configured")


engine = create_async_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def seed_database():
    generated_keys = []

    async with SessionLocal() as session:
        async with session.begin():
            # 1. Plans
            plan_data = [
                {
                    "name": "free",
                    "requests_per_minute": 60,
                    "monthly_quota": 10_000,
                },
                {
                    "name": "premium",
                    "requests_per_minute": 600,
                    "monthly_quota": 500_000,
                },
            ]

            plans = {}
            for data in plan_data:
                plan = await session.scalar(
                    select(Plan).where(Plan.name == data["name"])
                )
                if plan is None:
                    plan = Plan(**data)
                    session.add(plan)
                    await session.flush()
                else:
                    plan.requests_per_minute = data["requests_per_minute"]
                    plan.monthly_quota = data["monthly_quota"]
                    plan.is_active = True

                plans[data["name"]] = plan

            # 2. Users
            user_data = [
                {"email": "alice@example.com", "name": "Alice"},
                {"email": "bob@example.com", "name": "Bob"},
            ]

            users = {}
            for data in user_data:
                user = await session.scalar(
                    select(User).where(User.email == data["email"])
                )
                if user is None:
                    user = User(**data)
                    session.add(user)
                    await session.flush()
                else:
                    user.name = data["name"]
                    user.is_active = True

                users[data["email"]] = user

            # 3. API clients and hashed API keys
            client_data = [
                {
                    "name": "alice-dev-client",
                    "email": "alice@example.com",
                    "plan": "free",
                },
                {
                    "name": "bob-premium-client",
                    "email": "bob@example.com",
                    "plan": "premium",
                },
            ]

            for data in client_data:
                client = await session.scalar(
                    select(ApiClient).where(
                        ApiClient.name == data["name"],
                        ApiClient.owner_user_id
                        == users[data["email"]].id,
                    )
                )

                if client is None:
                    prefix = f"gk_{secrets.token_hex(4)}"
                    secret = secrets.token_urlsafe(32)
                    plaintext_key = f"{prefix}.{secret}"

                    client = ApiClient(
                        name=data["name"],
                        owner=users[data["email"]],
                        plan=plans[data["plan"]],
                        key_prefix=prefix,
                        key_hash=hashlib.sha256(
                            plaintext_key.encode("utf-8")
                        ).hexdigest(),
                    )
                    session.add(client)
                    generated_keys.append(
                        (data["name"], plaintext_key, data["plan"])
                    )
                else:
                    client.plan = plans[data["plan"]]
                    client.is_active = True

            # 4. Routes
            route_data = [
                {
                    "name": "users",
                    "public_prefix": "/api/users",
                    "upstream_url": "http://user-service:8001",
                    "upstream_prefix": "/users",
                    "methods": ["GET"],
                },
                {
                    "name": "products",
                    "public_prefix": "/api/products",
                    "upstream_url": "http://product-service:8002",
                    "upstream_prefix": "/products",
                    "methods": ["GET"],
                },
                {
                    "name": "orders",
                    "public_prefix": "/api/orders",
                    "upstream_url": "http://order-service:8003",
                    "upstream_prefix": "/orders",
                    "methods": ["GET"],
                },
            ]

            routes = {}
            for data in route_data:
                route = await session.scalar(
                    select(RouteDefinition).where(
                        RouteDefinition.name == data["name"]
                    )
                )
                if route is None:
                    route = RouteDefinition(**data)
                    session.add(route)
                    await session.flush()
                else:
                    for field, value in data.items():
                        setattr(route, field, value)
                    route.is_active = True

                routes[data["name"]] = route

            # 5. Default plan-level rate-limit policies
            for plan_name, plan in plans.items():
                policy = await session.scalar(
                    select(RateLimitPolicy).where(
                        RateLimitPolicy.plan_id == plan.id,
                        RateLimitPolicy.route_id.is_(None),
                    )
                )

                values = {
                    "requests_limit": plan.requests_per_minute,
                    "window_seconds": 60,
                    "is_active": True,
                }

                if policy is None:
                    session.add(
                        RateLimitPolicy(plan=plan, **values)
                    )
                else:
                    for field, value in values.items():
                        setattr(policy, field, value)

        # The transaction has committed successfully here.
        print("Seed data committed successfully.")

        for name, key, plan_name in generated_keys:
            print(f"\nNew API client: {name} ({plan_name})")
            print(f"API key (shown only once): {key}")

        if not generated_keys:
            print("No new API keys generated; existing keys were preserved.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed_database())
