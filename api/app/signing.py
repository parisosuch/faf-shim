import hashlib
import hmac

from app.db.models import Shim, SignatureAlgorithm


def verify_signature(shim: Shim, headers: dict, body: bytes) -> bool:
    """
    Returns True if the request is authorised to trigger this shim.
    If the shim has no secret configured, all requests are accepted.
    On failure, always returns False — never raises — so the caller can
    silently accept without leaking whether the slug exists.
    """
    if not shim.secret or not shim.signature_header:
        return True

    header_value = headers.get(shim.signature_header.lower())
    if not header_value:
        return False

    if shim.signature_algorithm == SignatureAlgorithm.token:
        return hmac.compare_digest(header_value, shim.secret)

    if shim.signature_algorithm == SignatureAlgorithm.sha256:
        expected = (
            "sha256=" + hmac.new(shim.secret.encode(), body, hashlib.sha256).hexdigest()
        )
        return hmac.compare_digest(header_value, expected)

    return False
