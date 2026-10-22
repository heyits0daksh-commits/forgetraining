"""
backend/services/video_lookup.py — Phase 18: in-app exercise demo videos.
Phase 19 (equipment-coverage expansion): extended from 5 channels covering
~470/808 exercises to 8 channels covering ~794/808.

WHY THIS EXISTS
`data/exercises.json` has 808 exercises. Hand-typing a YouTube video id for
each one (and keeping them all pointed at the *right* creator per category)
isn't something this module does — those ids would be untraceable guesses
and a large fraction would quietly 404 or drift to the wrong video over
time. Instead this resolves a video **live**, per exercise, restricted to
one specific, hand-picked channel per category, and caches the result on
disk so it's a one-time cost per exercise rather than a YouTube API call on
every page view.

CHANNEL ASSIGNMENTS (by equipment type, see `_EQUIPMENT_CHANNEL_MAP` below
for the exact equipment-string -> channel mapping this implements):

  - Bodyweight & calisthenics apparatus (Bodyweight, Rings, Pull-up Bar,
    Parallel Bars, Suspension Trainer)  -> FitnessFAQs (Daniel Vadnal)
    channel id UC1CVzH-XVr3E-kTT6D8hhfg
  - Snatch/Clean/Jerk-family lifts (any equipment) -> Torokhtiy Weightlifting
    Library, channel id UCbgKgsiar0ycHyrcFThdDjw
  - Barbell and barbell-adjacent bar/rack/bench equipment (Barbell, EZ Curl
    Bar, Safety Squat Bar, Cambered Bar, Swiss Bar, Buffalo Bar, Trap Bar,
    Landmine, Power Rack, Squat Rack, Belt Squat, Hyperextension Bench,
    Reverse Hyper, Seal Row Bench, Bench, Sit-Up Bench, Weighted Vest)
    -> Barbell Medicine, channel id UCMcGFPjX2aQy31KYdEvT2-Q
  - Kettlebell exercises -> StrongFirst (Pavel Tsatsouline)
    channel id UCV7jQ4M9uUxHy-UF-EUkjJg
  - Dumbbell, Machine-anything (equipment contains "Machine" - Leg Press,
    Cable, Smith, Pec Deck, etc.), plus general conditioning/accessory gear
    (Resistance Band, Plyo Box, Medicine Ball, Battle Ropes, Jump Rope,
    Assault Bike, Rowing Erg, Neck Harness, Ab Wheel, Captain's Chair, GHD,
    Balance Board, Agility Ladder) -> ScottHermanFitness, channel id
    UCEtMRF1ywKMc4sf3EXYyDzw (widest general "How To" library of any channel
    checked, so it's the catch-all for accessory equipment without a more
    specific niche home)
  - Strongman implements (Sled, Yoke, Farmer Handles, Atlas Stone, Tire,
    Conan's Wheel, Fingal's Fingers, Husafell Stone, Keg, Sandbag, Log Bar,
    Axle Bar) -> Natural Strongman, channel id UCyKP1JCtO0c4t9n8xmijY7g
  - Striking-bag equipment (Boxing Heavy Bag, Speed Bag, Partner/Clinch Bag)
    -> Precision Striking (Jason Van Veldhuysen), channel id
    UC4PwJo76WpTOk-3N8dazt1A
  - Climbing Hangboard / Climbing Hold-Hangboard -> Hooper's Beta (a doctor
    of physical therapy's climbing-specific training/rehab channel), channel
    id UCsqZk5V2d44TNLRFSI5aVfg

Deliberately still unassigned: Wrestling Dummy and Tackle Bag (14 exercises
total). Both are take-down/grappling drilling equipment and no channel
checked has focused, per-move coverage of them the way the channels above
do for their categories — a forced pick would mean showing wrong-context
video for those two equipment types, which is worse than showing nothing.
`pick_channel_for_exercise` returns None for these and the route/frontend
treat that as "no demo video configured" rather than falling back to an
unrestricted, unvetted YouTube search.

Requires `settings.YOUTUBE_API_KEY` (a free YouTube Data API v3 key from
https://console.cloud.google.com/apis/credentials, "YouTube Data API v3"
enabled). Without a key configured, `get_video_for_exercise` returns None
and the route reports the feature as unconfigured rather than failing.
"""
from __future__ import annotations

import json
import re
import threading
from pathlib import Path
from typing import Optional, TypedDict
from urllib.parse import urlparse, parse_qs

import httpx

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.data.exercise_video_links import EXERCISE_VIDEO_LINKS

logger = get_logger(__name__)

