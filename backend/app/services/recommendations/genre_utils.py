import re

from app.models.track import Track


GENRE_SYNONYMS = {
    "hip-hop": "hip hop",
    "hiphop": "hip hop",
    "hip_hop": "hip hop",
    "rap music": "rap",
    "rnb": "r&b",
    "rhythm and blues": "r&b",
    "dance pop": "dance-pop",
    "dance-pop": "dance-pop",
    "electro house": "electro house",
    "future bass": "future bass",
    "drum and bass": "drum and bass",
    "dnb": "drum and bass",
    "alt rock": "alternative rock",
    "indie rock": "indie rock",
    "pop rock": "pop rock",
    "neo soul": "neo soul",
    "new jack swing": "new jack swing",
    "quiet storm": "quiet storm",
    "americana": "americana",
    "bluegrass": "bluegrass",
    "edm": "edm",
    "electronic": "electronic",
    "electropop": "electropop",
    "synth-pop": "synthpop",
    "synthwave": "synthwave",
    "lo-fi": "lofi",
    "lo fi": "lofi",
}

FAMILY_ALIASES = {
    "hip_hop": {
        "hip hop",
        "rap",
        "trap",
        "drill",
        "grime",
        "boom bap",
        "southern hip hop",
        "east coast hip hop",
        "west coast hip hop",
        "alternative hip hop",
        "underground hip hop",
        "gangsta rap",
        "cloud rap",
        "emo rap",
        "mumble rap",
        "conscious hip hop",
        "phonk",
        "crunk",
        "hyphy",
        "g-funk",
        "horrorcore",
        "uk drill",
    },
    "dance_electronic": {
        "dance",
        "dance-pop",
        "edm",
        "electronic",
        "electronica",
        "electropop",
        "electro",
        "electro house",
        "house",
        "deep house",
        "progressive house",
        "tech house",
        "tropical house",
        "future house",
        "bass house",
        "big room",
        "future bass",
        "drum and bass",
        "jungle",
        "breakbeat",
        "dubstep",
        "brostep",
        "riddim",
        "garage",
        "uk garage",
        "2-step",
        "techno",
        "trance",
        "psytrance",
        "hardstyle",
        "hardcore techno",
        "gabber",
        "synthwave",
        "vaporwave",
        "idm",
        "glitch",
        "club",
        "bass",
        "bass music",
        "rave",
        "eurodance",
        "moombahton",
        "trip hop",
        "industrial dance",
    },
    "rnb_soul": {
        "r&b",
        "contemporary r&b",
        "alternative r&b",
        "soul",
        "neo soul",
        "quiet storm",
        "new jack swing",
        "funk",
        "motown",
        "disco",
        "boogie",
    },
    "rock_alt": {
        "rock",
        "alternative",
        "alternative rock",
        "alternrock",
        "alternatif et indé",
        "indie",
        "indie rock",
        "pop rock",
        "punk",
        "pop punk",
        "punk rock",
        "grunge",
        "post-grunge",
        "metal",
        "heavy metal",
        "death metal",
        "black metal",
        "doom metal",
        "nu metal",
        "thrash metal",
        "power metal",
        "metalcore",
        "deathcore",
        "screamo",
        "emo",
        "hardcore",
        "post-hardcore",
        "hard rock",
        "classic rock",
        "southern rock",
        "garage rock",
        "psychedelic rock",
        "progressive rock",
        "post-rock",
        "post-punk",
        "shoegaze",
        "new wave",
        "britpop",
        "industrial",
        "industrial metal",
        "rockabilly",
        "surf rock",
        "ska",
        "ska punk",
        "math rock",
        "stoner rock",
        "alternative metal",
        "gothic rock",
        "gothic metal",
        "symphonic metal",
        "folk metal",
        "grindcore",
        "sludge metal",
    },
    "pop": {
        "pop",
        "bedroom pop",
        "art pop",
        "indie pop",
        "dream pop",
        "hyperpop",
        "k-pop",
        "j-pop",
        "power pop",
        "chamber pop",
        "teen pop",
        "adult contemporary",
        "singer-songwriter",
        "synthpop",
    },
    "country_folk": {
        "country",
        "folk",
        "indie folk",
        "folk rock",
        "americana",
        "bluegrass",
        "country rock",
        "country pop",
        "texas country",
        "red dirt",
        "outlaw country",
        "alt-country",
        "honky tonk",
        "western",
        "acoustic",
        "traditional country",
        "contemporary country",
        "nashville sound",
    },
    "jazz_blues": {
        "jazz",
        "blues",
        "swing",
        "bebop",
        "smooth jazz",
        "jazz fusion",
        "big band",
        "delta blues",
        "chicago blues",
        "blues rock",
        "soul jazz",
        "vocal jazz",
        "cool jazz",
    },
    "ambient_chill": {
        "ambient",
        "ambiance",
        "chill",
        "chillout",
        "chillwave",
        "lofi",
        "downtempo",
        "new age",
        "meditation",
        "drone",
    },
    "gospel_spiritual": {
        "gospel",
        "spiritual",
        "christian",
        "christian rock",
        "worship",
        "ccm",
        "contemporary christian",
        "praise",
    },
    "latin": {
        "latin",
        "latin pop",
        "reggaeton",
        "latin trap",
        "salsa",
        "bachata",
        "merengue",
        "cumbia",
        "corridos",
        "corridos tumbados",
        "banda",
        "norteño",
        "regional mexicano",
        "mariachi",
        "bossa nova",
        "latin rock",
        "urbano",
        "dembow",
    },
    "reggae_dancehall": {
        "reggae",
        "dancehall",
        "dub",
        "roots reggae",
        "afrobeats",
        "afrobeat",
        "afropop",
        "amapiano",
        "soca",
        "calypso",
    },
    "classical_score": {
        "classical",
        "orchestral",
        "opera",
        "baroque",
        "chamber music",
        "piano",
        "soundtrack",
        "score",
        "film score",
        "video game music",
        "instrumental",
    },
    "world": {
        "world",
        "musiques du monde",
        "world music",
        "celtic",
        "flamenco",
        "bollywood",
        "traditional",
    },
}

