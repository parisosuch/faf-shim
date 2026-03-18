"""In-memory cache for AppConfig — avoids a DB round-trip on every hot path."""

from dataclasses import dataclass, field


@dataclass
class _State:
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    log_retention_days: int = 30
    max_body_size_kb: int = 1024
    cleanup_interval_seconds: int = 3600


_state = _State()


def get() -> _State:
    return _state


def update(
    cors_origins: list[str] | None = None,
    log_retention_days: int | None = None,
    max_body_size_kb: int | None = None,
    cleanup_interval_seconds: int | None = None,
) -> None:
    if cors_origins is not None:
        _state.cors_origins = cors_origins
    if log_retention_days is not None:
        _state.log_retention_days = log_retention_days
    if max_body_size_kb is not None:
        _state.max_body_size_kb = max_body_size_kb
    if cleanup_interval_seconds is not None:
        _state.cleanup_interval_seconds = cleanup_interval_seconds
