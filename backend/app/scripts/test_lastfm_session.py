from app.db import SessionLocal
from app.models.app_setting import AppSetting
from app.services.lastfm import get_lastfm_session


def main():
    db = SessionLocal()

    try:
        settings = db.query(AppSetting).first()

        if not settings:
            print("No settings found")
            return

        token = input("Enter Last.fm token: ").strip()

        result = get_lastfm_session(
            token=token,
            api_key=settings.lastfm_api_key or "",
            api_secret=settings.lastfm_api_secret or "",
        )

        print(result)

    finally:
        db.close()


if __name__ == "__main__":
    main()