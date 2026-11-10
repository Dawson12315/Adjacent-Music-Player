# Lyrics

[← Back to the README](../README.md)

Adjacent shows lyrics in the web player and in the phone's full player. It
never downloads lyrics from anywhere: every word it shows comes from the
listener's own files, from the listener, or from the listener's own server
working on the listener's own audio. There is no lyrics database inside
Adjacent and no lyrics service it talks to.

## Where the words come from

In order of precedence, highest first:

1. **Corrected in Adjacent.** An admin can edit a track's lyrics in the web
   player (plain text, or timed with the "time the lines" tool). A person's
   words outrank every other source and are never overwritten by a scan.
2. **Inside the file.** The lyrics tags the tagging tools write: `USLT` and
   timed `SYLT` in MP3/WAV/AIFF, `©lyr` in M4A, `LYRICS` / `UNSYNCEDLYRICS` in
   FLAC, Ogg and Opus. LRC text inside any of them is understood as timed.
3. **A sidecar file.** `Song.lrc` or `Song.txt` beside `Song.flac`, the
   convention Plex, Jellyfin and Navidrome share. The folder watcher notices
   a new one and the nightly scan picks up a changed one.
4. **Timed on this server.** When the words are known but carry no timing,
   the server can time them against the audio.
5. **Produced on this server.** When a track has no words anywhere, the
   server can produce words and timing from the audio. These are labelled
   *generated* in the players and may contain errors; the editor fixes them.

Generated lyrics can be thrown away and redone: **Regenerate**, in the web
player's lyrics panel and the phone's lyrics view, for admins. The file's
own words are kept and only re-timed; a person's edits are never
regenerated over (reset them to the file first).

4 and 5 are off until an admin turns on **Settings → Automation → Generate
lyrics**. They run on demand (someone opens the lyrics panel on a track that
has none) and, if a run time is set, overnight for the most-played tracks
that still have none, for at most two hours a night. The work takes a
background transcode slot, so a track someone is streaming always has the
CPU first.

## What generation costs

The model runs on the CPU with 8-bit weights, on at most half the cores.
Measured on an Apple M4 Max (four threads): the `base` model transcribes
about 25 seconds of audio per second, `small` about 8. A NAS-class CPU is
roughly ten to fifteen times slower: a four-minute song takes one to two
minutes with `base`, three to five with `small`. `base` is the default;
`small` is more accurate and three times the size.

The model is downloaded once from Hugging Face on first use into
`data/models` (`base` about 300 MB, `small` about 1 GB) and kept in the data
volume. A server without internet access cannot fetch it; the Settings card
says so.

## Licences

Everything the generation path uses is under terms that allow commercial
use and redistribution at no cost. The table is here so it can be checked
again whenever a version changes.

| Component | Role | Licence |
| --- | --- | --- |
| Whisper model weights (OpenAI) | the speech model | MIT |
| faster-whisper | runs the model | MIT |
| CTranslate2 | inference engine | MIT |
| tokenizers, huggingface-hub | tokenizer, model download | Apache-2.0 |
| onnxruntime | pulled in by faster-whisper (unused voice-activity model) | MIT |
| PyAV | pulled in by faster-whisper; not used — audio is decoded by ffmpeg as a subprocess | BSD-3-Clause |
| numpy | sample buffers | BSD-3-Clause |
| ffmpeg (Debian build) | decodes the audio, as a separate process | GPL/LGPL; not linked |

Deliberately not used: Meta's MMS forced aligner (weights released for
non-commercial use only), aeneas (AGPL) and any online lyrics database.

Adjacent ships no lyrics, fetches none, and produces text only from audio
the listener already holds, for display to that listener. The licences above
govern the software; they say nothing about the lyrics themselves, which
remain their authors' work. Say "generated" where the players say it.

The same words also tell the radio something: see [Audio analysis](audio-analysis.md)
for the vocal, language and explicit flags and the words block of the map.
