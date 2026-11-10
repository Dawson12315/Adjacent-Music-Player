"""The words block of the map: a position for every track that has lyrics,
from what its lyrics are about.

Tags and the Last.fm graph say what people call a track; the audio profile
says what it sounds like; this says what it is about, which is the one
thing the other two cannot: two songs about a long drive home sit near each
other whether one is country and the other synth-pop. It is a tie-breaker,
weighted low (see vector_map.STATION_SHARES), never the reason a track is
chosen on its own.

Plain bag of words, weighted by TF-IDF with a log-scaled term frequency (a
chorus sung eight times is not eight times more about its subject), reduced
to WORDS_DIMENSIONS with the same randomised SVD the map uses. Stop words
are not a hand list per language but a document-frequency cut: a word in
more than MAX_DOC_FRACTION of all lyrics ("the", "love", "yeah" — and their
equivalents in any language) carries no information and is dropped. A
transcription with a few wrong words is fine here; the subject survives.

The text itself never leaves the row it came from. The vector cannot be
turned back into words.
"""

from __future__ import annotations

import logging
import math
import re
from collections import Counter

import numpy as np

logger = logging.getLogger(__name__)

WORDS_DIMENSIONS = 16
# A term must appear in at least this many tracks, and at most this share
# of them, to count.
MIN_DOC_FREQ = 2
MAX_DOC_FRACTION = 0.30
# Fewer tokens than this and the lyrics say too little to place.
MIN_TOKENS = 8
# The vocabulary is capped by document frequency, highest first.
MAX_TERMS = 20000
# Tokens: runs of letters (any script) of at least three characters.
_TOKEN = re.compile(r"[^\W\d_]{3,}", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN.findall(text or "")]


def build_word_vectors(documents: dict[int, str], dimensions: int = WORDS_DIMENSIONS) -> tuple[list[int], np.ndarray]:
    """(track_ids, unit rows) for the tracks whose words placed them. Empty
    when too few tracks have lyrics for a reduction to mean anything."""
    try:
        import scipy.sparse as sparse
    except Exception:  # noqa: BLE001
        logger.warning("The words block needs scipy; skipped")
        return [], np.zeros((0, 0), dtype=np.float32)
    from app.services.recommendations.vector_map import _normalize_rows, _randomized_svd

    tokens_by_track: dict[int, Counter] = {}
    for track_id, text in documents.items():
        tokens = tokenize(text)
        if len(tokens) < MIN_TOKENS:
            continue
        tokens_by_track[int(track_id)] = Counter(tokens)
    n_docs = len(tokens_by_track)
    if n_docs < max(4, dimensions // 2):
        return [], np.zeros((0, 0), dtype=np.float32)

    doc_freq: Counter = Counter()
    for counts in tokens_by_track.values():
        doc_freq.update(counts.keys())
    max_df = max(MIN_DOC_FREQ, int(MAX_DOC_FRACTION * n_docs))
    vocabulary = [term for term, df in doc_freq.most_common() if MIN_DOC_FREQ <= df <= max_df][:MAX_TERMS]
    if len(vocabulary) < dimensions:
        return [], np.zeros((0, 0), dtype=np.float32)
    column_of = {term: i for i, term in enumerate(vocabulary)}
    idf = np.asarray([math.log((1 + n_docs) / (1 + doc_freq[term])) + 1.0 for term in vocabulary], dtype=np.float32)

    track_ids = list(tokens_by_track.keys())
    rows, cols, vals = [], [], []
    for row, track_id in enumerate(track_ids):
        for term, count in tokens_by_track[track_id].items():
            col = column_of.get(term)
            if col is None:
                continue
            rows.append(row)
            cols.append(col)
            vals.append((1.0 + math.log(count)) * idf[col])
    matrix = sparse.csr_matrix((np.asarray(vals, dtype=np.float32), (rows, cols)), shape=(len(track_ids), len(vocabulary)))
    norms = np.sqrt(np.asarray(matrix.multiply(matrix).sum(axis=1)).ravel())
    norms[norms == 0] = 1.0
    matrix = sparse.diags(1.0 / norms).dot(matrix).tocsr().astype(np.float32)

    rank = min(dimensions, len(track_ids) - 1, len(vocabulary) - 1)
    u, s = _randomized_svd(
        lambda omega: np.asarray(matrix.dot(omega), dtype=np.float32),
        lambda q: np.asarray(matrix.T.dot(q), dtype=np.float32),
        len(track_ids),
        len(vocabulary),
        rank,
    )
    vectors = _normalize_rows((u * s).astype(np.float32))
    placed = vectors.any(axis=1)
    kept_ids = [track_id for track_id, keep in zip(track_ids, placed) if keep]
    return kept_ids, vectors[placed]
