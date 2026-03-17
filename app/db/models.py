from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from sqlmodel import Field, SQLModel


class RuleOperator(str, Enum):
    eq = "=="
    neq = "!="
    contains = "contains"


class SignatureAlgorithm(str, Enum):
    token = "token"  # direct header value comparison
    sha256 = "sha256"  # HMAC-SHA256 of the request body


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ShimBase(SQLModel):
    name: str
    slug: str
    target_url: str
    headers: str = Field(default="{}")
    secret: Optional[str] = None
    signature_header: Optional[str] = None
    signature_algorithm: Optional[SignatureAlgorithm] = None
    body_template: Optional[str] = None
    sample_payload: Optional[str] = None


class Shim(ShimBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=_now)


class ShimCreate(ShimBase):
    pass


class ShimUpdate(SQLModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    target_url: Optional[str] = None
    headers: Optional[str] = None
    secret: Optional[str] = None
    signature_header: Optional[str] = None
    signature_algorithm: Optional[SignatureAlgorithm] = None
    body_template: Optional[str] = None
    sample_payload: Optional[str] = None


class ShimVariable(SQLModel, table=True):
    __tablename__ = "shim_variable"

    id: Optional[int] = Field(default=None, primary_key=True)
    shim_id: int = Field(foreign_key="shim.id", index=True)
    key: str
    value: str


class ShimVariableCreate(SQLModel):
    key: str
    value: str


class ShimVariableUpdate(SQLModel):
    key: Optional[str] = None
    value: Optional[str] = None


class ShimRuleBase(SQLModel):
    order: int = Field(default=0)
    field: str
    operator: RuleOperator
    value: str
    target_url: str
    body_template: Optional[str] = None


class ShimRule(ShimRuleBase, table=True):
    __tablename__ = "shim_rule"

    id: Optional[int] = Field(default=None, primary_key=True)
    shim_id: int = Field(foreign_key="shim.id", index=True)


class ShimRuleCreate(ShimRuleBase):
    pass


class ShimRuleUpdate(SQLModel):
    order: Optional[int] = None
    field: Optional[str] = None
    operator: Optional[RuleOperator] = None
    value: Optional[str] = None
    target_url: Optional[str] = None
    body_template: Optional[str] = None


class ShimRead(ShimBase):
    id: int
    created_at: datetime
    rules: list["ShimRule"] = []
    variables: list["ShimVariable"] = []


class WebhookLog(SQLModel, table=True):
    __tablename__ = "webhook_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    shim_id: int = Field(foreign_key="shim.id", index=True)
    received_at: datetime = Field(default_factory=_now)
    payload: str = Field(default="{}")  # raw JSON body
    target_url: Optional[str] = None  # where the payload was forwarded
    status: Optional[int] = None  # HTTP status returned by target
    error: Optional[str] = None
