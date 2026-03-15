from fastapi import APIRouter

router = APIRouter(prefix="/shims", tags=["shims"])


@router.get("/")
def list_shims():
    return []
