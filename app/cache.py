from app.db.models import Shim, ShimRule

_cache: dict[str, tuple[Shim, list[ShimRule]]] = {}


def get(slug: str) -> tuple[Shim, list[ShimRule]] | None:
    return _cache.get(slug)


def set(slug: str, shim: Shim, rules: list[ShimRule]) -> None:
    _cache[slug] = (shim, rules)


def invalidate(slug: str) -> None:
    _cache.pop(slug, None)


def clear() -> None:
    _cache.clear()
