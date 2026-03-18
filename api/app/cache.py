from app.db.models import Shim, ShimRule, ShimVariable

_cache: dict[str, tuple[Shim, list[ShimRule], list[ShimVariable]]] = {}


def get(slug: str) -> tuple[Shim, list[ShimRule], list[ShimVariable]] | None:
    return _cache.get(slug)


def set(
    slug: str, shim: Shim, rules: list[ShimRule], variables: list[ShimVariable]
) -> None:
    _cache[slug] = (shim, rules, variables)


def invalidate(slug: str) -> None:
    _cache.pop(slug, None)


def clear() -> None:
    _cache.clear()
