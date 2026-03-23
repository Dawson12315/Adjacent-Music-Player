from app.config import settings
from app.services.scanner import scan_directory


def main():
    print("Starting scan...")
    result = scan_directory(settings.music_library_path, limit=20)
    print(f"Done. Added {result['added']} tracks.")


if __name__ == "__main__":
    main()