from fastapi import APIRouter

router = APIRouter()


@router.get("/tracks", tags=["tracks"])
def list_tracks():
    return []