# --- Channel ids (verified against youtube.com, see module docstring) ---
CHANNEL_FITNESSFAQS = "UC1CVzH-XVr3E-kTT6D8hhfg"      # Daniel Vadnal - calisthenics
CHANNEL_TOROKHTIY = "UCbgKgsiar0ycHyrcFThdDjw"        # Torokhtiy Weightlifting Library - Olympic lifts
CHANNEL_BARBELL_MEDICINE = "UCMcGFPjX2aQy31KYdEvT2-Q"  # Barbell Medicine - other barbell lifts
CHANNEL_STRONGFIRST = "UCV7jQ4M9uUxHy-UF-EUkjJg"      # StrongFirst (Pavel Tsatsouline) - kettlebell
CHANNEL_SCOTT_HERMAN = "UCEtMRF1ywKMc4sf3EXYyDzw"     # ScottHermanFitness - dumbbell, machines & general accessory gear
CHANNEL_NATURAL_STRONGMAN = "UCyKP1JCtO0c4t9n8xmijY7g"  # Natural Strongman - strongman implements
CHANNEL_PRECISION_STRIKING = "UC4PwJo76WpTOk-3N8dazt1A"  # Precision Striking (Jason Van Veldhuysen) - striking bags
CHANNEL_HOOPERS_BETA = "UCsqZk5V2d44TNLRFSI5aVfg"     # Hooper's Beta - climbing hangboard training/rehab

# Equipment values (exact match against the `equipment` field) that route to
# a channel other than the five original ones. Checked after the special
# cases (Bodyweight, Olympic lifts, Barbell, Kettlebell, Dumbbell, and any
# "Machine"-containing equipment) below in `pick_channel_for_exercise`.
_EQUIPMENT_CHANNEL_MAP: dict[str, str] = {
    # Calisthenics apparatus - same home as Bodyweight
    "Rings": CHANNEL_FITNESSFAQS,
    "Pull-up Bar": CHANNEL_FITNESSFAQS,
    "Parallel Bars": CHANNEL_FITNESSFAQS,
    "Suspension Trainer": CHANNEL_FITNESSFAQS,
    # Barbell-adjacent bars, racks & benches
    "EZ Curl Bar": CHANNEL_BARBELL_MEDICINE,
    "Safety Squat Bar": CHANNEL_BARBELL_MEDICINE,
    "Cambered Bar": CHANNEL_BARBELL_MEDICINE,
    "Swiss Bar": CHANNEL_BARBELL_MEDICINE,
    "Buffalo Bar": CHANNEL_BARBELL_MEDICINE,
    "Trap Bar": CHANNEL_BARBELL_MEDICINE,
    "Landmine": CHANNEL_BARBELL_MEDICINE,
    "Power Rack": CHANNEL_BARBELL_MEDICINE,
    "Squat Rack": CHANNEL_BARBELL_MEDICINE,
    "Belt Squat": CHANNEL_BARBELL_MEDICINE,
    "Hyperextension Bench": CHANNEL_BARBELL_MEDICINE,
    "Reverse Hyper": CHANNEL_BARBELL_MEDICINE,
    "Seal Row Bench": CHANNEL_BARBELL_MEDICINE,
    "Bench": CHANNEL_BARBELL_MEDICINE,
    "Adjustable Bench": CHANNEL_BARBELL_MEDICINE,
    "Sit-Up Bench": CHANNEL_BARBELL_MEDICINE,
    "Weighted Vest": CHANNEL_BARBELL_MEDICINE,
    # General conditioning / accessory equipment - same home as Dumbbell/Machine
    "Resistance Band": CHANNEL_SCOTT_HERMAN,
    "Plyo Box": CHANNEL_SCOTT_HERMAN,
    "Medicine Ball": CHANNEL_SCOTT_HERMAN,
    "Battle Ropes": CHANNEL_SCOTT_HERMAN,
    "Jump Rope": CHANNEL_SCOTT_HERMAN,
    "Assault Bike": CHANNEL_SCOTT_HERMAN,
    "Rowing Erg": CHANNEL_SCOTT_HERMAN,
    "Neck Harness": CHANNEL_SCOTT_HERMAN,
    "Ab Wheel": CHANNEL_SCOTT_HERMAN,
    "Captain's Chair": CHANNEL_SCOTT_HERMAN,
    "GHD": CHANNEL_SCOTT_HERMAN,
    "Balance Board": CHANNEL_SCOTT_HERMAN,
    "Agility Ladder": CHANNEL_SCOTT_HERMAN,
    # Strongman implements
    "Sled": CHANNEL_NATURAL_STRONGMAN,
    "Yoke": CHANNEL_NATURAL_STRONGMAN,
    "Farmer Handles": CHANNEL_NATURAL_STRONGMAN,
    "Atlas Stone": CHANNEL_NATURAL_STRONGMAN,
    "Tire": CHANNEL_NATURAL_STRONGMAN,
    "Conan's Wheel": CHANNEL_NATURAL_STRONGMAN,
    "Fingal's Fingers": CHANNEL_NATURAL_STRONGMAN,
    "Husafell Stone": CHANNEL_NATURAL_STRONGMAN,
    "Keg": CHANNEL_NATURAL_STRONGMAN,
    "Sandbag": CHANNEL_NATURAL_STRONGMAN,
    "Log Bar": CHANNEL_NATURAL_STRONGMAN,
    "Axle Bar": CHANNEL_NATURAL_STRONGMAN,
    # Striking bags
    "Boxing Heavy Bag": CHANNEL_PRECISION_STRIKING,
    "Speed Bag": CHANNEL_PRECISION_STRIKING,
    "Partner / Clinch Bag": CHANNEL_PRECISION_STRIKING,
    # Climbing-specific training
    "Climbing Hangboard": CHANNEL_HOOPERS_BETA,
    "Climbing Hold / Hangboard": CHANNEL_HOOPERS_BETA,
}

