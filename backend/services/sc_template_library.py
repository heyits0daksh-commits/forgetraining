"""
sc_template_library.py — the FORGE S&C Template Libraries: ten source
files (grappling, striking, MMA, rock climbing, rugby, special forces /
military operator, HYROX, powerlifting, natural bodybuilding, and general
strength + hypertrophy) totaling 1,730 pre-built, named strength &
conditioning templates (id, level, goal, days_per_week, duration_weeks, a
day-by-day exercise breakdown, and the equipment each requires). Loaded
from JSON at import time — see backend/data/sc_templates/*.json — the same
"one shared in-process load, not re-read per request" contract
ProgressionEngine already uses for exercises.json.

WHY THIS IS A CATALOG, NOT A SECOND `/generate-program`
routes.py's own module docstring records a real, deliberate architectural
decision: the old static "Manual" mode — verbatim printed-table endpoints
that handed back a fixed, pre-written session instead of one the live
engine reasoned over — "has been removed for good." These 1,730 templates
are exactly that kind of artifact: a coach pre-selected the exercises,
sets, reps and order for each one, so serving one back as *the* answer to
`/api/v1/generate-workout` or `/api/v1/generate-program` would silently
reintroduce the disconnected-copy pattern that removal closed off.

So this module treats the libraries as a browsable reference catalog
instead — look one up by id, filter by sport/level/goal/days-per-week —
the same "reference data the API exposes for inspection" role
conditioning_protocols.py and grappling_playbook.py already play, not a
competing prescription path. `program_builder.generate_program` surfaces a
short list of *matching template ids/names* (via `sc_template_guidance`,
same `None`-means-not-covered contract `conditioning_guidance` and
`grappling_guidance` already use) so a caller can discover relevant
templates alongside the engine-generated program.

The top match of that same shortlist is also used as a SEED (see
progression_engine.template_seed_multiplier): a matched day's exercise
names are passed to the engine as a soft ranking bias, not a substitute
exercise list. Every exercise the engine considers - seeded or not - still
goes through the exact same equipment/injury/strength/level safety gate
before it can appear in a session; a seeded name that fails that gate is
simply outscored, same as any other candidate that fails it, never
force-included and never bypassing the check. That preserves the
distinction from the old removed-for-good static "Manual" mode
(routes.py's own module docstring) - a template still never becomes *the*
answer to `/api/v1/generate-workout` or `/api/v1/generate-program`
unmediated by the live engine's own judgment of what's safe for this
specific athlete right now.

HOW THIS RELATES TO grappling_playbook.py
grappling_playbook.py is the Iowa State playbook's per-level *loading
grid* (sets/reps/%1RM/rest by quality, a 4-week wave, an Olympic-lift
gate) — numbers and rules the engine or a coach can apply to any exercise
selection. The grappling library loaded here is a different, complementary
source: 150 already-assembled named templates (specific exercises already
chosen, in order) for Wrestling/Judo/BJJ/Sanda plus a sport-agnostic
grappling pool. The two don't share an id space or a data shape and
aren't merged — a caller wanting the loading grid still calls
grappling_playbook.py; a caller wanting a ready-made session to browse
calls this module.

ID NAMESPACING
The grappling and striking source files each independently number their
templates "SC-001", "SC-002", ... — colliding if read as one flat id
space. Every template is addressed here by a `global_id` of
`"{library}:{id}"` (e.g. "grappling:SC-001", "striking:SC-001",
"mma:MMA-SC-001") so a lookup is always unambiguous; the template's own
original `id` field is preserved unchanged inside the returned object.

SPORT COVERAGE PER LIBRARY (read from the data, not hand-typed — see
LIBRARY_SPORTS/GENERIC_SPORT_LABEL below): "Sanda" is deliberately the one
sport with templates in *both* the grappling and striking libraries (its
clinch-and-throw exchanges sit across both), matching the real overlap
sport_profiles.py already encodes for Sanda's own quality profile — not a
data error to be de-duplicated away.

THE SEVEN NON-COMBAT LIBRARIES
Rock climbing, rugby, special forces / military operator, HYROX,
powerlifting, natural bodybuilding, and general strength + hypertrophy
each ship as a single-sport source file — every template in the file
carries the same `sport` string (e.g. every HYROX template has
sport="HYROX"), so none of the seven has a sport-agnostic generic pool of
its own; they follow the same `GENERIC_SPORT_LABEL: None` contract the
MMA library already uses, not the grappling/striking generic-pool
pattern.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.core.cache import cache_forever
from backend.core.config import settings

# Shared by progression_engine.template_seed_multiplier (matching a
# candidate exercise's own name) and program_builder.generate_program
# (resolving a seed day's exercises back to the database to score which
# split day it fits best) - one normalizer so both sides of the match
# agree on what "the same exercise name" means. Deliberately NOT a fuzzy/
# substring match: this collapses spelling/punctuation/word-order noise
# between the two independently-authored sources (hyphens, "DB"/"KB"/"BB"
# abbreviations, parenthetical qualifiers like "(Rack)" or "(Dip Belt)",
# token order), but two genuinely different exercises still normalize to
# different bags - "Barbell Row" and "Pendlay Row" never collide.
_ABBREVIATIONS = {"db": "dumbbell", "kb": "kettlebell", "bb": "barbell", "med": "medicine"}


def normalize_exercise_name(name: str) -> str:
    """Canonical, order-independent form of an exercise name for matching
    across the FORGE S&C Template Libraries and exercises.json - lowercase,
    parentheticals dropped, punctuation collapsed to spaces, common
    equipment abbreviations expanded, tokens sorted. Two names that mean
    the same lift (\"Trap-Bar Deadlift\" / \"Trap Bar Deadlift\", \"Single-Arm
    DB Row\" / \"Single-Arm Dumbbell Row (light)\") normalize to the same
    string; names for different lifts don't."""
    n = (name or "").lower()
    n = re.sub(r"\([^)]*\)", " ", n)
    n = re.sub(r"[^a-z0-9]+", " ", n)
    tokens = sorted(_ABBREVIATIONS.get(tok, tok) for tok in n.split())
    return " ".join(tokens)


# Extra words a template author's name can carry that exercises.json's own
# name doesn't (an equipment call-out like "Front Squat (Rack)") or
# vice-versa (exercises.json's own equipment prefix, "Barbell Front
# Squat", that a template just calls "Front Squat") - resolvable by
# fuzzy_resolve_exercise_name below only when the *entire* difference
# between the two names is made up of words from this set. A difference
# that includes a real movement/technique word ("Pause Front Squat" vs
# "Front Squat") is never bridged this way - see that function's docstring.
#
# Split into two tiers because they carry different risk:
#   _SETUP_QUALIFIER_WORDS describe how a tool is rigged (a rack, a dip
#   belt, a weighted vest) without naming a *different* tool, so they're
#   safe to add or drop on either side of a match.
#   _BASE_TOOL_WORDS name the tool itself (barbell vs dumbbell vs cable vs
#   machine vs EZ bar...). Two names differing by the SAME direction (one
#   side names a tool the other leaves implicit - "Front Squat" -> "Barbell
#   Front Squat") are still safe to bridge. Two names each naming a
#   DIFFERENT base tool ("DB Lateral Raise" vs "Cable Lateral Raise",
#   "Barbell Curl" vs "EZ Bar Curl") are NOT the same exercise - that's an
#   equipment substitution the equipment/injury gate needs to reason about
#   itself, not something the name matcher should silently paper over.
_SETUP_QUALIFIER_WORDS = {"rack", "weighted", "assisted", "resistance"}
_BASE_TOOL_WORDS = {
    "barbell", "dumbbell", "kettlebell", "machine", "cable", "band", "banded",
    "bodyweight", "smith", "trap", "safety", "buffalo", "cambered", "swiss",
    "ez", "bar", "sandbag", "plate", "sled", "landmine", "suspension", "trx",
    "ring",
}
# "belt" and "vest" are deliberately NOT in either set above: a dip belt
# and a weighted vest are two different physical props for adding load,
# not two names for the same setup, and neither is safe to add as an
# unstated default the way "barbell" is for an unqualified "Front Squat"
# (e.g. a plain "Box Jump" must NOT resolve to "Weighted Vest Box Jump" -
# that would invent an equipment requirement, "Plyo Box", the template
# never asked for - "Explosive Box Jump" is the real match there, and it
# differs by a real word, "explosive", that this matcher correctly leaves
# to the caller rather than guessing past).
_EQUIPMENT_WORDS = _SETUP_QUALIFIER_WORDS | _BASE_TOOL_WORDS

# A small, hand-checked list of exact-wording synonyms the token-diff
# algorithm below can't safely bridge on its own - either because both
# names carry their OWN base-tool word ("Back Squat (Rack)" vs "Barbell
# Back Squat": neither is a subset of the other, and "rack"/"barbell" are
# different tool concepts so the base-tool-conflict guard correctly
# refuses to bridge them), or because the plain, unqualified colloquial
# name ("Bench Press", "Reverse Hyper") needs pointing at exercises.json's
# specific default variant. Checked one at a time against exercises.json
# by hand - not generated - so each line is a real, unambiguous same-lift
# synonym, never a same-category guess.
_NAME_ALIASES: Dict[str, str] = {
    "back squat": "Barbell Back Squat",
    "bench press": "Flat Bench Press",
    "barbell bench press": "Flat Bench Press",
    "hyper reverse": "Reverse Hyperextension",
    "barbell curl": "Standing Barbell Curl",
    "curl dumbbell": "Standing Dumbbell Bicep Curl",
    "barbell row": "Barbell Bent-Over Row",
    "cable row seated": "Cable Row",
    "kettlebell swing": "Russian Kettlebell Swing",
    "leg rdl single": "Single-Leg Dumbbell RDL",
    "carry farmer s": "Dumbbell Farmer's Carry",
    "cable delt fly rear": "Reverse Pec Deck (Rear Delt Fly)",
    "cable woodchop": "Cable Woodchopper",
    "cable crossover": "Cable Chest Fly",
    "calf leg press raise": "Calf Press on Leg Press Machine",
    "ball medicine rotational slam": "Medicine Ball Rotational Throw",
    "barbell incline press": "Incline Bench Press",
    "alternating curl dumbbell": "Standing Dumbbell Bicep Curl",
    "cable curl": "Cable Bicep Curl",
}

# Two normalized keys above ("face pull", "pallof press") are ambiguous on
# their own - exercises.json has more than one real variant, and which one
# a template means depends on wording that normalize_exercise_name strips
# out entirely (parenthetical/slash content). Checked against the RAW name
# text here, before it's thrown away, rather than guessing one default for
# every spelling the way the rest of _NAME_ALIASES does.
_DISAMBIGUATED_ALIASES: Dict[str, List[Tuple[str, str]]] = {
    "face pull": [("band", "Band Face Pull")],  # default (no "band" hint): Cable Face Pull
    "pallof press": [("landmine", "Landmine Pallof Press")],  # default: Cable Pallof Press
}
_DISAMBIGUATED_DEFAULTS: Dict[str, str] = {
    "face pull": "Cable Face Pull",
    "pallof press": "Cable Pallof Press",
}


def _resolve_named_alias(name: str, norm: str) -> Optional[str]:
    if norm in _DISAMBIGUATED_ALIASES:
        lname = (name or "").lower()
        for hint, target in _DISAMBIGUATED_ALIASES[norm]:
            if hint in lname:
                return target
        return _DISAMBIGUATED_DEFAULTS[norm]
    return _NAME_ALIASES.get(norm)


def fuzzy_resolve_exercise_name(name: str, exercises_by_id: Dict[str, Dict]) -> Optional[Dict]:
    """Fallback for when `normalize_exercise_name(name)` has no exact match
    in exercises.json - a FORGE S&C Template author's exact wording
    ("Front Squat (Rack)", "Chest-Supported DB Row", "Weighted Hanging Knee
    Raise (Dip Belt)") often differs from the database's own name for the
    same lift only by an equipment call-out on one side or the other
    ("Barbell Front Squat", "Chest Supported Row", "Hanging Knee Raise").
    Without this, that name never resolves to real exercise data at all,
    so it can't be equipment/injury-checked or substituted - it just gets
    passed through unchanged and flagged Unverified, even when the
    athlete's actual equipment would call for a substitution (e.g. a
    "Seal Row" swapped for a Pendlay/bent-over row when no bench is
    available for the seal setup).

    Two safe paths, tried in order:
      1. `_NAME_ALIASES` - a short hand-checked list of exact synonyms
         (see its own comment).
      2. Token-diff matching: one name's token set must be a strict subset
         of the other's, AND every token in the difference must be
         equipment vocabulary (_EQUIPMENT_WORDS), AND the difference may
         name at most one _BASE_TOOL_WORDS concept. That last guard is
         what keeps this from ever bridging an actual equipment swap -
         "DB Lateral Raise" (subset-adjacent to "Cable Lateral Raise" by
         token count) must NOT resolve, because the diff names two
         different tools (dumbbell, cable), not one tool named on one
         side and left implicit on the other. "Front Squat" -> "Barbell
         Front Squat" (diff: {barbell}, only one tool named) still
         resolves fine. A difference that includes a real movement/
         technique word ("Pause Front Squat" vs "Front Squat") is never
         bridged either way. If more than one exercise ties for the
         smallest such difference, the pick is genuinely ambiguous and
         this returns None rather than guessing.
    """
    norm = normalize_exercise_name(name)
    alias = _resolve_named_alias(name, norm)
    if alias:
        for ex in exercises_by_id.values():
            if ex.get("name") == alias:
                return ex

    query_tokens = set(norm.split())
    if not query_tokens:
        return None

    # normalize_exercise_name drops parenthetical content entirely (by
    # design, for the display-form key used elsewhere), which is fine when
    # the parenthetical is a setup qualifier ("(Rack)") but dangerous when
    # it names a competing tool ("Preacher Curl (Machine)") - the base-tool
    # word would be silently discarded and the query would land on
    # whichever OTHER tool's exercise happens to tie for smallest diff
    # ("Dumbbell Preacher Curl"), which is exactly the equipment-swap this
    # function must never guess across. Recover parenthetical base-tool
    # words here, for this diff check only, so a stated-but-parenthesized
    # tool can't be silently overridden by a different one.
    paren_text = " ".join(re.findall(r"\(([^)]*)\)", name or ""))
    paren_tokens = {
        _ABBREVIATIONS.get(tok, tok)
        for tok in re.sub(r"[^a-zA-Z0-9]+", " ", paren_text.lower()).split()
    }
    query_tokens = query_tokens | (paren_tokens & _BASE_TOOL_WORDS)

    # Recovering a parenthetical base-tool word (above) can make the query
    # land on an exact token-set match that the display-form exact-match
    # path elsewhere didn't catch ("Hammer Curl (DB)" recovers to exactly
    # "Dumbbell Hammer Curl"'s token set). Return that directly if it's
    # the only such candidate, rather than falling through to the diff
    # logic below (which deliberately skips zero-diff pairs).
    exact_recovered = [
        ex for ex in exercises_by_id.values()
        if set(normalize_exercise_name(ex.get("name", "")).split()) == query_tokens
    ]
    if len(exact_recovered) == 1:
        return exact_recovered[0]

    best_diff = None
    ties: List[Dict] = []
    for ex in exercises_by_id.values():
        db_tokens = set(normalize_exercise_name(ex.get("name", "")).split())
        if not db_tokens or db_tokens == query_tokens:
            continue
        if not (query_tokens <= db_tokens or db_tokens <= query_tokens):
            continue
        diff = query_tokens ^ db_tokens
        if not diff or not diff <= _EQUIPMENT_WORDS:
            continue
        if len(diff & _BASE_TOOL_WORDS) > 1:
            continue
        if best_diff is None or len(diff) < best_diff:
            best_diff = len(diff)
            ties = [ex]
        elif len(diff) == best_diff:
            ties.append(ex)

    if len(ties) == 1:
        return ties[0]
    return None

# library key -> (source filename, display title filled in from the file's own "meta.title")
_SOURCE_FILES: Dict[str, str] = {
    "grappling": "forge_grappling_sc_templates.json",
    "striking": "forge_striking_sc_templates.json",
    "mma": "forge_mma_sc_templates.json",
    "climbing": "forge_climbing_sc_templates.json",
    "rugby": "forge_rugby_sc_templates.json",
    "special_forces": "forge_special_forces_sc_templates.json",
    "hyrox": "forge_hyrox_templates.json",
    "powerlifting": "forge_powerlifting_templates.json",
    "natural_bodybuilding": "forge_natural_bodybuilding_templates.json",
    "strength_hypertrophy": "forge_strength_hypertrophy_fullgym_templates.json",
}

# Every library's generic, not-sport-specific template pool, keyed by the
# exact `sport` string those templates carry in the source data — matched
# in addition to a sport's own specific templates, never instead of them.
# The MMA library has no generic pool (all 150 of its templates already
# carry sport="MMA"), and neither do any of the seven single-sport
# libraries added alongside it (see this module's docstring).
GENERIC_SPORT_LABEL: Dict[str, Optional[str]] = {
    "grappling": "General / Cross-Sport (Grappling)",
    "striking": "General / Cross-Sport",
    "mma": None,
    "climbing": None,
    "rugby": None,
    "special_forces": None,
    "hyrox": None,
    "powerlifting": None,
    "natural_bodybuilding": None,
    "strength_hypertrophy": None,
}


# Wizard-facing sport names (ProgramRequest.sport / ProgressionEngine.all_sports
# — e.g. "Powerlifting", "Special Forces", "Look Jacked") sometimes differ from
# the `sport` string a library's own templates carry (e.g. "Powerlifting
# (Squat / Bench / Deadlift)", "Special Forces / Military Operator", "General
# Physique / Natural Bodybuilding"). Every other library's templates already
# carry the exact wizard sport string (Rugby, MMA, Rock Climbing, HYROX, Judo,
# BJJ, Wrestling, Sanda, Boxing, Muay Thai, Kickboxing), so this map only
# needs the four exceptions. Used by resolve_wizard_sport() below so a caller
# can filter/browse by the sport name the wizard actually sends, instead of
# needing to know each library's own internal sport string.
WIZARD_SPORT_ALIASES: Dict[str, str] = {
    "Powerlifting": "Powerlifting (Squat / Bench / Deadlift)",
    "Special Forces": "Special Forces / Military Operator",
    "Look Jacked": "General Physique / Natural Bodybuilding",
    "Strength + Hypertrophy": "General / Off-Season-GPP for Combat Athletes",
}

# Same idea as WIZARD_SPORT_ALIASES, but for `level`: every library uses
# the wizard's own five experience_level strings (Beginner/Novice/
# Intermediate/Advanced/Elite) as-is, EXCEPT special_forces, whose five
# levels are its own domain vocabulary (e.g. "Selection Candidate",
# "Elite / Tier 1") in the exact same rank order - so a level filter needs
# translating only for that one library, keyed by wizard level name.
SPECIAL_FORCES_LEVEL_ALIASES: Dict[str, str] = {
    "Beginner": "Selection Candidate",
    "Novice": "Novice Operator",
    "Intermediate": "Intermediate Operator",
    "Advanced": "Advanced Operator",
    "Elite": "Elite / Tier 1",
}


def resolve_wizard_level(sport: Optional[str], level: Optional[str]) -> Optional[str]:
    """Maps a wizard-facing experience_level onto the level string `sport`'s
    own library actually uses - a no-op for every sport except Special
    Forces (see SPECIAL_FORCES_LEVEL_ALIASES)."""
    if level is None:
        return None
    if sport == "Special Forces":
        return SPECIAL_FORCES_LEVEL_ALIASES.get(level, level)
    return level


def resolve_wizard_sport(sport: Optional[str]) -> Optional[str]:
    """Maps a wizard-facing sport name onto the sport string its SC
    template library actually uses, via WIZARD_SPORT_ALIASES; sports not
    in that map (Rugby, MMA, Rock Climbing, HYROX, Judo, BJJ, Wrestling,
    Sanda, Boxing, Muay Thai, Kickboxing, or anything with no library
    coverage at all) pass through unchanged."""
    if sport is None:
        return None
    return WIZARD_SPORT_ALIASES.get(sport, sport)


# Extra sport-specific question(s) the wizard should ask beyond the shared
# goal/experience/schedule/equipment/injury set, keyed by the *wizard's* own
# sport name (not the library's internal sport string - see
# WIZARD_SPORT_ALIASES). Each entry's `options` is read live from that
# library's own meta block (never hand-duplicated) so it can't drift out of
# sync with the JSON source files. `field` is the key the option is filtered
# on via list_templates(); `tag_category` (when present) is the template
# `category` value whose bracketed "[Tag]" in the name IS this field's value
# - see _enrich_tag() below. Sports absent from this dict (Judo, BJJ,
# Wrestling, Sanda, Boxing, Muay Thai, Kickboxing, and anything with no SC
# template coverage) have no extra question: for the combat/grappling sports
# the discipline choice itself already IS the dimension (a dedicated
# per-sport pool in the grappling/striking libraries), so asking again would
# just repeat the sport picker.
def _dimension_defs() -> Dict[str, List[Dict]]:
    grappling_meta = LIBRARY.library_meta["grappling"]
    return {
        "Rugby": [
            {
                "field": "emphasis",
                "label": "Positional Emphasis",
                "options": LIBRARY.library_meta["rugby"].get("positional_emphases", []),
                "tag_category": "S&C — Positional Emphasis",
            },
            {
                "field": "position",
                "label": "Detailed Position (optional)",
                "options": LIBRARY.library_meta["rugby"].get("detailed_positions", []),
                "tag_category": "S&C — Positional (Detailed)",
                "optional": True,
            },
        ],
        "MMA": [
            {
                "field": "emphasis",
                "label": "Fight Style Emphasis",
                "options": LIBRARY.library_meta["mma"].get("fight_style_emphases", []),
                "tag_category": "S&C — Fight-Style Emphasis",
            },
        ],
        "Rock Climbing": [
            {
                "field": "emphasis",
                "label": "Discipline Emphasis",
                "options": LIBRARY.library_meta["climbing"].get("discipline_emphases", []),
                "tag_category": "S&C — Discipline Emphasis",
            },
        ],
        "Powerlifting": [
            {
                "field": "periodization_style",
                "label": "Periodization Style",
                "options": LIBRARY.library_meta["powerlifting"].get("periodization_styles", []),
            },
        ],
        "Look Jacked": [
            {
                "field": "split",
                "label": "Split",
                "options": LIBRARY.library_meta["natural_bodybuilding"].get("splits", []),
            },
        ],
        "Strength + Hypertrophy": [
            {
                "field": "bias",
                "label": "Training Bias",
                "options": LIBRARY.library_meta["strength_hypertrophy"].get("biases", []),
            },
        ],
        "Special Forces": [
            {
                "field": "role_emphasis",
                "label": "Role Emphasis",
                "options": LIBRARY.library_meta["special_forces"].get("role_emphases", []),
            },
        ],
        "HYROX": [
            {
                "field": "race_category",
                "label": "Race Category",
                "options": LIBRARY.library_meta["hyrox"].get("race_categories", []),
            },
        ],
    }


_TAG_PATTERN = re.compile(r"\[([^\]]+)\]")


def _enrich_tag(tpl: Dict) -> Optional[str]:
    """Pulls a template's own bracketed "[Tag]" out of its name, e.g.
    "Rugby [Forwards-Dominant]: Max Strength..." -> "Forwards-Dominant".
    None if the name has no bracket (true of every library except rugby's
    positional templates, MMA's fight-style templates, and climbing's
    discipline templates - the only three libraries that encode their
    extra dimension in the name rather than a dedicated field)."""
    m = _TAG_PATTERN.search(tpl.get("name", ""))
    return m.group(1) if m else None


class _TemplateLibraryStore:
    """Loads all ten source files once and indexes them for lookup.
    Instantiated as a single module-level singleton (LIBRARY, below) —
    same one-load-at-import-time contract as ProgressionEngine for
    exercises.json, just without the DAG-building step this data doesn't
    need."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or settings.SC_TEMPLATES_DIR
        self.library_meta: Dict[str, Dict] = {}
        self.templates_by_global_id: Dict[str, Dict] = {}
        self.templates_by_library: Dict[str, List[Dict]] = {}
        self._load_all()

    def _load_all(self):
        for library, filename in _SOURCE_FILES.items():
            path = self.base_dir / filename
            if not path.exists():
                # Same "fail loudly at startup, not silently at request
                # time" posture ProgressionEngine takes for a missing
                # exercises.json — a missing template library is a broken
                # deploy, not a normal empty-catalog state.
                raise FileNotFoundError(f"SC template library file '{path}' not found.")
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)

            meta = raw.get("meta", {})
            self.library_meta[library] = meta

            templates = []
            for tpl in raw.get("templates", []):
                global_id = f"{library}:{tpl['id']}"
                enriched = {**tpl, "library": library, "global_id": global_id}
                enriched["tag"] = _enrich_tag(enriched)
                self.templates_by_global_id[global_id] = enriched
                templates.append(enriched)
            self.templates_by_library[library] = templates

    def sports_in_library(self, library: str) -> List[str]:
        """Every distinct `sport` value actually present in this
        library's templates, generic pool included, sorted for a stable
        API response."""
        return sorted({t["sport"] for t in self.templates_by_library.get(library, [])})


# Single shared instance, built once at import time — import LIBRARY (or
# the module-level functions below, which all read from it) rather than
# constructing _TemplateLibraryStore yourself.
LIBRARY = _TemplateLibraryStore()

# {sport_name: [library_keys_that_carry_specific_templates_for_it]},
# derived from the loaded data rather than hand-typed so it can never drift
# out of sync with what the JSON files actually contain. A sport not in
# this dict has no templates in any library (e.g. "Rugby", "HYROX").
LIBRARY_SPORTS: Dict[str, List[str]] = {}
for _lib, _templates in LIBRARY.templates_by_library.items():
    _generic = GENERIC_SPORT_LABEL[_lib]
    for _t in _templates:
        _sport = _t["sport"]
        if _sport == _generic:
            continue
        LIBRARY_SPORTS.setdefault(_sport, [])
        if _lib not in LIBRARY_SPORTS[_sport]:
            LIBRARY_SPORTS[_sport].append(_lib)


def _summarize(tpl: Dict) -> Dict:
    """The list-view shape: enough to identify and pick a template
    without shipping its full day-by-day exercise breakdown over the
    wire for every row of a filtered browse."""
    return {
        "global_id": tpl["global_id"],
        "id": tpl["id"],
        "library": tpl["library"],
        "name": tpl["name"],
        "sport": tpl["sport"],
        "level": tpl["level"],
        "goal": tpl["goal"],
        "category": tpl.get("category"),
        "days_per_week": tpl.get("days_per_week"),
        "duration_weeks": tpl.get("duration_weeks"),
        # The template's own extra-dimension value, wherever it lives for
        # this library - a bracketed name tag (rugby/MMA/climbing) or one
        # of the structured fields the other five libraries carry
        # (periodization_style/split/bias/race_category/role_emphasis).
        # None for libraries with no such dimension (grappling, striking,
        # generic pools) - the sport choice alone already covers those.
        "emphasis": (
            tpl.get("tag")
            or tpl.get("periodization_style")
            or tpl.get("split")
            or tpl.get("bias")
            or tpl.get("race_category")
            or tpl.get("role_emphasis")
        ),
    }


def get_template(global_id: str) -> Optional[Dict]:
    """The full template (every day, every exercise) for one
    `library:id` global id — see this module's docstring for the
    namespacing rule. None if the id doesn't exist in any library."""
    return LIBRARY.templates_by_global_id.get(global_id)


def sport_question(sport: Optional[str]) -> List[Dict]:
    """The extra sport-specific question(s) (beyond goal/experience/
    schedule/equipment/injuries) the wizard should ask for this *wizard*
    sport name before browsing/building an SC template - e.g. Rugby gets
    Positional Emphasis (+ optional Detailed Position), MMA gets
    Fight-Style Emphasis, Powerlifting gets Periodization Style. Each item
    is `{field, label, options, optional?}` - `field` is what
    list_templates()'s own `emphasis`/`position` filters key on. Returns
    [] for any sport with no extra dimension (including sports with no SC
    template coverage at all, and Judo/BJJ/Wrestling/Sanda/Boxing/Muay
    Thai/Kickboxing, whose dimension IS the sport choice itself)."""
    return _dimension_defs().get(sport or "", [])


def all_sport_questions() -> Dict[str, List[Dict]]:
    """`sport_question()` for every sport that has an extra dimension,
    keyed by wizard sport name - one call for the wizard to cache at
    startup instead of one round trip per sport."""
    return _dimension_defs()


def list_templates(
    sport: Optional[str] = None,
    level: Optional[str] = None,
    goal: Optional[str] = None,
    days_per_week: Optional[int] = None,
    library: Optional[str] = None,
    include_generic: bool = True,
    limit: Optional[int] = None,
    emphasis: Optional[str] = None,
    position: Optional[str] = None,
) -> List[Dict]:
    """Filtered, summarized template list — every filter is optional and
    combines with AND. `sport` matches a template's own specific sport
    value; pass `include_generic=True` (the default) to also include each
    matched library's sport-agnostic pool (e.g. "General / Cross-Sport")
    alongside sport-specific hits, or False to return only templates
    naming that exact sport. `library` narrows to one of "grappling",
    "striking", "mma", "climbing", "rugby", "special_forces", "hyrox",
    "powerlifting", "natural_bodybuilding", or "strength_hypertrophy"
    regardless of sport. Unmatched filter values yield
    an empty list, not an error — this is browsable reference data, same
    "invalid filters are silently narrowed away" contract
    grappling_playbook_reference already uses.
    """
    _original_sport = sport  # level aliasing (Special Forces) keys off the wizard's own sport name, not the library's internal one
    sport = resolve_wizard_sport(sport)
    level = resolve_wizard_level(_original_sport, level)

    if library is not None:
        candidate_libraries = [library] if library in LIBRARY.templates_by_library else []
    elif sport is not None:
        candidate_libraries = LIBRARY_SPORTS.get(sport, [])
    else:
        candidate_libraries = list(LIBRARY.templates_by_library.keys())

    # position filters against rugby's "S&C — Positional (Detailed)"
    # templates specifically, keeping it distinct from `emphasis` (rugby's
    # "S&C — Positional Emphasis" templates) even though both live in the
    # same tag-in-the-name field - see sport_question()'s tag_category.
    position_category = None
    if position is not None:
        for dim in _dimension_defs().get(sport or "", []):
            if dim["field"] == "position":
                position_category = dim.get("tag_category")
                break

    results = []
    for lib in candidate_libraries:
        generic_label = GENERIC_SPORT_LABEL[lib]
        for tpl in LIBRARY.templates_by_library[lib]:
            if sport is not None:
                is_generic_hit = include_generic and generic_label is not None and tpl["sport"] == generic_label
                if tpl["sport"] != sport and not is_generic_hit:
                    continue
            if level is not None and tpl["level"] != level:
                continue
            if goal is not None and tpl["goal"] != goal:
                continue
            if days_per_week is not None and tpl.get("days_per_week") != days_per_week:
                continue
            if emphasis is not None:
                tpl_emphasis = (
                    tpl.get("periodization_style") or tpl.get("split")
                    or tpl.get("bias") or tpl.get("race_category")
                    or tpl.get("role_emphasis")
                    or (tpl.get("tag") if tpl.get("category") != position_category else None)
                )
                if tpl_emphasis != emphasis:
                    continue
            if position is not None:
                if tpl.get("category") != position_category or tpl.get("tag") != position:
                    continue
            results.append(_summarize(tpl))

    if limit is not None:
        results = results[:limit]
    return results


@cache_forever
def sports_covered() -> List[str]:
    """Every sport with at least one template in any library — the
    `LIBRARY_SPORTS` keys, sorted. Cached forever like the rest of this
    module's derived tables: fixed for the process lifetime, same as
    engine.all_sports."""
    return sorted(LIBRARY_SPORTS.keys())


def library_summary(library: Optional[str] = None) -> Dict:
    """Each library's own `meta` block (title, levels, global_rules,
    total_templates, etc. — whatever that source file's meta carries) plus
    the sports actually present in it. Pass `library` to narrow to one of
    "grappling"/"striking"/"mma"/"climbing"/"rugby"/"special_forces"/
    "hyrox"/"powerlifting"/"natural_bodybuilding"/"strength_hypertrophy";
    omit for all ten keyed by library."""
    def _one(lib: str) -> Dict:
        return {
            "library": lib,
            "meta": LIBRARY.library_meta[lib],
            "sports": LIBRARY.sports_in_library(lib),
            "template_count": len(LIBRARY.templates_by_library[lib]),
        }

    if library is not None:
        if library not in LIBRARY.templates_by_library:
            return {}
        return _one(library)
    return {lib: _one(lib) for lib in LIBRARY.templates_by_library}


def templates_for_program(
    sport: Optional[str],
    level: Optional[str],
    days_per_week: Optional[int] = None,
    limit: int = 5,
) -> List[Dict]:
    """The shortlist `program_builder.generate_program` surfaces as
    `sc_template_guidance` — sport- and level-matched templates first
    (also matched on `days_per_week` when given), topped up from the same
    sport/level with any `days_per_week` if that narrower match doesn't
    fill `limit`, so a real schedule mismatch still surfaces relevant
    templates instead of an empty list. Returns [] (not None) when the
    sport has no library coverage at all — callers wanting the
    `None`-means-not-covered contract should check `sport in
    LIBRARY_SPORTS` themselves, same pattern `grappling_guidance`'s own
    call site uses against GRAPPLING_SPORTS.
    """
    original_sport = sport  # kept unresolved for list_templates' own level aliasing (Special Forces) - see resolve_wizard_level
    sport = resolve_wizard_sport(sport)
    if sport not in LIBRARY_SPORTS:
        return []

    exact = list_templates(sport=original_sport, level=level, days_per_week=days_per_week, limit=limit)
    if len(exact) >= limit or days_per_week is None:
        return exact

    seen = {t["global_id"] for t in exact}
    backfill = [
        t for t in list_templates(sport=original_sport, level=level, limit=None)
        if t["global_id"] not in seen
    ]
    return (exact + backfill)[:limit]
