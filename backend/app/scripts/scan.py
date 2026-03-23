from app.config import settings
from app.services.scanner import scan_directory


def main():
    print("Starting scan...")
    scan_directory(settings.music_library_path, limit=20)
    print("Done.")


if __name__ == "__main__":
    main()