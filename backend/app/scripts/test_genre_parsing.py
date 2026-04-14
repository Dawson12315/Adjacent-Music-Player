from app.utils.genre_parsing import split_genre_names


def main():
    print("Hip-Hop, Rap →", split_genre_names("Hip-Hop, Rap"))
    print("EDM / Dance →", split_genre_names("EDM / Dance"))
    print("Rock & Metal →", split_genre_names("Rock & Metal"))
    print("R&B →", split_genre_names("R&B"))
    print("Pop; Rock →", split_genre_names("Pop; Rock"))
    print("Pop / R&B →", split_genre_names("Pop / R&B"))


if __name__ == "__main__":
    main()