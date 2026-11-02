"""The themes a client may wear, named once for the server to check against.

The palettes themselves live in the clients (CSS variables on the web, a
token object on the phone); the server only keeps the listener's choice so
every device they sign in on wears the same one. Adjacent is the default and
the look the app ships with. There is deliberately no green theme and no
free colour: the list is the whole menu.
"""

DEFAULT_THEME = "adjacent"

# Year-round colours, then the eight that follow the calendar.
THEME_IDS = (
    "adjacent",
    "ultraviolet",
    "rosewood",
    "ember",
    "graphite",
    "spring",
    "summer",
    "autumn",
    "halloween",
    "winter",
    "festive",
    "newyear",
    "valentine",
)


def is_theme(value) -> bool:
    return isinstance(value, str) and value in THEME_IDS
