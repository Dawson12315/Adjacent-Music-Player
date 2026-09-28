import re
from typing import Optional, List

# Names that contain a separator and are one act. Splitting these made
# "Dunn", "Wind" and "The Creator" into artists of their own and removed the
# band from the index. Matched case-insensitively, whole string.
PROTECTED_ARTIST_NAMES = {
    name.casefold()
    for name in (
        "Brooks & Dunn",
        "Earth, Wind & Fire",
        "Tyler, The Creator",
        "Simon & Garfunkel",
        "Hall & Oates",
        "Daryl Hall & John Oates",
        "Mumford & Sons",
        "Of Mice & Men",
        "She & Him",
        "Crosby, Stills & Nash",
        "Crosby, Stills, Nash & Young",
        "Emerson, Lake & Palmer",
        "Peter, Paul and Mary",
        "Peter, Paul & Mary",
        "Belle & Sebastian",
        "Belle and Sebastian",
        "Salt-N-Pepa",
        "Ike & Tina Turner",
        "Sonny & Cher",
        "Captain & Tennille",
        "Big & Rich",
        "Montgomery Gentry",
        "Florida Georgia Line",
        "Dan + Shay",
        "Zac Brown Band",
        "Sam & Dave",
        "Chas & Dave",
        "Iron & Wine",
        "Angus & Julia Stone",
        "Kool & The Gang",
        "Huey Lewis & The News",
        "Tom Petty & The Heartbreakers",
        "Bob Marley & The Wailers",
        "Nick Cave & The Bad Seeds",
        "Florence + The Machine",
        "Florence & The Machine",
        "Bruce Springsteen & The E Street Band",
        "Katrina & The Waves",
        "Prince & The Revolution",
        "Sly & The Family Stone",
        "Martha & The Vandellas",
        "Gladys Knight & The Pips",
        "Echo & The Bunnymen",
        "Derek & The Dominos",
        "Bill Haley & His Comets",
        "Elvis Costello & The Attractions",
        "Booker T. & The M.G.'s",
        "Marvin Gaye & Tammi Terrell",
        "Calvin Harris & Rag'n'Bone Man",
        "Mike & The Mechanics",
        "Toots & The Maytals",
        "Junior Senior",
    )
}

# What separates credited artists. Slashes and semicolons always do; commas
# and ampersands do unless the whole string is a protected name.
_SPLIT_PATTERN = re.compile(r"\s*;\s*|\s*/\s*|\s*&\s*|\s*,\s*")
_HARD_SPLIT_PATTERN = re.compile(r"\s*;\s*|\s*/\s*")


def split_artist_names(artist_value: Optional[str]) -> List[str]:
    if not artist_value:
        return []

    raw_value = artist_value.strip()
    if not raw_value:
        return []

    if raw_value.casefold() in PROTECTED_ARTIST_NAMES:
        return [raw_value]

    parts: List[str] = []
    # Split on the separators that never sit inside a name first, then
    # decide about commas and ampersands per piece.
    for piece in _HARD_SPLIT_PATTERN.split(raw_value):
        piece = piece.strip()
        if not piece:
            continue
        if piece.casefold() in PROTECTED_ARTIST_NAMES:
            parts.append(piece)
            continue
        parts.extend(_SPLIT_PATTERN.split(piece))

    cleaned: List[str] = []
    seen: set[str] = set()

    for part in parts:
        name = part.strip()
        if not name:
            continue

        dedupe_key = name.casefold()
        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)
        cleaned.append(name)

    return cleaned


_FEATURE_PATTERN = re.compile(
    r"[\(\[]?\s*\b(?:feat\.?|ft\.?|featuring)\s+([^\)\]]+)[\)\]]?",
    flags=re.IGNORECASE,
)


def extract_featured_artists(text: Optional[str]) -> List[str]:
    """Every name after a feat./ft./featuring, wherever it sits in the text."""
    if not text:
        return []

    cleaned: List[str] = []
    seen: set[str] = set()

    for match in _FEATURE_PATTERN.findall(text):
        for part in re.split(r"\s*&\s*|\s*,\s*|\s+and\s+", match, flags=re.IGNORECASE):
            name = part.strip()
            if not name:
                continue

            dedupe_key = name.casefold()
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            cleaned.append(name)

    return cleaned
