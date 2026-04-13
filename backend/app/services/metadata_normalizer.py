import re
from typing import Optional


FEATURE_PATTERNS = [
    r"\s+\(feat\.[^)]+\)",
    r"\s+\(ft\.[^)]+\)",
    r"\s+\[feat\.[^\]]+\]",
    r"\s+\[ft\.[^\]]+\]",
]

EXTRA_TITLE_PATTERNS = [
    r"\s+\(instrumental\)",
    r"\s+\[instrumental\]",
    r"\s+\(a capella\)",
    r"\s+\[a capella\]",
    r"\s+\(acapella\)",
    r"\s+\[acapella\]",
    r"\s+\(live version\)",
    r"\s+\[live version\]",
]

ALBUM_SUFFIX_PATTERNS = [
    r"\s*-\s*single$",
    r"\s*-\s*ep$",
]

ARTIST_ALIASES = {
    "Dj Snake": "DJ Snake",
    "Jid": "J.I.D",
    "Givēon": "Giveon",
    "Beyonce": "Beyoncé",
    "Bigxthaplug": "BigXthaPlug",
    "Bts": "BTS",
    "Nf": "NF",
    "Sza": "SZA",
    "Xxxtentacion": "XXXTentacion",
    "PartyNextDoor": "PARTYNEXTDOOR",
    "Partynextdoor": "PARTYNEXTDOOR",
    "The Black Eyed Peas": "Black Eyed Peas",
    "The Eagles": "Eagles",
    "The Red Hot Chili Peppers": "Red Hot Chili Peppers",
    "The Bee Gees": "Bee Gees",
    "The Rolling Stones": "Rolling Stones",
    "The Chainsmokers with Tritonal": "The Chainsmokers",
    "Brooks And Dunn": "Brooks & Dunn",
    "She And Him": "She & Him",
    "Of Mice And Men": "Of Mice & Men",
    "Calvin Harris And Ragnbone Man": "Calvin Harris & Rag'n'Bone Man",
    "Lady GaGa": "Lady Gaga",
    "Lana Del Ray": "Lana Del Rey",
    "Jason DeRulo": "Jason Derulo",
    "Jason Derülo": "Jason Derulo",
    "Jason Der�lo": "Jason Derulo",
    "Ke$ha": "Kesha",
    "Bring Me The Horizon": "Bring Me the Horizon",
    "Cage The Elephant": "Cage the Elephant",
    "Kings Of Leon": "Kings of Leon",
    "Motionless In White": "Motionless in White",
    "P!Nk": "P!nk",
    "We The Kings": "We the Kings",
    "Fred AgAin..": "Fred Again..",
    "Bangtan Boys": "BTS",
    "방탄소년단": "BTS",
    "Jason Derulo And Shouse": "Jason Derulo & Shouse",
    "David Guetta And Morten": "David Guetta & MORTEN",
    "David Guetta and MORTEN": "David Guetta & MORTEN",
    "David Guetta X Morten": "David Guetta & MORTEN",
    "David Guetta x MORTEN x Prophecy": "David Guetta & MORTEN",
    "Fred Again.. And The Blessed Madonna": "Fred Again.. & The Blessed Madonna",
    "Motionless In White, Crystal Joilena": "Motionless in White, Crystal Joilena",
    "Motionless In White, Kerli": "Motionless in White, Kerli",
    "We The Kings;Anna Maria Island": "We the Kings, Anna Maria Island",
    "We The Kings;Elena Coats": "We the Kings, Elena Coats",
    "A Boogie Wit da Hoodie": "A Boogie Wit Da Hoodie",
    "A Boogie wit da Hoodie": "A Boogie Wit Da Hoodie",
    "Ac-Dc": "AC/DC",
    "Acdc": "AC/DC",
    "Ac/Dc": "AC/DC",
    "Alice In Chains": "Alice in Chains",
    "BONES & Dylan Ross": "Bones & Dylan Ross",
    "Bbno$;Yung Gravy": "bbno$ & Yung Gravy",
    "Bones, cat soup": "Bones & Cat Soup",
    "Bones, Lyson": "Bones & Lyson",
    "Calvin Harris X Rag'n'bone Man": "Calvin Harris & Rag'n'Bone Man",
    "Chance The Rapper": "Chance the Rapper",
    "DJ Snake, J Balvin": "DJ Snake & J Balvin",
    "David Guetta X Cedric Gervais": "David Guetta & Cedric Gervais",
    "David Guetta, Sia": "David Guetta & Sia",
    "David Guetta VS The Egg": "David Guetta vs. The Egg",
    "Diplo, SIDEPIECE": "Diplo & SIDEPIECE",
    "Foster The People": "Foster the People",
    "Fred again..": "Fred Again..",
    "J. Balvin": "J Balvin",
    "KiD CuDi": "Kid Cudi",
    "Kidrock": "Kid Rock",
    "MY Chemical Romance": "My Chemical Romance",
    "Meek Mills": "Meek Mill",
    "Nct Dream": "NCT Dream",
    "Onerepublic": "OneRepublic",
    "PARTYNEXTDOOR, Drake": "PARTYNEXTDOOR & Drake",
    "PARTYNEXTDOOR/Drake": "PARTYNEXTDOOR & Drake",
    "Panic! At the Disco": "Panic! At The Disco",
    "Panic! at the Disco": "Panic! At The Disco",
    "Paul Woolford, Diplo & Kareen Lomax": "Paul Woolford & Diplo & Kareen Lomax",
    "Post Malone, The Weeknd": "Post Malone & The Weeknd",
    "Reneé Rapp": "Renee Rapp",
    "Selena Gomez, Benny Blanco": "Selena Gomez & Benny Blanco",
    "Slaugher To Prevail": "Slaughter to Prevail",
    "Slaughter To Prevail": "Slaughter to Prevail",
    "System Of A Down": "System of a Down",
    "Tate Mcrae": "Tate McRae",
    "The Marías": "The Marias",
    "Tommy Richman, mynameisntjmack": "Tommy Richman & mynameisntjmack",
    "Ty Dolla Sign": "Ty Dolla $ign",
    "bbno$, Yung Gravy": "bbno$ & Yung Gravy",
    "Bbno$, Yung Gravy": "bbno$ & Yung Gravy",
}