# Exercise *name* patterns that mean "Olympic lift family" even though the
# `equipment` field is just "Barbell" (or, for a few, Kettlebell/Dumbbell/
# Sandbag/Log/Axle variants of the same movement pattern) - snatch, clean,
# jerk, and their named pulls/deadlifts/high-pulls/squats all belong with
# the Olympic-lifting channel rather than generic Barbell Medicine content.
_OLYMPIC_LIFT_PATTERN = re.compile(r"\b(snatch|clean|jerk)\b", re.IGNORECASE)

_CACHE_LOCK = threading.Lock()


class VideoResult(TypedDict, total=False):
    video_id: str
    title: str
    channel_name: str
    embed_url: str
    watch_url: str
    # Added for statically-curated links (see EXERCISE_VIDEO_LINKS above).
    # Every result - static or live-search - now carries these two so the
    # frontend has one consistent shape to branch on instead of assuming
    # "available: true" always means an embeddable iframe.
    source_type: str    # "youtube" | "vimeo" | "direct_file" | "external"
    embeddable: bool     # False -> frontend shows a "Watch on <site>" link-out instead of an iframe


_CHANNEL_DISPLAY_NAMES = {
    CHANNEL_FITNESSFAQS: "FitnessFAQs (Daniel Vadnal)",
    CHANNEL_TOROKHTIY: "Torokhtiy Weightlifting Library",
    CHANNEL_BARBELL_MEDICINE: "Barbell Medicine",
    CHANNEL_STRONGFIRST: "StrongFirst (Pavel Tsatsouline)",
    CHANNEL_SCOTT_HERMAN: "ScottHermanFitness",
    CHANNEL_NATURAL_STRONGMAN: "Natural Strongman",
    CHANNEL_PRECISION_STRIKING: "Precision Striking (Jason Van Veldhuysen)",
    CHANNEL_HOOPERS_BETA: "Hooper's Beta",
}


def pick_channel_for_exercise(exercise: dict) -> Optional[str]:
    """Return the channel id this exercise's demo video should come from, or
    None if this exercise's equipment type has no assigned channel."""
    name = exercise.get("name", "")
    equipment = exercise.get("equipment", "")

    if equipment == "Bodyweight":
        return CHANNEL_FITNESSFAQS

    if equipment == "Barbell":
        if _OLYMPIC_LIFT_PATTERN.search(name):
            return CHANNEL_TOROKHTIY
        return CHANNEL_BARBELL_MEDICINE

    if equipment == "Kettlebell":
        return CHANNEL_STRONGFIRST

    if equipment == "Dumbbell":
        return CHANNEL_SCOTT_HERMAN

    if "Machine" in equipment:
        return CHANNEL_SCOTT_HERMAN

    return _EQUIPMENT_CHANNEL_MAP.get(equipment)


_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"}
_VIMEO_HOSTS = {"vimeo.com", "www.vimeo.com", "player.vimeo.com"}
_DIRECT_FILE_EXTENSIONS = (".mp4", ".webm", ".mov", ".m4v")


def _youtube_id_from_url(url: str, parsed) -> Optional[str]:
    host = parsed.netloc.lower()
    if host == "youtu.be":
        return parsed.path.lstrip("/").split("/")[0] or None
    if "/shorts/" in parsed.path:
        return parsed.path.split("/shorts/")[1].split("/")[0] or None
    if "/embed/" in parsed.path:
        return parsed.path.split("/embed/")[1].split("/")[0] or None
    qs = parse_qs(parsed.query)
    if "v" in qs and qs["v"]:
        return qs["v"][0]
    return None


def _vimeo_id_from_url(parsed) -> Optional[str]:
    # vimeo.com/123456789 or player.vimeo.com/video/123456789
    segments = [s for s in parsed.path.split("/") if s]
    for seg in reversed(segments):
        if seg.isdigit():
            return seg
    return None


