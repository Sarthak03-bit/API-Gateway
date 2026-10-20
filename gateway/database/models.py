
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    api_clients: Mapped[list["ApiClient"]] = relationship(
        back_populates="owner"
    )


class Plan(Base):
    __tablename__ = "plans"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False
    )
    requests_per_minute: Mapped[int] = mapped_column(
        Integer, nullable=False
    )
    monthly_quota: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    api_clients: Mapped[list["ApiClient"]] = relationship(
        back_populates="plan"
    )
    rate_limit_policies: Mapped[list["RateLimitPolicy"]] = relationship(
        back_populates="plan"
    )


class ApiClient(Base):
    __tablename__ = "api_clients"
    __table_args__ = (
        Index("ix_api_clients_key_prefix", "key_prefix"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id"), nullable=False
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("plans.id"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    key_prefix: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False
    )
    key_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    owner: Mapped["User"] = relationship(back_populates="api_clients")
    plan: Mapped["Plan"] = relationship(back_populates="api_clients")


class RouteDefinition(Base):
    __tablename__ = "route_definitions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    public_prefix: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False
    )
    upstream_url: Mapped[str] = mapped_column(
        String(500), nullable=False
    )
    upstream_prefix: Mapped[str] = mapped_column(
        String(255), nullable=False
    )
    methods: Mapped[list[str]] = mapped_column(
        JSON, default=lambda: ["GET"], nullable=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    rate_limit_policies: Mapped[list["RateLimitPolicy"]] = relationship(
        back_populates="route"
    )


class RateLimitPolicy(Base):
    __tablename__ = "rate_limit_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    plan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("plans.id"), nullable=False
    )
    route_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("route_definitions.id"), nullable=True
    )
    requests_limit: Mapped[int] = mapped_column(Integer, nullable=False)
    window_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, nullable=False
    )

    plan: Mapped["Plan"] = relationship(
        back_populates="rate_limit_policies"
    )
    route: Mapped["RouteDefinition"] = relationship(
        back_populates="rate_limit_policies"
    )
