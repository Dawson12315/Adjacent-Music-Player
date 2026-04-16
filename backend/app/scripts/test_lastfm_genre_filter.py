from app.services.lastfm_genre_filter import clean_lastfm_genre_tags


def main():
    raw_tags = [
        "pop",
        "electropop",
        "2014",
        "dance",
        "EDM",
        "zedd",
        "Ariana Grande",
        "female vocalists",
        "electro house",
        "party",
    ]

    cleaned = clean_lastfm_genre_tags(
        raw_tags,
        artist_names=["Ariana Grande", "Zedd"],
    )

    print("RAW TAGS:")
    print(raw_tags)
    print()
    print("CLEANED TAGS:")
    print(cleaned)


if __name__ == "__main__":
    main()