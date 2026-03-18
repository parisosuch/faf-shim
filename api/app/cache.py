from app.db.models import Shim, ShimRule, ShimVariable

_cache: dict[str, tuple[Shim, list[ShimRule], list[ShimVariable]]] = {}
_hits: int = 0
_misses: int = 0


def get(slug: str) -> tuple[Shim, list[ShimRule], list[ShimVariable]] | None:
    global _hits, _misses
    result = _cache.get(slug)
    if result is not None:
        _hits += 1
    else:
        _misses += 1
    return result


def get_stats() -> tuple[int, int]:
    """Return (hits, misses) since last clear."""
    return _hits, _misses


def set(
    slug: str, shim: Shim, rules: list[ShimRule], variables: list[ShimVariable]
) -> None:
    _cache[slug] = (shim, rules, variables)


def invalidate(slug: str) -> None:
    _cache.pop(slug, None)


def clear() -> None:
    global _hits, _misses
    _cache.clear()
    _hits = 0
    _misses = 0
