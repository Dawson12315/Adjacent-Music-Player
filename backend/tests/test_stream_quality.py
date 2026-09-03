"""The contract between a mobile client's quality preference and the ladder.

An HLS ladder can only carry AAC, but a client's *preference* is free to name
a format the ladder has no rung for — and older builds in the field do exactly
that. These tests pin down that such a request is substituted rather than
refused: rejecting it produced a phone that played nothing at all the moment it
left Wi-Fi.
"""

import pytest

from app.routes.tracks import (
    HLS_ACCEPTED_QUALITIES,
    HLS_QUALITY_SUBSTITUTIONS,
    HLS_QUALITY_VARIANTS,
    MOBILE_STREAM_PROFILES,
)


def test_every_advertised_rung_has_a_real_profile():
    for variant in HLS_QUALITY_VARIANTS:
        profile = MOBILE_STREAM_PROFILES.get(variant["quality"])
        assert profile is not None, variant["quality"]
        assert not profile.get("passthrough"), (
            f"{variant['quality']} is passthrough; an HLS rung is by definition "
            "a re-encode"
        )


def test_every_substitution_lands_on_something_the_ladder_accepts():
    for requested, substitute in HLS_QUALITY_SUBSTITUTIONS.items():
        assert substitute in HLS_ACCEPTED_QUALITIES, (
            f"{requested} substitutes to {substitute}, which the ladder would "
            "still reject"
        )


def test_mp3_preferences_are_substituted_not_refused():
    # The regression: a client with "MP3 320 kbps" selected got a 400 from the
    # master playlist and fell silent on cellular.
    assert HLS_QUALITY_SUBSTITUTIONS["mp3_320"] == "aac_320"
    assert HLS_QUALITY_SUBSTITUTIONS["mp3_128"] == "aac_128"


def test_retired_aac_256_is_still_accepted_by_name():
    # App builds already installed request this quality. Dropping it from the
    # advertised ladder is cosmetic; refusing it would break those installs.
    assert "aac_256" in HLS_ACCEPTED_QUALITIES
    assert "aac_256" not in {v["quality"] for v in HLS_QUALITY_VARIANTS}


def test_ladder_rungs_are_perceptually_distinct():
    """No two rungs may declare the same bandwidth.

    aac_256 and aac_320 were both advertised even though ffmpeg's native AAC
    encoder saturates near 224 kbps and returned effectively the same file for
    both — so the player could "adapt" between identical streams while the
    server paid for two transcodes and two cache entries.
    """
    bandwidths = [variant["bandwidth"] for variant in HLS_QUALITY_VARIANTS]
    assert len(bandwidths) == len(set(bandwidths))


@pytest.mark.parametrize("variant", HLS_QUALITY_VARIANTS, ids=lambda v: v["quality"])
def test_declared_bandwidth_exceeds_the_encoded_bitrate(variant):
    """BANDWIDTH is a budget, and MPEG-TS packetisation adds ~10% on top of the
    audio bitrate. Declaring the raw encoder setting made players downshift on
    links that could in fact carry the top rung."""
    encoder_bitrate = {"aac_320": 224_000, "aac_128": 130_000}[variant["quality"]]
    assert variant["bandwidth"] > encoder_bitrate


def test_frontend_origin_ignores_a_trailing_slash():
    """A browser's Origin header never carries one, and CORS compares exactly.

    `FRONTEND_ORIGIN=https://example.com/` — the form you get by copying the
    address out of the URL bar — matched nothing, so every request from the real
    site came back `400 Disallowed CORS origin` and the UI could only report it
    as "cannot connect to server".
    """
    from app.config import Settings

    # A realistic key: "x" * 40 is now refused as a placeholder, which is the
    # point of test_placeholder_secret_keys_are_refused below.
    generated = "a3f9c1e08b7d264a5f0e91c2b8d47a6e3f5c0b19d8a72e46c1f93b0d5a8e7c24"

    def origin_for(value: str) -> str:
        return Settings(
            auth_secret_key=generated, frontend_origin=value
        ).frontend_origin

    assert origin_for("https://example.com/") == "https://example.com"
    assert origin_for("https://example.com///") == "https://example.com"
    assert origin_for("  https://example.com  ") == "https://example.com"
    assert origin_for("https://example.com") == "https://example.com"


def test_placeholder_secret_keys_are_refused():
    """A 32-character placeholder used to satisfy the length rule and boot.

    `PASTE_YOUR_GENERATED_SECRET_HERE` is exactly 32 characters, so it passed
    the only check there was — leaving a server signing admin tokens with a
    string anyone reading the docs could guess.
    """
    from pydantic import ValidationError
    from app.config import Settings

    for placeholder in (
        "PASTE_YOUR_GENERATED_SECRET_HERE",
        "YOUR_GENERATED_SECRET",
        "CHANGE_ME",
        "replace-this-with-a-real-secret-value",
    ):
        with pytest.raises(ValidationError):
            Settings(auth_secret_key=placeholder)


def test_a_real_generated_secret_is_accepted():
    """`openssl rand -hex 32` output is only [0-9a-f], so the placeholder
    markers cannot produce a false positive against it."""
    from app.config import Settings

    generated = "a3f9c1e08b7d264a5f0e91c2b8d47a6e3f5c0b19d8a72e46c1f93b0d5a8e7c24"

    assert Settings(auth_secret_key=generated).auth_secret_key == generated
