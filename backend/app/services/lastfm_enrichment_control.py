STOP_LASTFM_ENRICHMENT = False


def request_stop():
    global STOP_LASTFM_ENRICHMENT
    STOP_LASTFM_ENRICHMENT = True


def reset_stop():
    global STOP_LASTFM_ENRICHMENT
    STOP_LASTFM_ENRICHMENT = False


def should_stop() -> bool:
    return STOP_LASTFM_ENRICHMENT