def resolve_static_video_link(url: str, title: str) -> VideoResult:
    """Turns one hand-typed link (see EXERCISE_VIDEO_LINKS's module
    docstring for the supported shapes) into the same VideoResult shape
    the live YouTube search already returns, so the frontend and the route
    don't need to know whether a given exercise's video came from a curated
    link or a live search. Never raises - an unparseable URL just falls
    through to the generic "external, not embeddable" case rather than
    breaking the modal for that exercise.
    """
    url = url.strip()
    try:
        parsed = urlparse(url)
    except ValueError:
        parsed = None

    host = (parsed.netloc.lower() if parsed else "")

    if parsed and host in _YOUTUBE_HOSTS:
        video_id = _youtube_id_from_url(url, parsed)
        if video_id:
            return {
                "title": title,
                "channel_name": "Curated link",
                "video_id": video_id,
                "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}",
                "watch_url": f"https://www.youtube.com/watch?v={video_id}",
                "source_type": "youtube",
                "embeddable": True,
            }

    if parsed and host in _VIMEO_HOSTS:
        video_id = _vimeo_id_from_url(parsed)
        if video_id:
            return {
                "title": title,
                "channel_name": "Curated link",
                "video_id": video_id,
                "embed_url": f"https://player.vimeo.com/video/{video_id}",
                "watch_url": f"https://vimeo.com/{video_id}",
                "source_type": "vimeo",
                "embeddable": True,
            }

    if url.lower().split("?")[0].endswith(_DIRECT_FILE_EXTENSIONS):
        return {
            "title": title,
            "channel_name": "Curated link",
            "embed_url": url,
            "watch_url": url,
            "source_type": "direct_file",
            "embeddable": True,
        }

    # Anything else (Instagram/TikTok/an article page/an unrecognized
    # host) - not embeddable, frontend link-outs instead.
    return {
        "title": title,
        "channel_name": (host or "External link"),
        "embed_url": "",
        "watch_url": url,
        "source_type": "external",
        "embeddable": False,
    }


def _cache_path() -> Path:
    return settings.DATA_DIR / "video_cache.json"


def _load_cache() -> dict:
    path = _cache_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        logger.warning("video_cache.json unreadable, starting fresh")
        return {}


def _save_cache(cache: dict) -> None:
    path = _cache_path()
    try:
        path.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
    except OSError:
        logger.warning("could not persist video_cache.json")


def _search_youtube(query: str, channel_id: str, api_key: str) -> Optional[VideoResult]:
    """One live call to YouTube Data API v3 search.list, restricted to a
    single channel. Returns the top result or None (no match / API error -
    never raises, since a missing demo video shouldn't break the modal)."""
    try:
        resp = httpx.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "key": api_key,
                "channelId": channel_id,
                "q": query,
                "part": "snippet",
                "type": "video",
                "maxResults": 1,
                "order": "relevance",
            },
            timeout=6.0,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        if not items:
            return None
        item = items[0]
        video_id = item["id"]["videoId"]
        title = item["snippet"]["title"]
        return {
            "video_id": video_id,
            "title": title,
            "channel_name": _CHANNEL_DISPLAY_NAMES.get(channel_id, ""),
            "embed_url": f"https://www.youtube-nocookie.com/embed/{video_id}",
            "watch_url": f"https://www.youtube.com/watch?v={video_id}",
        }
    except (httpx.HTTPError, KeyError, ValueError) as exc:
        logger.warning(f"YouTube search failed for '{query}' on channel {channel_id}: {exc}")
        return None


def get_video_for_exercise(exercise_id: str, exercise: dict) -> Optional[VideoResult]:
    """Cached lookup: exercise id -> demo video on its assigned channel.
    Returns None if no channel is assigned to this exercise, no API key is
    configured, or no matching video was found.

    A curated link in EXERCISE_VIDEO_LINKS always wins over the live
    search below and skips the API/cache entirely - it's resolved fresh
    on every call (cheap - just URL parsing, no network) so an edit to
    that file takes effect immediately without needing to clear
    video_cache.json.
    """
    curated_url = EXERCISE_VIDEO_LINKS.get(exercise_id)
    if curated_url:
        return resolve_static_video_link(curated_url, exercise.get("name", ""))

    channel_id = pick_channel_for_exercise(exercise)
    if channel_id is None:
        return None

    if not settings.YOUTUBE_API_KEY:
        return None

    with _CACHE_LOCK:
        cache = _load_cache()
        cached = cache.get(exercise_id)
        if cached is not None:
            return cached if cached else None  # cached "no result" -> None

        result = _search_youtube(exercise["name"], channel_id, settings.YOUTUBE_API_KEY)
        if result:
            result["source_type"] = "youtube"
            result["embeddable"] = True
        cache[exercise_id] = result or {}
        _save_cache(cache)
        return result
