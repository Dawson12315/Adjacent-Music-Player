from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.db import Base


class PlaybackDevice(Base):
    """One client that can hold the user's playback: a phone, a browser, a tablet.

    Identity is device-level, not account-level: the id (`device_id`) is minted
    once by the client and reused across sign-ins, so a phone keeps its place
    in the picker when a second person signs into it. The row is per
    (user, device_id), because the same browser can be two people's device, and
    each sees only their own.

    CarPlay is deliberately not a device of its own — it is the phone's screen
    in the car, so the phone's row carries a context the pickers read instead.
    """

    __tablename__ = "playback_devices"
    __table_args__ = (
        UniqueConstraint("user_id", "device_id", name="uq_playback_device_user_device"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # The client-minted identifier; stable for the life of the install.
    device_id = Column(String(64), nullable=False)
    name = Column(String(80), nullable=False, default="")
    # "phone", "tablet", "web".
    kind = Column(String(16), nullable=False, default="web")
    platform = Column(String(32), nullable=True)
    app_version = Column(String(24), nullable=True)
    # "carplay" while the phone is the screen in a car, else null; the
    # pickers render "This iPhone · CarPlay" from it. A property of the
    # moment, carried on hello, not an identity.
    context = Column(String(16), nullable=True)

    # Bumped on every hello, report and heartbeat; half of how "online" is
    # decided.
    last_seen_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    # When this device's control socket last went away, and null while it has
    # one (or has never had one). A device that held a socket and lost it is
    # unreachable *now*, whatever its last-seen says, so the music must not be
    # handed to it; a polling client never sets this and keeps the last-seen
    # grace. Nullable so it can be added to a table that already has rows.
    away_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    user = relationship("User")