ALBUM_ALIASES = {
    "AfterLife": "Afterlife",
    "BLOOM": "Bloom",
    "BULLY": "Bully",
    "BasketCase": "Basket Case",
    "Confessions Of A Dangerous Mind": "Confessions of a Dangerous Mind",
    "Hail To The King": "Hail to the King",
    "I HOPE YOU'RE HAPPY": "I Hope You're Happy",
    "InLovingMemory": "in loving memory",
    "Live At Billy Bob's Texas": "Live at Billy Bob's Texas",
    "NEVER ENOUGH": "Never Enough",
    "Recess": "recess",
    "SAVE ME": "Save Me",
    "TYCOON": "Tycoon",
    "To Plant A Seed": "To Plant a Seed",
    "This Ones For You": "This One's For You",
    "Tranquility Base Hotel + Casino": "Tranquility Base Hotel & Casino",
    "What I Do": "what i do",
    "CREEP": "Creep",
    "LosT": "Lost",
    "Whatever": "whatever",
    "Willow": "willow",
    "boom.": "boom",
}

def _collapse_spaces(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def normalize_artist(value: Optional[str]) -> Optional[str]:
    if not value:
        return value

    cleaned = value.strip()

    # remove bracketed featured artist expressions
    cleaned = re.sub(r"\s+\(feat\.[^)]+\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\(ft\.[^)]+\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\[feat\.[^\]]+\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+\[ft\.[^\]]+\]", "", cleaned, flags=re.IGNORECASE)

    # remove inline featured artist expressions
    cleaned = re.sub(r"\s+feat\.?\s+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+ft\.?\s+.*$", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+featuring\s+.*$", "", cleaned, flags=re.IGNORECASE)

    cleaned = cleaned.replace("_", " ")
    cleaned = cleaned.replace("&", " & ")
    cleaned = cleaned.replace(";", ", ")
    cleaned = _collapse_spaces(cleaned)

    # normalize some obvious all-upper/all-lower cases only
    if cleaned.isupper() or cleaned.islower():
        cleaned = cleaned.title()

    cleaned = ARTIST_ALIASES.get(cleaned, cleaned)

    return cleaned


def normalize_title(value: Optional[str]) -> Optional[str]:
    if not value:
        return value

    cleaned = value.strip()

    for pattern in FEATURE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    for pattern in EXTRA_TITLE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = _collapse_spaces(cleaned)
    return cleaned


def normalize_album(value: Optional[str]) -> Optional[str]:
    if not value:
        return value

    cleaned = value.strip()

    for pattern in FEATURE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    for pattern in ALBUM_SUFFIX_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = _collapse_spaces(cleaned)
    cleaned = ALBUM_ALIASES.get(cleaned, cleaned)
    return cleaned