# Audio analysis

[← Back to the README](../README.md)

Adjacent's radio and recommendations place every track on a map built from
genre tags, Last.fm's similar-artist graph and what gets played together.
That map knows who made a track and what people call it. It does not know
what the track sounds like, so a quiet ballad and a loud single by the same
artist used to sit on top of each other, and a station seeded from a Spanish
song could drift into English pop because the tags agreed.

Audio analysis fixes that by listening. It runs on the server, on the
listener's own files, and sends nothing anywhere.

## What is measured

**The sound profile.** Three thirty-second excerpts of each track (early,
middle, late) are decoded by ffmpeg and measured with librosa: tempo, how
hard the beat hits, loudness and how much it varies, brightness, noisiness,
width, thirteen timbre coefficients and twelve harmony bins. The raw numbers
are stored per track; on every map rebuild they are standardised over the
whole library into a unit vector, the *sound block* of the map. Tempo is
folded by octave, because beat trackers disagree by a factor of two far more
often than by anything else.

**The flags.** When the lyrics engine is installed, the same speech model
listens to one thirty-second window (two if the first was quiet) and records:

- `vocal_state`: *vocal* or *instrumental*, from how many words it heard.
  Each window is judged on its own, and only segments the model was
  reasonably sure of count (an average log-probability above −1, no
  repetition loops): on a pure tone Whisper invents a word or two per window
  at a log-probability near −2, and those must not add up into a song. Six
  words, four of them different, in one window says vocal; at most two in
  every window says instrumental; anything between stays unknown. A track
  with lyrics on file is vocal whatever a thirty-second listen says;
- `language`: the language of the vocals, kept only on a vocal track and
  only when the model was at least 50% sure;
- `explicit_state`: *explicit* or *clean*, read from the lyrics text whenever
  a track has words, from any source.

Null is a real third state: a track nobody has listened to yet is unknown,
and the radio never treats unknown as wrong. Every flag is a machine's guess
and the clients say "detected"; an admin can set any of them, and the server
then leaves that track alone.

**The words block.** Where a track has lyrics (from its tags, a sidecar, an
edit or a transcription), a weighted bag of its words is reduced to sixteen
dimensions, so songs about the same thing sit near each other whatever they
sound like. The vector cannot be turned back into words.

## How the radio uses it

A station scores candidates by the map, the sound block and the words block
at shares of 60 / 25 / 15, renormalised over the blocks a candidate actually
has, so a track that has not been measured is judged by the map alone rather
than pushed away. The recommender reads the two blocks as channels of their
own, weighted low. A station also keeps its seed's vocal state (instrumental
stays instrumental) and, unless the listener's own plays spread over
languages, its seed's language.

## When it runs, and what it costs

Analysis is on by default (**Settings → Automation → Analyse audio**) and
runs overnight at the set time, most-played tracks first, for at most two
hours a night, in a background transcode slot so a stream always has the CPU
first. New files are measured after a scan, and a station started on an
unmeasured track asks for it straight away. "Analyse now" starts on the
backlog immediately.

Measured on an Apple M4 Max: the sound profile takes about half a second per
track, the flags about a second with the `base` model. A NAS-class CPU is ten
to fifteen times slower. The stored numbers come to under ten megabytes for a
library of forty thousand tracks. librosa compiles its numeric kernels on
first use, about eighteen seconds, once per install (cached under
`data/numba_cache`).

## Licences

| Component | Role | Licence |
| --- | --- | --- |
| librosa | the measurements | ISC |
| scipy, scikit-learn, joblib, threadpoolctl | numerics librosa relies on | BSD-3-Clause |
| numba, llvmlite | compile librosa's loops | BSD-2-Clause; llvmlite also Apache-2.0 with LLVM exception |
| pooch, lazy-loader, decorator, msgpack, platformdirs | utilities pulled in by librosa | BSD-3, BSD-3, BSD-2, Apache-2.0, MIT |
| soundfile | file reading, not used (ffmpeg decodes) | BSD-3-Clause wrapper around libsndfile, LGPL-2.1-or-later |
| soxr | resampling, not used (ffmpeg resamples) | LGPL-2.1-or-later |
| Whisper model and runtime | the flags | see [lyrics](lyrics.md) |
| ffmpeg (Debian build) | decodes the audio, as a separate process | GPL/LGPL; not linked |

The two LGPL components are permitted in software that is sold; their
notices travel with the distribution and they remain separately installed,
replaceable packages. Deliberately not used: Essentia (AGPL, with
non-commercial models), MERT and similar music encoders (non-commercial
weights), any embedding model that needs PyTorch, and any online service.

The measurements are facts about a recording, not copies of it. They stay
on the server that made them.
