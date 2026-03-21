import json
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel
from app.utils import now


class RuleOperator(str, Enum):
    eq = "=="
    neq = "!="
    contains = "contains"


class SignatureAlgorithm(str, Enum):
    token = "token"  # direct header value comparison
    sha256 = "sha256"  # HMAC-SHA256 of the request body


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
    # Per-shim config overrides (None = use global AppConfig default)
    max_body_size_kb: Optional[int] = None
    log_retention_days: Optional[int] = None
    rate_limit_requests: Optional[int] = None
    rate_limit_window_seconds: Optional[int] = None


class Shim(ShimBase, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=now)


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
    max_body_size_kb: Optional[int] = None
    log_retention_days: Optional[int] = None
    rate_limit_requests: Optional[int] = None
    rate_limit_window_seconds: Optional[int] = None


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
    received_at: datetime = Field(default_factory=now)
    payload: str = Field(default="{}")  # raw JSON body
    target_url: Optional[str] = None  # where the payload was forwarded
    status: Optional[int] = None  # HTTP status returned by target
    duration_ms: Optional[int] = None  # forward round-trip time in milliseconds
    error: Optional[str] = None


class AppConfig(SQLModel, table=True):
    __tablename__ = "app_config"

    id: Optional[int] = Field(default=None, primary_key=True)
    cors_origins: str = Field(default='["*"]')  # JSON array of allowed origins
    log_retention_days: int = Field(default=30)  # 0 = keep forever
    max_body_size_kb: int = Field(default=1024)  # global default body size limit
    cleanup_interval_seconds: int = Field(
        default=3600
    )  # how often the cleanup task runs

    def cors_origins_list(self) -> list[str]:
        return json.loads(self.cors_origins)


class AppConfigRead(SQLModel):
    cors_origins: list[str]
    log_retention_days: int
    max_body_size_kb: int
    cleanup_interval_seconds: int


class AppConfigUpdate(SQLModel):
    cors_origins: Optional[list[str]] = None
    log_retention_days: Optional[int] = None
    max_body_size_kb: Optional[int] = None
    cleanup_interval_seconds: Optional[int] = None
