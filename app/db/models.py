from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class RuleOperator(str, Enum):
    eq = "=="
    neq = "!="
    contains = "contains"


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ShimBase(SQLModel):
    name: str
    slug: str
    target_url: str
    headers: str = Field(default="{}")


class Shim(ShimBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=_now)


class ShimCreate(ShimBase):
    pass


class ShimRuleBase(SQLModel):
    order: int = Field(default=0)
    field: str
    operator: RuleOperator
    value: str
    target_url: str


class ShimRule(ShimRuleBase, table=True):
    __tablename__ = "shim_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    shim_id: int = Field(foreign_key="shim.id", index=True)


class ShimRuleCreate(ShimRuleBase):
    pass


class WebhookLog(SQLModel, table=True):
    __tablename__ = "webhook_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    shim_id: int = Field(foreign_key="shim.id", index=True)
    received_at: datetime = Field(default_factory=_now)
    payload: str = Field(default="{}")  # raw JSON body
    status: Optional[int] = None  # HTTP status returned by target
    error: Optional[str] = None