# The curated buckets above. Long-tail genres that match nothing fall back to
# themselves for *matching* precision, but they must not count as first-class
# families when classifying a playlist as focused or multi-cluster — that is
# what made every enriched playlist look eclectic.
CANONICAL_FAMILIES = set(FAMILY_ALIASES.keys())

# Keyword fallbacks for compound tags the alias table cannot enumerate
# ("melodic dubstep", "dark trap", "progressive metal"...). Order matters:
# more specific families are checked before broader ones, and "pop" goes last
# because so many compounds contain it ("pop punk" must hit rock_alt first).
FAMILY_KEYWORD_RULES = [
    ("hip_hop", ("hip hop", "rap", "trap", "drill", "grime", "phonk", "boom bap")),
    ("latin", ("reggaeton", "latin", "corrido", "banda", "cumbia", "bachata", "salsa", "mariachi")),
    ("reggae_dancehall", ("reggae", "dancehall", "afro", "amapiano", "soca")),
    ("gospel_spiritual", ("gospel", "worship", "christian", "praise")),
    ("country_folk", ("country", "folk", "americana", "bluegrass", "honky")),
    ("jazz_blues", ("jazz", "blues", "bebop", "swing")),
    ("ambient_chill", ("ambient", "chill", "lofi", "lo-fi", "downtempo", "sleep")),
    ("classical_score", ("classical", "orchestr", "symphony", "soundtrack", "score", "opera")),
    (
        "rock_alt",
        (
            "rock", "metal", "punk", "core", "grunge", "emo", "shoegaze",
            "industrial", "indie", "alternative", "ska", "wave",
        ),
    ),
    (
        "dance_electronic",
        (
            "house", "techno", "trance", "dubstep", "electro", "edm", "dance",
            "bass", "garage", "rave", "hardstyle", "synth", "step", "dnb",
            "drum and bass", "club", "glitch", "breakbeat",
        ),
    ),
    ("rnb_soul", ("r&b", "rnb", "soul", "funk", "disco", "motown")),
    ("pop", ("pop",)),
]


def get_track_genres(track: Track) -> list[str]:
    """
    Returns all genres associated with a track.
    Prefers normalized track_genres relationship,
    falls back to raw track.genre.
    """
    if track.track_genres:
        seen = set()
        genres: list[str] = []

        for item in track.track_genres:
            if not item.genre:
                continue

            genre = item.genre.strip()
            if not genre:
                continue

            normalized = normalize_genre_name(genre)
            if normalized in seen:
                continue

            seen.add(normalized)
            genres.append(genre)

        if genres:
            return genres

    if track.genre and track.genre.strip():
        return [track.genre.strip()]

    return []


def normalize_genre_name(value: str) -> str:
    """
    Normalize genre string for consistent comparison.
    """
    normalized = value.strip().casefold()
    normalized = normalized.replace("_", " ")
    normalized = re.sub(r"\s+", " ", normalized)
    normalized = GENRE_SYNONYMS.get(normalized, normalized)
    return normalized


def map_genre_to_family(genre: str) -> str:
    """
    Map raw genre -> broader family bucket.

    Resolution order: exact alias, then keyword rules for compound tags, then
    the normalized genre itself. The self-fallback keeps matching precise for
    the long tail (two "vaporwave" tracks still align), but callers deciding
    playlist shape should only trust canonical families — see
    is_canonical_family.
    """
    normalized = normalize_genre_name(genre)

    for family, aliases in FAMILY_ALIASES.items():
        if normalized in aliases:
            return family

    for family, keywords in FAMILY_KEYWORD_RULES:
        if any(keyword in normalized for keyword in keywords):
            return family

    return normalized


def is_canonical_family(family: str) -> bool:
    return family in CANONICAL_FAMILIES


def get_track_families(track: Track) -> list[str]:
    """
    Convert track genres -> unique family buckets.
    """
    families: list[str] = []
    seen = set()

    for genre in get_track_genres(track):
        family = map_genre_to_family(genre)
        if family in seen:
            continue

        seen.add(family)
        families.append(family)

    return families


def get_track_primary_family(track: Track) -> str | None:
    """
    Best single family for a track, if available.
    """
    families = get_track_families(track)
    if not families:
        return None

    return families[0]