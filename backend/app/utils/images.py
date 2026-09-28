"""What counts as an image upload.

The upload endpoints used to trust the client's declared content type and
extension and store whatever bytes followed — twenty megabytes of zeros as a
"PNG", an SVG with a script in it as a "JPEG". The bytes are checked now: the
file has to start like a JPEG, PNG, WebP or GIF, and the extension it is kept
under follows from that, not from the filename.
"""

from fastapi import HTTPException, UploadFile

# Bounded here as well as by the body-size middleware; artwork is a cover,
# not a photo archive.
MAX_ARTWORK_BYTES = 8 * 1024 * 1024

_SIGNATURES = (
    (b"\xff\xd8\xff", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", ".png"),
    (b"GIF87a", ".gif"),
    (b"GIF89a", ".gif"),
)


def sniff_image_extension(head: bytes) -> str | None:
    for signature, extension in _SIGNATURES:
        if head.startswith(signature):
            return extension

    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return ".webp"

    return None


def read_validated_image(file: UploadFile, max_bytes: int = MAX_ARTWORK_BYTES) -> tuple[bytes, str]:
    """The upload's bytes and the extension they warrant.

    Raises 400 for anything that is not an image and 413 for one too large.
    Reads the whole file: the callers write it out in one go anyway, and the
    size cap keeps that bounded.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    data = file.file.read(max_bytes + 1)

    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Image is too large (limit {max_bytes // (1024 * 1024)} MB).",
        )

    extension = sniff_image_extension(data[:16])

    if extension is None:
        raise HTTPException(status_code=400, detail="File must be a JPEG, PNG, WebP or GIF image")

    return data, extension
