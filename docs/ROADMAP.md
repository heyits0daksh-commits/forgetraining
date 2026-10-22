## FORGE S&C Template Libraries — new sc_template_library.py module (v5.38)

Merges three new source files (410 pre-built, named S&C templates total —
grappling: 150, striking: 110, MMA: 150) into the live app as a browsable
reference catalog, not a second program-generation path — see the new
module's own docstring for why that distinction is load-bearing: routes.py
already records the static "Manual" mode (verbatim pre-written sessions
served instead of one the live engine reasoned over) as removed for good,
and these 410 templates are exactly that kind of pre-assembled artifact.

- **New**: `backend/data/sc_templates/*.json` — the three source files
  (`forge_grappling_sc_templates.json`, `forge_striking_sc_templates.json`,
  `forge_mma_sc_templates.json`) copied in unchanged. `backend/core/
  config.py` gained `SC_TEMPLATES_DIR` pointing at this new subdirectory.
- **New**: `backend/services/sc_template_library.py` — loads all three
  files once at import time (same one-load contract `ProgressionEngine`
  uses for `exercises.json`), indexes every template under a namespaced
  `global_id` (`"{library}:{id}"` — the grappling and striking source
  files each independently number templates starting at "SC-001", so a
  flat id space would collide), and exposes `list_templates` (filter by
  sport/level/goal/days_per_week/library, sport-agnostic pool included by
  default), `get_template` (full day-by-day breakdown by global_id),
  `sports_covered`, `library_summary`, and `templates_for_program` (the
  sport+level(+days_per_week)-matched shortlist `generate_program` uses).
  `LIBRARY_SPORTS` is derived from the loaded data rather than hand-typed,
  so it can't drift out of sync with what the JSON actually contains —
  confirmed Sanda is the one sport with real template coverage in *both*
  the grappling and striking libraries (clinch-and-throw exchanges span
  both), matching the overlap `sport_profiles.py` already encodes for
  Sanda's own quality profile, not a data error.
- **Wired in, not just parked as a reference endpoint**:
  `program_builder.generate_program` now returns an `sc_template_guidance`
  block (sport, a matched shortlist of template ids/names, the browse
  endpoint) whenever `req.sport` has any library coverage — `None`
  otherwise, same contract `conditioning_guidance`/`grappling_guidance`
  already use. It surfaces template ids to browse, never substitutes a
  template's own fixed exercise list for what the live engine just
  generated.
- **New endpoints**: `GET /api/v1/sc-templates` (filtered, summarized
  list + `sports_covered` + per-library `meta`) and
  `GET /api/v1/sc-templates/{global_id}` (one template's full breakdown,
  404 for an unknown id), mirroring `/api/v1/grappling-playbook`'s
  optional-filter, invalid-filters-return-empty-not-error shape.
- **Tests**: `tests/test_sc_template_library.py` — exact per-library
  counts (150/110/150, 410 total); global-id namespacing actually
  disambiguates the colliding "SC-001" ids; unknown-id lookups return
  `None`/404; sport coverage includes every expected sport; Sanda's
  dual-library coverage; filter combination (AND) and generic-pool
  inclusion/exclusion; uncovered-sport empty-list contract for both
  `list_templates`/`templates_for_program` and the `generate-program`
  wiring; both new endpoints end to end via the real `client` fixture.
- **Verified**: full suite re-run in batches against the real installed
  stack — **282/282 passing** (264 going in, +18 new). Live `uvicorn
  backend.main:app` boot re-confirmed clean (`GET /openapi.json` -> 200),
  plus manual `GET /api/v1/sc-templates`, `GET /api/v1/sc-templates/
  {global_id}`, and `POST /api/v1/generate-program` (Boxing, Advanced,
  2 days/week) calls against the live server all returned the expected
  shapes.
- **Not done in this pass**: the three libraries aren't cross-checked
  exercise-name-by-exercise-name against `exercises.json`'s own ids —
  template exercises are plain name strings from the source data, not
  resolved to real exercise ids the way `injury_taxonomy.py`'s Part 7.7
  substitutions are. A template's `equipment_required` (grappling/MMA)
  vs. `equipment_used` (striking) field-name difference is also left
  as-is rather than normalized to one shared key, since callers reading a
  specific template already know which library it came from.

## Iowa State Grappling S&C Playbook — new grappling_playbook.py module (v5.37)

Adds the Iowa State Grappling Strength & Conditioning Playbook (BJJ /
Judo / Sambo / Wrestling, Beginner->Elite) as data the live engine
reasons over — same "no disconnected copy of a guide's printed pages"
contract this doc already committed to for the Combat Sports & Rugby
manual (see routes.py's own note on the removed static "Manual" mode).

- **New**: `backend/services/grappling_playbook.py` — athlete
  classification + testing battery, the RAMP warm-up system, the 5-level
  rotational-strength spectrum, the gated Olympic-lift progression
  ladder, each level's full per-quality (Max Strength / Explosive/
  Ballistic / Grappling Accessory / Hypertrophy/Isolation / Loaded Carry/
  Grip / Olympic-Power Derivative / Prehab-Armor) sets-reps/%1RM/rest
  grid, the 4-week wave progression, the %1RM-to-rep chart, the
  body-area injury-armor system (keyed to `injury_taxonomy.py`'s own
  joint tags), the exercise selection matrix, the 16-week macrocycle +
  in-season load management, the seven session cards, and recovery/
  fueling guidance. Kept separate from `conditioning_protocols.py` (the
  Combat Sports manual's own sport-agnostic reference material) rather
  than merged into it — this source goes considerably deeper *inside*
  the lifting template (a per-level loading grid + wave, an Olympic
  ladder, a rotational spectrum) than that module's scope covers, and the
  two shouldn't silently blend under one shared warm-up/reference name.
- **Wired in, not just parked as a reference endpoint**:
  `program_builder.generate_program` now returns a `grappling_guidance`
  block (sport, discipline supplemental block, the athlete's level
  loading grid, week-1 wave %, the progression rule, the armor placement
  rule) whenever `req.sport` is one of the four sports the playbook
  covers — `None` otherwise, same contract `conditioning_guidance`
  already uses for sports outside its own coverage.
- **New endpoint**: `GET /api/v1/grappling-playbook` (optional `sport`/
  `level` query params narrow the discipline block / loading grid /
  wave), mirroring `/api/v1/conditioning-protocols`'s shape.
- **Tests**: `tests/test_grappling_playbook.py` — every level has all
  seven loading-quality rows; every grappling sport has a 5-item
  supplemental block, non-grappling sports get `None`; the 4-week wave
  and its out-of-range clamping; armor-protocol lookup including the
  Lower Back/Hip -> combined-slot resolution; macrocycle week lookup
  (including the single-week deload/retest rows at weeks 4/8/12 correctly
  taking priority over the range rows they overlap); the reference and
  generate-program endpoints end to end.
- **Not done in this pass**: the loading grid isn't yet fed into
  `load_prescription.py`'s per-exercise weight math (that module still
  drives working weight off `progression_engine.py`'s own difficulty-
  scaled `load_pct_1rm`, not this playbook's level-quality grid) — right
  now `grappling_guidance` surfaces the playbook's own numbers alongside
  the engine's existing prescription rather than the two being reconciled
  into one number. Session-card block order also isn't yet cross-checked
  against `programming_role.py`'s `ROLE_ORDER` for consistency beyond the
  shared "explosive before heavy strength" principle both already state.

## Deload-signal reconciliation: adaptive load can no longer fight a forced deload (v5.36)

Closes the concrete, fixable half of the "four uncoordinated deload
signals" gap this doc has flagged since v5.17 and re-confirmed as still
open in v5.19 and the v5.35 pass above. Not a redesign of all four
sources into one decision-maker (still a real, open product question -
see below) - this closes the one way they could actively contradict each
other.

- **Real bug found and fixed**: `ProgressionEngine.generate_session`
  computed `adaptive_training_load` (the history-driven volume/intensity
  nudge - RPE trend, weekly volume spike, missed-session gap, aggregate
  plateau/progressing read) *before* it computed `effective_readiness`/
  `deload_mode`. That meant a genuinely-earned "progressing trend, push
  intensity up 4%" or "plateaued, add volume" nudge from
  `compute_adaptive_load_adjustment` had no way to know the session was
  already going into `deload_mode` for a completely different reason - a
  low readiness slider, a 5/5 soreness report, or (via
  `program_builder.generate_program`'s own readiness clamp to <=35 on its
  calendar deload week) a scheduled mesocycle deload. Since
  `adaptive_load["intensity_multiplier"]` is folded multiplicatively into
  `readiness_factor` right after, this meant a plateau-busting or
  progressing-trend signal could partially undo a deload some other,
  earlier-decided signal had already committed to - three of the four
  signal sources this doc's v5.17/v5.19 notes flagged as "don't reconcile
  with each other" could genuinely fight, not just coexist without
  talking.
- **Fixed**: reordered `generate_session` so `effective_readiness`/
  `poor_sleep`/`max_soreness`/the pre-adaptive `deload_mode` read are
  computed *before* the `compute_adaptive_load_adjustment` call (moved up
  from where they used to run, no logic in that block changed - see the
  new `pre_adaptive_deload_mode` variable). `compute_adaptive_load_
  adjustment` (`recommendation_engine.py`) gained a `forced_deload: bool
  = False` parameter - when set, it caps both multipliers at "never push
  harder than baseline," identical treatment to the existing Fight Week/
  Post-Competition cap (same `if` branch now: `training_phase in
  ("Fight Week", "Post-Competition") or forced_deload`). It can still
  recommend easing FURTHER during an already-forced-lighter session (a
  bad RPE trend during a deload week is still worth surfacing) - the cap
  only ever stops it from pushing harder than baseline.
- **Not done in this pass, still genuinely open**: which of the four
  signal sources gets to *decide* a week is a deload in the first place
  is still uncoordinated - the fixed calendar week
  (`program_builder.py`), the client-side signal-triggered week
  (`checkSignalDeload` in `autoregulation.js`, reusing a real server-
  computed `recommend_deload` signal), and this session-generation-time
  `adaptive_training_load` are still three independent triggers with no
  single owner. This pass closes the one concrete way they actively
  fought each other's *magnitude* (a nudge partially undoing a deload);
  it doesn't merge the three *decisions* into one - that's still the
  real design question v5.17 originally flagged it as ("which signal
  should own in-progress-program adjustments"), not a mechanical fix.
- **Verified**: 2 new tests added to `tests/test_adaptive_load_engine.py`
  - `test_forced_deload_caps_multipliers_at_baseline` (unit-level, mirrors
  the existing Fight Week test exactly: the same falling-RPE history that
  pushes `intensity_multiplier` above 1.0 is capped at <=1.0 once
  `forced_deload=True`, and `auto_deload_recommended` is unaffected by
  the cap) and `test_generate_session_low_readiness_prevents_adaptive_
  load_from_pushing_intensity_up` (end-to-end through the real
  `/api/v1/generate-workout` route: the identical progressing-trend
  history that pushes `intensity_multiplier` above 1.0 at
  `readiness=80` is capped at <=1.0 at `readiness=20`, with
  `deload_mode: true` confirmed in the response). Full suite re-run in
  batches against the real installed stack (fastapi/uvicorn/pydantic/
  sqlalchemy/pyjwt/httpx, real network access confirmed in this sandbox):
  **264/264 passing** (262 going in, +2 new). Live `uvicorn
  backend.main:app` boot re-confirmed clean (`GET /openapi.json` -> 200)
  after these changes.

## Real full-suite smoke test + last known stale test fixed (v5.35)

Ran the real installed stack end-to-end (not stubs) for the first time
since the note this fix closes: `pip install` (fastapi/uvicorn/pydantic/
sqlalchemy/pyjwt/httpx/pytest, network access confirmed available in this
sandbox), then the full `tests/` suite in batches (262 tests total across
27 files) plus a live `uvicorn backend.main:app` boot with a real
`GET /api/v1/metadata` and `GET /openapi.json` call against it (200s,
correct shape, all 16 sports listed).

- **Fixed**: `tests/test_video_lookup.py::
  test_no_curated_link_falls_through_to_existing_behavior` was asserting
  on `EXERCISE_VIDEO_LINKS`'s live, growing content instead of isolating
  itself from it - `pushup_001` now legitimately has a real curated link
  (the "curated exercise demo videos" pass above), which correctly made
  `get_video_for_exercise` return a result instead of `None`, but the
  test's own fixture assumption ("no curated link exists for this id")
  had gone stale under it. This is the exact single pre-existing failure
  the v5.24 pass's own note flagged and left open ("1 pre-existing
  unrelated failure ... unrelated to this pass, not touched"). Fixed by
  `monkeypatch.delitem`-ing `pushup_001` out of the real dict for the
  duration of this one test, so it now asserts the no-curated-link
  *behavior* rather than a snapshot of today's data - won't go stale
  again as more curated links get pasted in.
- **Also checked, found to be already resolved by design rather than a
  bug**: the v5.22 pass's flagged "Skill/Technical pool converges on the
  same generic drill (Change-of-Direction 5-10-5) across Judo/Wrestling/
  Boxing" - re-verified live with full equipment available (including
  Wrestling Dummy/Boxing Heavy Bag/Tackle Bag) and it still converges
  today. Reading `programming_role.py` shows this is now intentional,
  not a scoring gap: every technique-correctness drill for these sports
  (Uchikomi entries, Wrestling Dummy takedowns, Heavy Bag combinations)
  was deliberately reclassified out of Skill/Technical entirely, into a
  `STRIKE_SKILL_EXCLUDED_ROLE` this app never selects into a generated
  session - the same "this app is a gym program builder, not a striking/
  grappling coach" reasoning the disclaimer screen already states, since
  a bag/dummy technique drill needs a live coach correcting form the same
  way sparring does. What's left in the Skill/Technical pool for these
  sports is only genuinely generic agility/functional work (`cod_5_10_5`,
  the obstacle circuit), so the convergence is the correct, safety-
  motivated behavior of a later pass, not the v5.22 gap re-appearing -
  left as-is, noting this here so a future pass doesn't "fix" it back
  into recommending unsupervised technique drilling.
- **Verified**: full `tests/` suite - **262/262 passing** (was 261/262
  going in), run in batches against the real installed stack in this
  sandbox (not `py_compile`/stubs). Live server boot confirmed clean.

## Severity-tier correction + a redundancy correction (v5.30, continued)

**Severity fix**: `Severe Spinal Stenosis / Osteophyte Locking` was coded
severity 1 (Mild) despite its own name saying "Severe," its own mechanism
text saying "advanced degenerative change" (directly contradicting this
file's own severity-1 tier definition of "early degeneration, stable
injuries"), and describing bilateral leg involvement + mechanical
locking that the plain `Lumbar Spinal Stenosis` entry (also severity 1,
correctly) doesn't have. Both entries being severity 1 meant the app
couldn't tell a routine presentation apart from an advanced one with
bony locking. Bumped to severity 2. Verified: 381 entries, counts shift
from 152/119/110 to 151/120/110 (severity 1/2/3), no other code
references this entry by name.

Scanned the rest of the taxonomy the same way (name/text implying a
different tier than the coded severity) and found no other genuine
mismatches - a handful of other hits (e.g. "Hip Dislocation - Grade 1
(Simple)" at severity 3) turned out to be correct on inspection: hip
dislocations are treated as severity-3 regardless of grade in real
practice, that's not a bug. I'm not comfortable re-grading the rest of
the 381 entries against clinical literature from here - that's exactly
the judgment call this review packet's Part 3 is asking an actual
clinician to make, not something to bulk-guess.

**Correction to the v5.30 systemic-flag fix above**: tracing the actual
call path in `progression_engine.generate_session`, `resolve_severe_injuries`
(v5.18) already raises `SevereInjuryBlockedError` and stops program
generation entirely for *any* severity-3 injury, before the `systemic`
check ever runs - it's checked first and unconditionally. So for the 8
severity-3 entries newly flagged `systemic=True` above, that flag has no
effect on `generate_session`'s actual behavior today: they were already
fully blocked by the stricter, pre-existing severity-3 gate. `systemic`
is real and load-bearing only for the three Concussion grades, because
Grade 1/2 are severity 1/2 - the only severities `resolve_severe_injuries`
doesn't already catch. The 8-entry fix is still correct data (the field
should reflect reality, and nothing consumes it outside this one
function today, so nothing else was silently wrong), but I overstated
its practical impact in the writeup - flagging that here rather than
letting it stand uncorrected.



Closes the two open questions raised in the clinician review packet
generated from v5.29 (`clinical_review_packet.md`, Part 2: "should
anything else be systemic?"). Only the three concussion grades were
flagged `systemic=True` before this pass, so every other severity-3
entry - even ones whose own `movement_restrictions`/`clinical_red_flags`
text already said "no training of any kind" or "not a
training-programmable condition" - only ever blocked exercises tagged to
that entry's single `joint`. A user reporting "Rib Fracture -
Displaced/Multiple (Flail Chest Risk)" (joint="Shoulder") would still be
handed a full leg day, contradicting that entry's own "No training until
medically cleared" restriction text.

- **Method**: scanned every severity-3 entry's own restriction/red-flag
  text for language already asserting a whole-body training stop (not
  just "avoid loading this joint") - i.e. fixed a text/flag *consistency*
  bug rather than introducing new severity grading. Left entries alone
  where the text is explicitly scoped to one region without emergency/
  whole-body language (e.g. "Unstable Spondylolisthesis / Facet
  Dislocation" stays joint-scoped - no cord/cauda-equina/breathing
  language in its own text).
- **`_muscle_condition()` (`backend/services/injury_taxonomy.py`)**
  gained a `systemic: bool = False` param (it never had one) - both
  Acute Compartment Syndrome entries now pass `systemic=True`.
- **8 entries newly flagged `systemic=True`**: Acute Compartment
  Syndrome (Anterior Leg, Deep Posterior Leg), Cervical Facet Injury -
  Stage 3 (Bilateral Dislocation), Lumbar Fracture - Unstable
  (Two/Three Column), Massive Central Disc Herniation, Burst Fracture
  (Spine), Fracture-Dislocation with Spinal Cord Injury, Rib Fracture -
  Displaced/Multiple (Flail Chest Risk).
- **`tests/test_systemic_injury_gate.py`**: replaced the old
  "concussion is the only systemic entry" assumption with an explicit
  `SYSTEMIC_INJURY_NAMES` set and a new
  `test_systemic_flag_matches_expected_set_exactly` pin, so a future
  addition/removal has to touch this test deliberately.
- **Not done this pass**: Part 3 of the review packet (severity-tier /
  difficulty-cutoff mis-grading) is still open - that's a broader
  clinical-judgment review that needs an actual sign-off, not a
  text-consistency fix like this one. Flagged for the next clinician
  review pass rather than guessed at here.
## Curated exercise demo videos + non-embeddable link-out fallback (v5.26)

Closes the PDF roadmap's own top priority ("exercise demo media") with an
actual delivery mechanism, on top of the live-search infrastructure
(`video_lookup.py`, Phase 18/19) that already existed. No hand-typed link
file was available to import this pass, so this builds the plumbing to
make adding one trivial later, and ships fully functional today with the
existing live-search fallback for every exercise not yet curated.

- **New `backend/data/exercise_video_links.py`**: one dict,
  `EXERCISE_VIDEO_LINKS: dict[str, str]`, keyed by exercise `id`. Empty by
  default (module docstring explains exactly how to fill it in and what
  link shapes are supported) - pasting in real links here is the entire
  integration step, no code changes needed elsewhere.
- **`video_lookup.get_video_for_exercise`**: now checks a curated link
  first, before the channel/API-key checks or the on-disk cache - a
  curated link always wins and resolves fresh on every call (URL parsing
  only, no network), so editing the file takes effect immediately.
- **New `resolve_static_video_link()`**: turns one hand-typed URL into the
  same `VideoResult` shape the live search already returns, auto-detecting
  4 shapes - YouTube (`watch?v=`, `youtu.be/`, `/shorts/`) and Vimeo links
  both embed via iframe; a direct `.mp4/.webm/.mov/.m4v` file link embeds
  via a plain `<video>` tag; anything else (Instagram, TikTok, an article
  page) is marked `embeddable: false` so the frontend link-outs to it in a
  new tab instead of trying to force it into an iframe.
- **`GET /api/v1/exercises/{id}/video`**: checks `EXERCISE_VIDEO_LINKS`
  before its existing "no channel assigned" / "no API key" early-outs, so
  a curated link works even for equipment types with no assigned live-
  search channel and even with zero YouTube API key configured.
- **Frontend (`exercise-modal.js`)**: the existing "Watch Demo" button
  (already wired to open on click for any exercise, across the results
  view, Program Builder, and the swap panel - `data-open-modal` handlers
  already existed) now branches three ways instead of always assuming an
  iframe: YouTube/Vimeo -> iframe, a direct file link -> `<video controls>`,
  non-embeddable -> a "Watch on <source>" button opening `watch_url` in a
  new tab. New `.video-embed-wrap video.video-embed-native` CSS rule
  (`styles.css`) gives the `<video>` tag the same absolute-fill treatment
  the iframe already had.
- **New `tests/test_video_lookup.py`** (11 tests): URL-shape detection for
  all 4 cases, curated-link-wins-over-missing-channel/API-key at the
  service layer, and the route returning the right `available`/
  `embeddable`/`watch_url` shape for both an embeddable and a
  non-embeddable curated link, plus the existing unknown-id 404 untouched.
  Full suite: **197/197 passing** (186 prior + 11 new), run against the
  real installed stack.
- **Not done this pass**: no real links are populated yet -
  `EXERCISE_VIDEO_LINKS` ships empty, so every exercise still falls
  through to the existing live-search behavior until real links are
  pasted in. Whoever has the actual curated link set should drop them into
  `backend/data/exercise_video_links.py` directly - the id has to match
  `data/exercises.json`'s real exercise ids, not display names.

## Fix: movement-family repeated up to 4x/week in Program Builder (v5.25)

Closes `tests/test_generation_endpoints.py::test_generate_program_does_not_repeat_the_same_movement_family_all_week`,
the one pre-existing failing test flagged (but not fixed) since v5.24's
first real smoke test. A Judo/4-day program's Hinge, Squat, Carry, and
Full-Body-Snatch slots each resolved to the *same* `movement_family`
every single day of the week (e.g. `clean_highpull_001` on day 1,
`snatch_highpull_001` on day 2, then `clean_highpull_001` again on days 3
and 4) - four distinct-looking exercises a coach would call the same
drill, because the existing `exclude_exercise_ids`/`recent_families`
machinery (`_pick_with_variety`) is deliberately soft: it only
*deprioritizes* a same-family repeat when a genuinely different family
clears the score floor, and for these four slots on this sport/equipment
combo nothing else ever did.

- **Root cause, once isolated**: soft deprioritization alone can't
  guarantee a weekly cap - by design (see `_pick_with_variety`'s own
  docstring: "never hard-excludes same-family candidates, so a thin pool
  ... still fills the slot"). A real weekly cap needs an actual hard
  filter somewhere, which didn't exist - `exclude_exercise_ids` was the
  only lever, and it only ever suppressed the exact same id, not every id
  sharing a movement_family.
- **Fixed**: added a new `hard_exclude_exercise_ids` field to
  `WorkoutRequest` (`backend/models/schemas.py`) - unlike
  `exclude_exercise_ids`, this removes ids from the candidate pool
  entirely, before role/pattern selection ever runs (same point in
  `generate_session` where injury/STRIKE_SKILL exclusions already happen -
  `backend/services/progression_engine.py`). `program_builder.py` now
  tracks `family_counts_this_week` (reset every week, alongside the
  existing `used_this_week`) and, once a family hits
  `_MAX_SAME_FAMILY_PER_WEEK` (2) uses in a week, hard-excludes every
  exercise id sharing that family for the rest of that week via the new
  field - forcing a genuinely different movement into the slot instead of
  a same-family relabel.
- **One real bug in the first attempt, caught before it shipped**: the
  first version of the hard-exclude list comprehension skipped any id
  already in `used_this_week`, on the theory that an already-used id
  didn't need re-excluding - this was backwards. It meant the *exact*
  exercise id already picked (e.g. `clean_highpull_001` from day 1) was
  the one id NOT hard-excluded on day 3, so the engine kept re-picking
  the literal same exercise it had already used, while every other family
  member correctly got blocked. Caught by instrumenting
  `generate_session` directly and diffing "was this picked id actually in
  the exclude list sent" per call - fixed by removing that filter
  entirely; the hard-exclude set is now the full family membership list,
  with no carve-out.
- **Verified**: the exact Judo/Advanced/4-day/1-week scenario from the
  test now shows each of the four previously-repeating families capped at
  2 uses across the week instead of 4, with a different, real movement
  filling the other two slots each day. Full suite re-run against the
  real installed stack: **186/186 passing** (185 pre-existing + this one
  now fixed, no new failures introduced) - closes the standing gap v5.24
  flagged ("the one failure ... is an unrelated program-variety bug, not
  auth").

## Session architecture — three-tier strength split (Primary/Secondary/Assistance) (v5.23)

Closes the P0 gap: "fix session architecture / exercise ordering." Every
loaded-strength exercise (Squat/Hinge/Horizontal-Vertical Push/Pull) at
difficulty >= 3 collapsed into a single "Primary Strength" role in
`programming_role.classify_programming_role` - a true max-effort barbell
lift (difficulty 5) and a goblet squat (difficulty 3) got identical
selection and sequencing treatment. A real coach's session runs Warm-up ->
Power -> Primary Strength -> **Secondary Strength** -> Assistance/
Accessory -> Core -> Conditioning - a distinct "second big lift" tier that
sits after the day's heaviest lift but before lighter accessory work,
which the engine had no concept of.

- **Fixed**: added `"Secondary Strength"` to `ROLE_ORDER` in
  `programming_role.py`, between `"Primary Strength"` and `"Accessory /
  Hypertrophy"`. The loaded-strength-category branch of
  `classify_programming_role` now splits three ways instead of two:
  difficulty >= 4 stays `Primary Strength`, difficulty == 3 is the new
  `Secondary Strength`, difficulty <= 2 stays `Accessory / Hypertrophy`
  (unchanged). `session_order_rank` picks the new role up automatically
  since it's a pure lookup against `ROLE_ORDER`'s index - no other
  ordering code needed to change.
- **Wired into selection, not just classification**: `progression_engine.
  _STRUCTURAL_ROLES` now also excludes `"Secondary Strength"` (same
  reasoning as the existing Primary Strength/Accessory exclusion - it
  draws from the same six loaded-strength categories the movement-pattern
  coverage pass owns). `_select_compound_accessory_finisher` (the
  single-session "generate me a workout" path) gained a `secondary_count`
  slot, taken right after `Primary Strength` and before `Accessory /
  Hypertrophy`, duration-gated the same way the v5.22 skill/power slots
  are: 0 below 45 minutes, 1 from 45-74 minutes, 2 at 75+ minutes. The
  Program Builder's per-day path (`_select_role_balanced`) needed no
  selection-logic change - it already fills by movement-pattern category,
  not role - so it picks up the corrected three-tier sequencing for free
  through `session_order_rank` alone.
- **Verified**: added `tests/test_programming_role.py::
  test_loaded_strength_splits_into_three_difficulty_tiers` (pins the
  difficulty->role mapping across all loaded-strength-category exercises
  in `data/exercises.json`), `test_secondary_strength_sequences_between_
  primary_and_accessory` (rank ordering), and
  `test_generated_session_respects_full_coaching_order` (live
  `generate_session` regression across 30/45/60/75/90-minute Powerlifting
  requests with real biometrics - asserts `session_order_rank` is always
  non-decreasing in the returned exercise list). Also ran a manual live
  check confirming the returned role sequence is now literally `Primer /
  Activation -> Primary Strength -> Secondary Strength (x1-4 depending on
  duration) -> Accessory / Hypertrophy -> Core & Stability` for a real
  Powerlifting/Barbell request, where before this fix there was no
  Secondary Strength tier at all. Ran against the real installed
  `requirements.txt` stack (not a stand-in) - full `tests/` suite: 178/178
  passing (175 pre-existing + 3 new).

## Heavy floor-deadlift patterns creeping to 8-9 reps (v5.22)

Follow-up to the rest-seconds fix above, same screenshot: a Barbell
Conventional Deadlift was also prescribed 8 reps at 73% 1RM. Reproduced -
the same `_apply_prescription_bias` goal-window remap applies its rep
window (e.g. `strength_hypertrophy` is 5-8 reps) identically to every
"strength"-type exercise, with no distinction between a Romanian Deadlift
(a deliberately submaximal, partial-ROM pattern real programs run at 8-12+
reps) and a full-ROM conventional/sumo deadlift off the floor or a Good
Morning (both near-1RM-technical-limit patterns on every rep, where the
real risk of grinding out rep 7-8 is a rounded back or a fried grip, not
insufficient load). No coach programs a heavy floor deadlift at 8 reps.

- **Fixed**: added `_MAX_EFFORT_HINGE_FAMILIES` (`hinge__deadlift`,
  `hinge__pull`, `hinge__good_morning` - the exercises' own
  `movement_family`, so this reads off real data, not exercise names) and
  `_MAX_EFFORT_HINGE_REP_CAP = 6`. `_apply_prescription_bias` now takes an
  optional `movement_family` and clamps the interpolation's rep window to
  the cap before computing reps, wired through both real callers
  (`program_builder.py`'s per-day bias pass and
  `progression_engine.py`'s single-session prescription). Romanian
  Deadlift, kettlebell swings, and every other Hinge exercise not in the
  set are unaffected - still get whatever the goal window prescribes.
- **Verified**: direct unit check - a max-effort-hinge prescription capped
  at 6 reps under the exact goal/load inputs that give Romanian Deadlift
  7-9 reps in the same window. Re-ran the same Powerlifting/Get Strong
  program that reproduced the original bug across 2 weeks: Good Morning
  now caps at 6 reps (was 8), Romanian Deadlift correctly stays uncapped
  at 9. Full `tests/` suite: 175/175 passing.

## Rest-time interpolation producing non-coaching numbers, e.g. "158s" (v5.22)

Found from a live screenshot: a Pause Back Squat came back prescribed
"4 x 8 reps @ 87.5kg (73% 1RM ref) · rest 158s". Reproduced exactly against
`data/exercises.json` with a real Powerlifting/Get Strong program request -
same 73% load, same 158s rest, plus a sibling Good Morning at the identical
158s and an Overhead Press at 256s.

- **Root cause**: `_apply_prescription_bias`'s goal-window remap linearly
  interpolates `rest_seconds` between a bias's low/high bound (e.g.
  `strength_hypertrophy` is 150-240s) using the same continuous 0-1 `idx`
  it uses for load/reps/sets, then just `round()`-ed to the nearest whole
  second. Every other rest value hand-typed elsewhere in this codebase
  (60/90/120/180/75 in `progression_engine.py`) is a multiple of 15 - real
  coaching numbers, not single-second precision - so "158s"/"256s" reads as
  a bug to anyone using the app even though the interpolation math itself
  was working as designed.
- **Fixed**: added `_round_rest_seconds()` (snaps to the nearest 15s,
  floor 15s) and routed both `_apply_prescription_bias` branches
  (`strength` and `strength_bodyweight`) through it instead of the bare
  `round()`. The interpolation itself is unchanged - only the final
  snap-to-grid at the end.
- **Verified**: re-ran the exact Powerlifting/Get Strong request that
  reproduced the bug - 158s -> 165s, 256s -> 255s, all six strength-type
  prescriptions in the sampled days now land on a 15s increment. Full
  `tests/` suite re-run: 175/175 passing (no test asserted the old
  raw-second values).

## Single-session sport-specificity — Skill/Power roles were never selected (v5.22)

Closes the P0 gap: "make sport-specific sessions actually sport-specific."
`_select_compound_accessory_finisher` (the path every plain "generate me a
workout" request goes through - not the Program Builder's per-day
`_select_role_balanced`, which was always fine) only ever pulled from
Primary Strength / Accessory / Conditioning. Skill/Technical and Power &
Explosive - the two roles carrying actual sport IDENTITY (a Judo grip
drill, a Wrestling sprawl-to-sprint, a reactive jump) - were never
selected in single-session mode at all.

**Verified live** (full equipment, Intermediate, 60-min, before this fix):
Judo, Wrestling, and Boxing sessions all came back as near-identical
generic strength templates (Zercher Squat / Meadows Row / an RDL) with
zero skill or power content, differing only in which specific squat/row
scored marginally higher for that sport.

- **Fixed**: added duration-gated `skill_count`/`power_count` slots to
  `_select_compound_accessory_finisher`, filled FIRST (before Primary
  Strength) so they can't be crowded out - 1 Skill/Technical + 1 Power/
  Explosive for sessions >=45 min, 1 Skill/Technical only below that
  (a coach cuts the jump before the sport's own technical work).
  `session_order_rank` sequencing (already correct) still runs everything
  through the same skill -> power -> strength -> accessory -> conditioning
  coach order afterward.
- **Verified**: re-ran the same three sports live post-fix - every session
  now carries a Skill/Technical and Power/Explosive pick (e.g. Judo got
  Change-of-Direction 5-10-5 + Medicine Ball Rotational Throw ahead of its
  compound lifts); `tests/` still 175/175 passing (no test asserted the
  old skill/power-less shape).
- **Not fixed in this pass, flagged for a future one**: the Skill/
  Technical candidate pool for several sports at this equipment tier
  converged on the same generic drill (Change-of-Direction 5-10-5) across
  Judo/Wrestling/Boxing rather than a sport-distinct one - a data/scoring
  gap in `sport_profiles.py`'s blended transfer score for "Sport Specific"
  category exercises, not a selection-logic gap. Worth a follow-up pass.

## Volume engine — weekly SET volume per muscle group, checked against landmarks (v5.21)

Closes the P0 gap flagged going into this pass: `program_builder.
_weekly_muscle_frequency` answers "how many days/week does each muscle get
direct work" but nothing computed or checked *how much* - total weekly set
volume per muscle vs. an experience/goal-appropriate target. A muscle could
hit the existing 2x/week frequency minimum at 6 sets/week (badly under-
dosed) or 24 sets/week (likely excessive) and look identical to that view.

- **New module**: `backend/services/volume_engine.py`. Collapses
  `exercises.json`'s fine-grained anatomical muscle tags (e.g. "Anterior
  Deltoid"/"Lateral Deltoid"/"Rear Deltoid"/"Deltoids") into ~13 canonical
  trainable groups, sums each week's real prescribed sets per group
  (primary movers full credit, secondary/assisting half credit - the same
  convention the volume-landmark literature this is checked against uses),
  and checks the 9 groups with real literature grounding (Chest, Back,
  Traps, Shoulders, Biceps, Triceps, Quads, Hamstrings, Glutes) against a
  weekly-set target range. Reuses `pl_hypertrophy_manual.
  LOOK_JACKED_LEVELS`'s own `weekly_sets_per_muscle` ranges (Beginner 8-10
  ... Elite 20-22, transcribed from a real hypertrophy guide) as the
  Build-Muscle baseline rather than inventing a second table, then scales
  that baseline per goal (`GOAL_VOLUME_MULTIPLIER`) since a "Get Strong"/
  "Power" program is correctly not trying to hit hypertrophy-volume
  numbers - Get Strong runs at 0.5x, Conditioning/Skill Development at
  0.35x. Minor stabilizer groups (Forearms, Adductors, Hip Flexors, Neck,
  Lower Leg/Ankle, Lower Back) are counted and reported but marked
  `not_tracked` rather than flagged, since the literature doesn't have an
  established per-week target for those.
- **Wired into `program_builder.generate_program`**: every week in the
  response now carries `weekly_volume` (per-muscle sets/target/status/
  note, same shape `muscle_frequency` already has). The program-level
  response gained `weekly_volume_summary` (average sets/muscle across
  non-deload weeks, same deload-exclusion the existing
  `muscle_frequency_summary` uses), `under_dosed_muscles`, and
  `over_dosed_muscles` - the aggregate answer, mirroring how
  `under_trained_muscles` already surfaces the frequency-side aggregate.
- **Real bug found and fixed during this pass, not a pre-existing one**:
  the first version of `_parse_range` (turns `"14-18 sets"` into a
  `(14.0, 18.0)` tuple) kept `-` characters in the digit-scan before
  splitting on whitespace, so `"14-18"` stayed one un-splittable token and
  `float("14-18")` raised on every call - every landmark lookup silently
  returned `None` and every muscle group came back `not_tracked` instead
  of evaluated. Caught immediately by direct verification (see below,
  same pattern as every other pass in this doc) before it reached a test
  file, let alone a review. Fixed by switching to `re.findall(r"\d+(?:\.\d+)?", ...)`
  instead of a hand-rolled character scan.
- **Verified**: ran `compute_weekly_muscle_sets`/`evaluate_weekly_volume`/
  `landmark_for` directly against real `data/exercises.json` exercise
  entries (Flat Bench Press, Barbell Back Squat, Standing Barbell Curl,
  Pendlay Row) with a hand-built `day_results` list matching
  `generate_program`'s real shape - confirmed full credit to primary
  movers, half credit to secondary, goal-scaled target ranges shrinking
  correctly from Build Muscle -> Get Strong -> Conditioning, and all four
  status bands (under/optimal/high/excessive) firing at the right
  thresholds. Added `tests/test_volume_engine.py`: 6 unit-level tests (run
  directly, all passing) plus 3 end-to-end tests through
  `POST /api/v1/generate-program` written to the same contract as
  `tests/test_generation_endpoints.py` but NOT executed in this sandbox
  (no network to install fastapi/pydantic) - same standing caveat as every
  prior pass; run `pytest tests/test_volume_engine.py -q` once network
  access exists.
- **Not done in this pass, flagged for a future one**: nothing yet
  *enforces* the volume targets during exercise selection - `program_
  builder.py` reports under/over-dosed muscles after the fact but doesn't
  feed `weekly_volume` back into which exercises get picked or how many
  sets they're prescribed. That's real progression/selection-engine work
  (P0 "exercise selection logic" / P1 "progression system" on the
  original priority list), not a volume-engine gap - this pass's scope
  was making the number exist and be checked at all, which it now is.

## Prescription-quality audit — barbell isolation exercises over-loaded (v5.20)

Found while doing a manual prescription-quality audit (no live server in this
sandbox - verified by extracting `_prescribe_volume_core` and running it
directly against real `data/exercises.json`, plus `add_working_weight`, both
unchanged in behavior except where noted below).

- **Real bug found and fixed**: `_prescribe_volume_core`'s isolation-vs-
  compound classifier (added to fix an earlier reported "Dumbbell Hammer
  Curl prescribed 35-60kg" bug - see that fix's own comment in
  `progression_engine.py`) exempted an entire equipment list - including
  `"barbell"` - from ever being classified as isolation, regardless of what
  the exercise's own `strength_requirements` ratio field said. Barbell
  DOES have a real tested %1RM anchor (unlike bodyweight/rings/pull-up bar/
  suspension trainer/parallel bars, which never did), so its ratio field is
  a trustworthy signal, not one that needed blanket protection. Concretely:
  Standing Barbell Curl, Barbell Drag Curl, Barbell 21s, Barbell Reverse
  Curl, and Barbell Skullcrusher all carry a correctly-set `ratio: 0.0` (the
  database's own "don't load this off a compound max" signal) but were
  still falling through to the heavy compound branch - verified live: a
  strong-lifter profile (160/220/250kg bench/squat/deadlift) was prescribed
  a **110kg Barbell Skullcrusher** and 92.5-102.5kg barbell curls, weights
  well beyond anything a human elbow tolerates for those movements.
  **Fixed**: `"barbell"` removed from the exemption set in
  `_prescribe_volume_core` - barbell exercises are now judged purely by
  their own ratio data. The 9 legitimate barbell exercises that had been
  leaning on the now-removed exemption because their ratio was left at the
  `0.0` placeholder (Good Morning, Kang Squat, Zercher Reverse Lunge,
  Zercher Split Squat, Meadows Row, Single Arm Barbell Row, Fat-Grip Row,
  Inverted Bar Row (Knees Bent/Legs Straight)) got real ratios set directly
  in `data/exercises.json`, benchmarked against comparable existing entries
  (Pendlay Row 0.6, Yates Row 0.55, Romanian Deadlift 0.5) rather than
  relying on an equipment-wide carve-out to get correct behavior by
  accident.
- **Secondary hardening, not an active bug today**: `load_prescription.py`'s
  Vertical Pull branch (the pull-up-anchored path) skipped the dumbbell/
  kettlebell per-implement conversion every other category gets - dead code
  currently (no real Vertical Pull exercise uses Kettlebell equipment, and
  the one Dumbbell case - curls - never reaches this path now that the
  isolation fix above catches them first), but would have silently shown a
  combined-total number instead of a per-implement one for a future
  Kettlebell-assisted pulldown variant. Fixed to mirror the generic path's
  equipment handling exactly.
- **Verified**: re-ran the before/after prescription for all 14 affected
  barbell exercises plus 3 unaffected controls (Standard Push-Up, Pendlay
  Row, Barbell Back Squat) directly against the real code - the 5 genuine
  isolation exercises now correctly return `type: "isolation"` (rep-only,
  no fabricated load); the 9 patched compound/bodyweight-loaded exercises
  and all 3 controls are numerically unchanged from before this pass. Also
  re-ran `tests/test_exercise_data_integrity.py`'s own checks by hand (no
  duplicate ids, no dangling DAG references, full required-field set,
  808 exercises intact, all 9 patched exercises kept their full
  `strength_requirements` key shape) - all pass.
- **Known limitation, NOT fixed in this pass, flagged for a future one**:
  `load_prescription.py` anchors load off a single fixed ratio per
  *category* (e.g. every Hinge exercise gets 100% of the deadlift anchor),
  not per individual exercise - so Good Morning and Sumo Deadlift still get
  identical intensity treatment despite being very different demands, and
  Single Arm Barbell Row (unilateral) gets the same load as a bilateral
  Pendlay Row. This predates this pass and isn't a regression from it -
  fixing it means making `add_working_weight` exercise-ratio-aware across
  the board (using each exercise's own `strength_requirements` ratio as
  the load multiplier, not just as an isolation on/off switch), which is a
  bigger design change than this pass's scope.
- **Standing caveat, same as every prior pass**: this sandbox has no
  network access, so verification was direct logic execution against the
  real data/module code (not stubs, but also not a live `uvicorn`/pytest
  run) - worth a real `pytest tests/ -q` pass once network access exists,
  same as the standing smoke-test note throughout this document.

## Section 1.2 spec implementation — per-exercise load ratio + unilateral adjustment

Closes the "Known limitation, NOT fixed in this pass" note directly above
(Good Morning/Sumo Deadlift, Single Arm Barbell Row/Pendlay Row), per the
`FORGE_Section_1.2_Implementation_Spec.docx` build order (steps 1-2; step 4
is the ongoing per-exercise unilateral-factor iteration, step 3 is content
work, not started here - see below).

- **Per-exercise load ratio (spec section 1)**: `add_working_weight`
  (`load_prescription.py`) now takes the exercise's own
  `strength_requirements.{bench,squat,deadlift}_ratio` as the load
  multiplier when it's set (>0), falling back to the flat
  `_ANCHOR_BY_CATEGORY` per-category ratio exactly as before for the
  exercises that don't have one yet - the resolution order the spec asks
  for (exercise ratio -> category default -> the existing 20-92% hard
  clamp in `progression_engine.py` as the last-resort floor/ceiling), with
  zero schema migration needed since the field already exists and is
  already populated for several hundred exercises (it was only ever being
  read for isolation-gating and prerequisite checks, never as a load
  multiplier). Verified: Good Morning (deadlift_ratio 0.4) vs Sumo
  Deadlift (deadlift_ratio 0.9) now diverge correctly (50.0kg vs 112.5kg
  off a 180kg deadlift @ 70%, previously both would have shown 125.0kg).
- **Unilateral load adjustment (spec section 2)**: added the "Option A"
  bridge - a global default factor (0.55, overridable per exercise via a
  new optional `strength_requirements.unilateral_adjustment_factor` key) -
  applied only when `movement_type == "Unilateral"`, equipment isn't
  Dumbbell/Kettlebell (which already get a per-implement discount via the
  existing `DB_KB_LOAD_RATIO` path - stacking both would double-discount),
  and the exercise doesn't already have its own calibrated ratio (Single
  Arm Barbell Row's `deadlift_ratio: 0.45` already reads as a hand-tuned
  per-arm number - confirmed unchanged, not further discounted). Surfaced
  in `weight_note` ("adjusted for single-arm/single-leg loading") per the
  spec's "why this weight" integration point. Note this factor is
  currently a no-op for the shipped catalog: every unilateral barbell/
  machine exercise that reaches `type: "strength"` today already has a
  nonzero exercise-specific ratio (the ones that don't - Single-Arm Pec
  Deck Fly, Single-Arm Cable Curl, etc - are genuine isolation work and
  correctly stay routed to the no-fabricated-load isolation branch instead
  of this one); it's live infrastructure for the first newly-added or
  not-yet-calibrated unilateral exercise, not a change to any number today.
- **Not done in this pass**: the spec's "Additional integration point" -
  deriving a unilateral prescription from its bilateral counterpart's
  logged 1RM via the knowledge-graph progression/regression edges, instead
  of a flat global factor. Most exercises' `progressions`/`regressions`/
  `alternatives` arrays are empty in the current data, so this would need
  real edges added first; flagged as a follow-up rather than half-built
  here. Also not done: iterating the unilateral factor from global to
  per-movement-pattern (spec's Option B / build-order step 4) - needs
  logged usage data to calibrate against, per the spec's own build order.
- **Section 3 ("Expand Thin Equipment Groups") - audit only, not content**:
  added `scripts/data_ops/audit_equipment_depth.py`, which reports current
  exercise count per equipment tag against a per-tier target (30 for
  core/Barbell/Dumbbell/Bodyweight, 20 for secondary equipment, 15 for
  niche/specialty implements - the spec's own "scaled to how central that
  equipment is" ask, not a flat number) and ranks by gap size. Confirms
  the spec's own example numbers exactly: Log Bar and Husafell Stone are
  both at 7/15. Writing the actual new exercise entries (name,
  description, muscle groups, progression/regression links) for each thin
  group is a content-authoring task, not done in this pass - the script
  only tells you where to start, same division of labor
  `generate_batch6_thin_equipment.py` and friends already established for
  the equipment groups expanded before this pass.
- **Verified**: new `tests/test_load_ratio_and_unilateral.py` (8 tests,
  all passing) covers the Good Morning/Sumo Deadlift divergence, the
  no-`strength_requirements`/zero-ratio fallback (unchanged from before
  this pass), an exercise ratio overriding a *nonzero* category default
  (Pendlay Row vs the generic Horizontal Pull figure), the
  no-double-discount guarantees for both the exercise-ratio and
  Dumbbell/Kettlebell cases, the per-exercise unilateral-factor override,
  and that bilateral exercises never pick up the unilateral discount. Full
  `pytest tests/ -q`: 196 passed, 1 pre-existing unrelated failure
  (`test_video_lookup.py::test_no_curated_link_falls_through_to_existing_behavior`
  - a curated video link now exists for `pushup_001`; unrelated to this
  pass, not touched).

# FORGE production-readiness roadmap

Status of the 17-phase plan. Each future session should pick up at the next
"pending" phase, verify against this file, and check it off.

| Phase | Description                          | Status   |
|-------|---------------------------------------|----------|
| 1     | Project structure                     | Done     |
| 2     | Modularization (split large files)    | Done — schemas live in `backend/models/schemas.py`, the `ProgressionEngine` now lives in `backend/services/progression_engine.py`, every endpoint moved to `backend/api/routes.py` (an `APIRouter`), and `backend/main.py` is now ~60 lines: app creation, CORS, the startup hook, and `app.include_router(router)` |
| 3     | Configuration (.env + Settings)       | Done     |
| 4     | Database (SQLite + repository layer)  | Done (v5.13) — real migration framework (`backend/migrations/`) replacing the bare `create_all` call, and a repository layer (`backend/repositories/`) wrapping every raw `db.query(...)` that used to live inline in `readiness_service.py`/`auth_service.py`. See "Database completion pass" below. |
| 5     | Scored recommendation engine          | Done (first pass) — history-based personalization on top of the existing static scoring. See "Recommendation-engine pass" below |
| 6     | Persistent user profiles              | Done (first pass) — accounts, JWT auth, profile prefill. See "Auth pass" below |
| 7     | Intelligent/adaptive programming      | Partial — heuristic readiness suggestion (`readiness_service.py`) done; server-side adaptive load engine (Phase 19) and rehab-stage engine done and, as of v5.17, actually wired to the frontend end-to-end; not a scored model, and v5.17's own "not touched" note (4 uncoordinated deload signal sources, incl. a client-side duplicate in `autoregulation.js`) is still open |
| 8     | Performance / caching                 | Done (first pass) — see "Caching pass" below |
| 9     | Structured logging                    | Done (first pass) — see "Logging + error-handling pass" below |
| 10    | Error handling / custom exceptions    | Done (v5.14 pass extends the first pass) — `auth_service.py`'s remaining inline `HTTPException` raises (refresh-token/password-reset/get_current_user) migrated to the `ForgeError` hierarchy, closing the exact gap the first pass's own "deliberately not migrated" note flagged. See "Error-handling completion pass" below. |
| 11    | API improvements (models, versioning) | Partial — every endpoint already lived under `/api/v1` before this pass; the consistent `{"error": {...}}` envelope from Phase 10 is the main improvement made here, and v5.14 extended that envelope to auth_service.py's routes too. Response-model coverage audit and an actual `/v2` story are still open. |
| 12    | Web UI upgrades                       | Done (login/signup) — a full login/register modal, account panel, token persistence, and boot-time session restore already exist in `frontend/web/index.html` (`openAuthModal`/`wireAuthForm`/`openAccountModal`/`refreshCurrentUser`), wired to `/auth/register`, `/auth/login`, `/auth/me`. This roadmap row and the README's "Web UI" section had gone stale — neither mentioned it. See "Web UI audit" pass below. |
| 13    | Test suite (pytest)                   | Done (first pass) — see "Test suite pass" below |
| 14    | Documentation                         | In progress (this file + README) |
| 15    | Code quality pass                     | Partial — the `on_event`-deprecation warning is fixed. This pass (v5.12) removed the dead imports flagged in `progression_engine.py` (`SEVERITY_DIFFICULTY_CEILING`, `part7_substitution_guidance`, `PART7_DISCLAIMER`, `explain_exercise`, `SPORT_MOVEMENT_EMPHASIS`, `SPORT_QUALITY_PROFILES`, `sport_conditioning_profile` — all imported but never referenced in that file, since callers import them directly from their source modules instead), `routes.py` (`INJURY_TAXONOMY`), and test-only unused imports in `tests/test_auth.py` (`pytest`) and `tests/conftest.py` (`os`). `pyflakes` itself isn't installable in this sandbox (no network), so this was done with a hand-rolled `ast`-based unused-import scan plus manual grep verification of every flagged name before removal, then `python -m py_compile` on every touched file. Not done: real `pyflakes`/`ruff` run to catch anything the hand-rolled scanner's simpler heuristic misses (e.g. unused local variables, which it doesn't check at all — only unused imports). |
| 16    | Security hardening                    | Partial — one real IDOR bug found + fixed by the Phase 13 pass (see below); no broader audit done yet |
| 17    | Future-AI-feature architecture hooks  | Done — extension point + a real working provider (`AnthropicInsightProvider`), off by default, now covering both the single-session AND program-level paths (v5.14 closed the "no program-level hook" gap). See "AI-hooks pass" below |

## Why this is being done incrementally

The original request asks for all 17 phases — including a rewritten
persistence layer, a rewritten scoring engine, adaptive programming logic,
and a rebuilt UI — in one pass. Each of those is a real design decision with
tradeoffs (e.g. SQLite schema shape, what the scoring weights should be,
what "adaptive" means for volume/deload logic) that's worth doing carefully
and testing rather than generating in bulk. Doing them one or two phases at
a time, with working code at the end of each, keeps the app runnable
throughout instead of risking a big-bang rewrite that breaks silently.

## Latest pass — Rehab-stage frontend wiring + adaptive-load transparency (v5.17)

A full-codebase audit of the decision flow (user profile -> injuries/safety
-> readiness -> filtering -> scoring -> adaptive load -> progression ->
workout/program generation) turned up two features that were fully built
and tested server-side but never actually reachable by a real user, plus
one place server-side data was computed and then silently dropped before
it reached the API response. All three are closed by this pass; no engine
logic changed, only what the frontend sends/shows and one dict `program_
builder.py` builds.

- **Real bug found and fixed - the rehab-stage engine was 100% dead code
  from a user's perspective.** `REHAB_STAGES`/`resolve_rehab_stage`/
  `_rehab_stage_tier` (`injury_taxonomy.py`), the `injury_joint_stage`
  threading through `classify_exercise_safety`/`find_alternatives`, and
  `WorkoutRequest.injury_stages`/`ProgramRequest.injury_stages` were all
  correctly implemented and covered by `tests/test_rehab_stage_
  progression.py` - but nothing in `frontend/web/js/*.js` ever read `GET
  /api/v1/metadata`'s `rehab_stages` key, rendered a stage picker, or sent
  `injury_stages` in any request. Every real session/program therefore ran
  with `stage=None` for every injury, no matter how the engine's own stage
  logic was designed to behave. Fixed: `injury-browser.js` now renders an
  optional rehab-stage `<select>` next to each checked injury chip (hidden
  until the chip is checked, populated from `S.metadata.rehab_stages`,
  cleared automatically if the chip is unchecked so a stale stage can never
  survive an unflagged injury); `S.injuryStages`/`S.pgInjuryStages` hold the
  {injury_name: stage} map for the Train wizard and Program Builder
  respectively (two independent instances, same pattern `S.injuries`/
  `S.pgInjuries` already use); `generate.js`/`program-wizard-steps.js` now
  send `injury_stages` on `generate-workout`/`generate-program`; both
  in-session and in-program swap panels (`workout-swap.js`) now pass
  `injury_stages` through to `GET .../injury-swap` too, via a new
  `flattenInjuryStages` helper matching that endpoint's `name:stage,...`
  query-string shape; review screens show the stage label next to each
  flagged injury via a new `formatInjuryWithStage` helper.
  - Verified against the real installed stack (not stubs): a severity-1
    injury (`Wrist Loose Bodies`) run with no stage excluded 73 exercises;
    the same request with `injury_stages: {..: 'early_recovery'}` excluded
    76 (the stage genuinely tightens the ceiling further); with
    `'return_to_performance'` it excluded 73, matching the unrestricted
    baseline - confirms `injury_joint_stage` was already wired correctly on
    the engine side and the only gap was the frontend never sending it.
- **Real bug found and fixed - `adaptive_training_load` (Phase 19) was
  computed then discarded for every generated program day.**
  `generate_session`'s response has carried `adaptive_training_load`
  (multipliers, `auto_deload_recommended`, `sessions_considered`, a
  plain-English `reasons` list) since Phase 19, explicitly documented as
  "same transparency contract as `personalization_applied`/
  `history_signals`" - but `program_builder.py`'s per-day loop only ever
  copied `prescribed_workout`/`session_structure`/`deload_mode` out of each
  day's `session_result` into the response; `adaptive_training_load` was
  computed correctly (and did affect that day's `deload_mode`/intensity)
  but never survived into the API response, so there was nothing for a
  program view to show even in principle. Separately, even where the field
  *did* reach the frontend (single-session `generate-workout`), nothing in
  `frontend/web/js/*.js` ever read it - a user's readiness slider input
  could be silently overridden by server-side RPE-trend/volume-spike/
  missed-session-gap/plateau logic with zero visible explanation, even
  though the `reasons` list built for exactly that purpose was sitting
  right there in the response. Fixed: `day_results.append(...)` in
  `program_builder.py` now forwards `session_result["adaptive_training_
  load"]`; a new `renderAdaptiveLoadNote()` in `exercise-editing.js` renders
  the `reasons` list (and flags `auto_deload_recommended` distinctly) and is
  now called from both the single-session results view and the per-day
  program view (`program-wizard-steps.js`'s `renderProgramDay`). A no-op
  response (`active: false` - anonymous caller, or too little logged
  history) renders nothing, same as before this existed.
  - Verified: `day.adaptive_training_load` now present with the correct
    `{active, volume_multiplier, intensity_multiplier,
    auto_deload_recommended, sessions_considered, reasons}` shape on a real
    `generate_program` call against the installed stack.
- **Not a bug, left as-is, flagged for a future pass**: the frontend also
  runs its own, independent client-side adaptive-load system
  (`autoregulation.js`'s `autoregulateNextWeek`/`checkSignalDeload`), which
  duplicates (with hand-rolled, not-quite-matching magnitudes - e.g. a flat
  `-15` percentage-point deload cut vs. `_prescribe_volume_core`'s
  continuous `readiness_factor`-driven curve) logic the server now computes
  and (as of this pass) actually surfaces via `adaptive_training_load`.
  Between this pass's fix and `program_builder.py`'s own fixed calendar
  deload week, there are four independent "should this be lighter"
  computations in the codebase that don't reconcile with each other. Real
  gap, not touched here - reconciling or removing `autoregulation.js`'s
  duplicate math is a bigger design decision (which signal should own
  in-progress-program adjustments) than this pass's scope of "wire up what
  already exists and stop dropping data."
- Full existing suite still green against the real installed stack:
  **153/153 passing** (`pytest tests/ -q`, ~109s), run after both fixes
  above, not just `py_compile`.

## Latest pass — Frontend error-envelope mismatch fix (v5.16)

No new backend gaps found this pass. What this pass actually did: instead of
another `py_compile`-only pass, built minimal stand-in `fastapi`/`sqlalchemy`/
`pydantic`/`pydantic_settings` modules (stdlib-only, no network needed) so
real application code - not just its syntax - could actually run in this
sandbox. With those stubs: rebuilt the real knowledge graph from
`data/exercises.json` and ran `explain_exercise` on all 769 exercises,
ran sport-transfer scoring + programming-role classification across every
exercise x all 15 sports, ran `ProgressionEngine.generate_session` across
2,400 sport/level/equipment/injury/manual_only combinations plus all 381
individual `INJURY_TAXONOMY` tags one at a time, ran `program_builder.
generate_program` across 600 randomized sport/goal/level/days/weeks/phase
combinations, and exercised the `ReadinessInputs`/`UserBiometrics`/
`ProgressionOverride`/empty-equipment paths - zero exceptions anywhere.
Data-integrity checks (`tests/test_exercise_data_integrity.py`'s logic,
run by hand since real `pytest` still isn't installable here) all pass too.

- **Real bug found and fixed**: `frontend/web/index.html` read
  `res.data.detail` / `data.detail` / `res.body.detail` to extract error
  messages on 4 failed-request paths (login/register, generate-program,
  generate-workout, and the in-program day-rebuild flow). That was the
  right key when this API used FastAPI's raw `HTTPException` everywhere,
  but Phase 10's error-handling pass (and the auth pass before it)
  moved almost every failure path onto the `ForgeError` hierarchy, which
  responds with `{"error": {"code", "message", "request_id"}}` instead -
  confirmed in `backend/core/exceptions.py`'s `_error_envelope`/
  `_forge_error_handler`. Concretely, this meant a duplicate-email
  registration or a wrong password showed a hardcoded generic
  "Something went wrong." instead of the actual, specifically-written
  message ("An account with this email already exists.", "Incorrect
  email or password.") - the message the backend went out of its way to
  produce never reached the user. New `extractErrorMessage(data,
  fallbackMsg)` helper (added right after `API_BASE`) checks
  `data.error.message` first, falls back to `data.detail` (still the
  real shape for raw pydantic 422s and `program_builder.py`'s one
  deliberately-unmigrated `HTTPException` for an unknown split id - see
  the v5.14 entry below for why that one call site stays as-is), then
  the caller's own fallback string. All 4 call sites now use it.
  - Verified: extracted both `<script>` blocks from `index.html` and
    ran `node --check` on each before and after the edit - clean both
    times. Confirmed by reading `backend/api/routes.py` +
    `backend/services/auth_service.py` that `/auth/register` (via
    `ConflictError`) and `/auth/login` (via `UnauthorizedError`) are
    exactly the two routes most likely to surface this to a real user
    on the very first thing they do with the app.
  - Not done: no live browser/server to click through the actual login
    modal and see the corrected message render - same standing
    no-network/no-`uvicorn` gap as every pass below.
- Re-confirmed (not re-litigated) the Phase 16 IDOR pattern: every
  `athlete_id`-resolving route still follows `str(current_user.id) if
  current_user else "default"` (or the required-auth equivalent where
  `Depends(get_current_user)`, not `_optional`, already guarantees a
  non-`None` user) - no new gap, Phase 16 stays "partial."
- **Not done in this pass**: the standing `pip install` + real
  `uvicorn`/`pytest` smoke test gap is still open (no PyPI access in
  this sandbox, confirmed fresh) - everything above is real logic
  execution against the actual data/module code via stubs, not a
  substitute for booting the real stack once.

## Latest pass — Program-level AI hook, plateau-progression naming, and error-handling completion (v5.14)

Three follow-ups, each closing a gap an earlier pass's own "not done in
this pass" note had already flagged - no new gaps discovered, all three
picked directly off standing to-do items in this file.

- **Program-level AI insight hook** (closes the AI-hooks pass's "no
  program-level hook" gap): `backend/services/ai_hooks.py` gained
  `ProgramContext` (the program-level equivalent of `SessionContext` -
  goal, sport, experience level, weeks/days, split name, periodization
  model, training phase, personalization flag, under-trained muscles - all
  built from summary fields `program_builder.generate_program` already had
  computed, not re-derived) and `annotate_program` on the
  `SessionInsightProvider` protocol, `NullInsightProvider` (always `None`),
  and `AnthropicInsightProvider` (real call, identical any-failure-returns-
  `None` contract as `annotate_session` - a separate `_build_program_prompt`
  reusing the same "context data, not instructions" framing).
  `generate_program` calls it right before its `return` and only attaches
  `response["ai_insight"]` when a provider returns something - same
  byte-for-byte no-op for every deployment that hasn't set
  `AI_FEATURES_ENABLED` + a real `ANTHROPIC_API_KEY`, exactly like the
  session-level hook already worked.
  - Verified: `python -m py_compile` clean on `ai_hooks.py`/
    `program_builder.py`; the success/failure/empty-content paths and the
    prompt content (goal, split, under-trained muscles all present) were
    exercised directly against a stubbed `httpx.post` in this sandbox
    (real `httpx` isn't installed here either, same standing network gap)
    - all four cases confirmed behaving exactly like the existing
    session-level provider's own tests. New pytest cases added to
    `tests/test_ai_hooks.py` (`annotate_program` null/success/failure/
    empty-content/prompt-content, plus a `generate-program` end-to-end
    "no `ai_insight` key by default" check) for whenever the real stack is
    installable - **still needs the standing `pip install` + `pytest`
    smoke test every prior pass has flagged**.
- **Plateau note names the specific next-tier exercise** (closes the
  Recommendation-engine pass's "not done" item: a plateau note said
  "consider its next progression" without naming one, even though the
  data - the plateaued exercise's own `progressions` field, the same one
  `knowledge_graph.py` builds its progression edges from - was already
  sitting right there). New `progression_engine._name_plateau_progression`
  rewrites `recommendation_engine.PLATEAU_NOTE` (now exported as a named
  constant instead of being duplicated as an inline string) to
  `"Flat for a few sessions - consider progressing to <name>"` when the
  plateaued exercise has a resolvable `progressions[0]`, and leaves every
  other personalization note (freshness/repeat/progressing) and any
  plateau note with no resolvable progression completely untouched.
  - Verified: the id-resolution logic was run directly against the real
    731-exercise `data/exercises.json` in this sandbox - confirmed a real
    `progressions` reference resolves to its real exercise name, and an
    exercise with an empty `progressions` list correctly falls back to the
    generic phrasing. The wiring into `generate_session` (which multiplier/
    note actually reaches a response) still needs the same real
    `uvicorn`/`pytest` smoke test as everything else on this page.
- **Error-handling completion**: `auth_service.py`'s 5 remaining inline
  `HTTPException` raises (`refresh_access_token` x2, `confirm_password_
  reset` x2, `get_current_user`) - explicitly flagged as "deliberately not
  migrated" by the original Logging + error-handling pass - are now
  `ForgeError` subclasses, so every one of these now returns the same
  `{"error": {"code", "message", "request_id"}}` envelope as the rest of
  the app instead of FastAPI's bare `{"detail": ...}`. New
  `BadRequestError` (400, `code="bad_request"`) added to
  `backend/core/exceptions.py` for the two password-reset-confirm cases
  (no existing `ForgeError` subclass was a 400). `ForgeError` itself
  gained an optional `headers` field (passed through by
  `_forge_error_handler`) so `get_current_user`'s required
  `WWW-Authenticate: Bearer` header on a 401 - a real OAuth2-spec
  requirement - survives the migration instead of silently being dropped.
  `program_builder.py`'s own `HTTPException(400, ...)` (unknown split id)
  was deliberately left as-is: that module keeps a local `from fastapi
  import HTTPException` specifically so it stays importable/unit-testable
  without the full FastAPI stack wired up (see its own comment), and
  `backend/core/exceptions.py` imports `fastapi` unconditionally at module
  level - migrating that one call site would have broken the exact
  property the local-import trick exists to preserve, for a purely
  cosmetic response-shape change. `routes.py`'s two `except HTTPException:
  raise` passthroughs around that call are correspondingly still needed
  and were left alone.
  - Verified: the exception classes' pure-Python behavior (status codes,
    default/overridden `code`, `headers` defaulting to `None` and passing
    through when set) was exercised directly against stubbed `fastapi`/
    `fastapi.responses` modules in this sandbox, since real `fastapi`
    isn't installed here. New pytest cases added to
    `tests/test_error_handling.py` (garbage refresh token, garbage access
    token including the `WWW-Authenticate` header, and a bad password-
    reset-confirm token all now assert the `{"error": {...}}` envelope
    shape) for the real suite run. `python -m py_compile` clean on every
    touched file; a hand-rolled `ast`-based unused-import scan (same
    approach the Phase 15 pass used) confirmed no dead imports were left
    behind after removing `auth_service.py`'s now-unused `HTTPException`/
    `status` imports.
- **Not done in this pass**: the standing "run the real `pip install` +
  `uvicorn`/`pytest` smoke test" gap is still open - this pass's sandbox
  still has no PyPI access (`pip install -r requirements.txt` fails with
  `No matching distribution found for fastapi`, confirmed fresh in this
  session), so every check above is `py_compile` + direct logic
  verification against stubbed/real-but-dependency-free inputs, same
  caveat as literally every pass on this page. No broader Phase 16
  security audit beyond re-confirming (by reading, not by discovering
  anything new) that every `athlete_id`-resolving route in `routes.py`
  still follows the `str(current_user.id) if current_user else "default"`
  pattern the Phase 13 IDOR fix established - no new bug found, Phase 16
  stays "partial."



`backend/core/config.py` had shipped a `METADATA_CACHE_TTL_SECONDS` setting
since the Phase 3 config pass, but nothing ever actually read it — found by
grepping the codebase for its usage before starting this pass and getting
zero hits outside its own definition. Three endpoints were doing real,
avoidable recompute work on every single request against data that's only
ever a function of `data/exercises.json`/`INJURY_TAXONOMY`, both loaded once
at startup (`ProgressionEngine.load_database`) and never mutated again for
the life of the process:

- **New `backend/core/cache.py`** (stdlib-only, same in-memory/per-process
  philosophy as `rate_limit.py`): `@ttl_cache(seconds)` for values that
  *could* change if a future pass adds hot-reloading of exercises.json
  without a restart, and `@cache_forever` (`functools.lru_cache(maxsize=None)`
  under a clearer name) for values provably fixed at startup. Neither ever
  caches a raised exception — a failing call just recomputes next time, so a
  404 on an unknown id can't get baked into the cache.
- **`grouped_injury_taxonomy()`** (`backend/services/injury_taxonomy.py`):
  was re-walking the full `INJURY_TAXONOMY` dict on every call, and got
  called *twice* per metadata-browsing session (`/api/v1/metadata` calls it
  directly; `/api/v1/injuries/grouped` calls it again). Now `@cache_forever`
  at the source, so every caller benefits from one shared cache instead of
  each endpoint needing its own.
- **`/api/v1/equipment`**: `build_equipment_catalog` was re-grouping all 731
  exercises into sections on every call. Now behind `@ttl_cache(settings.
  METADATA_CACHE_TTL_SECONDS)` (30s default) via a new `_cached_equipment_
  catalog()` helper in `backend/api/routes.py`.
- **`/api/v1/knowledge-graph/{exercise_id}`**: `explain_exercise` was
  walking every in/out edge of one node (progressions, regressions,
  substitutes, joints, rehab-candidacy, sport transfer x ~13 sports, then a
  sort) on every call. Now behind `@cache_forever` via a new
  `_cached_explain_exercise(exercise_id)` helper — safe because
  `engine.knowledge_graph`/`engine.exercises_by_id` are the same two objects
  for the life of the process (unlike `engine.base_dag`, which a request's
  `custom_progressions` can deep-copy and edit per-request — see
  `progression_engine.py` — this endpoint doesn't touch that path at all).
  Bounded memory: at most one cache entry per real exercise id.
- **Deliberately left uncached**: `generate-workout`/`generate-program` and
  `/api/v1/exercises` (search) — both depend on per-request input
  (equipment/injuries/sport/search text/athlete history), so a shared cache
  either wouldn't hit or would risk serving one person's personalized/
  filtered result to another. Caching those would need a request-shaped
  cache key and TTL short enough to respect `readiness`/history changes —
  real design work, out of scope for this pass, and not what was actually
  slow (the metadata endpoints above were the ones doing pure, static
  recompute for no reason).
- **New `tests/test_cache.py`**: `ttl_cache` (returns cached value within
  the window, separate entries per distinct args, expires after the TTL,
  `cache_clear()` forces recompute, never caches a raised exception),
  `cache_forever` (never recomputes the same arg), and a real-call-site
  check that `grouped_injury_taxonomy()` returns the identical cached object
  on a second call.
- **Verified**: `python -m py_compile` clean on every touched/new file;
  `ttl_cache`/`cache_forever` exercised directly with plain Python
  (expiry, cache-clear, per-arg isolation, exception-not-cached all
  confirmed) and `grouped_injury_taxonomy()` confirmed to return the same
  object on a second call — `fastapi`/`networkx` still aren't installable in
  this sandbox (no network access), so the actual `/api/v1/equipment` and
  `/api/v1/knowledge-graph/{id}` routes weren't hit through a live server.
  **Same standing caveat as every prior pass**: run the real `uvicorn`
  smoke test before shipping, and while there, confirm a second call to
  those two endpoints is actually faster (or at least returns
  `is`-identical/equal data) and that `_cached_equipment_catalog`'s 30s TTL
  visibly expires.
- **Not done in this pass**: no cache-invalidation hook if exercises.json
  is ever hot-reloaded (a restart is currently the only way `engine`
  rebuilds, so this is a null gap today, but would need a `cache_clear()`
  call added at reload time if hot-reload ever gets built); the other real
  performance work implied by "Phase 8" title — response compression, DB
  query optimization/indexes on `session_logs` for the readiness/history
  endpoints as usage grows — wasn't touched, since nothing in the current
  codebase or test suite pointed at either being an actual bottleneck yet.

## AI-hooks pass — Phase 17 (future-AI-feature architecture hooks)

Two sub-passes, both in this section: the extension point itself, then a
real provider wired through it.

**Extension point** (see backend/services/ai_hooks.py's module docstring
for the full reasoning): `SessionContext` (a dataclass capturing exactly
what `generate_session` already has in hand right before it returns -
sport, experience level, deload/readiness state, prescribed/excluded
exercise ids, history_signals - built from existing data, nothing new
computed or fetched), a `SessionInsightProvider` Protocol (one method,
`annotate_session(context) -> dict | None`), and `NullInsightProvider` -
always returns `None`.
`ProgressionEngine.generate_session` calls the configured provider once,
right before its final `return` - `response["ai_insight"]` is only ever
added when a provider returns something non-`None`.

**Real provider — `AnthropicInsightProvider`**: calls the real Anthropic
Messages API (`https://api.anthropic.com/v1/messages`) to generate a
short (2-3 sentence) coach-style note about a session that's already been
finalized - commentary only, it cannot change which exercises got
selected. New settings in `backend/core/config.py`:
`ANTHROPIC_API_KEY` (default `None`), `AI_MODEL` (default
`"claude-sonnet-4-6"`), `AI_MAX_TOKENS` (220), `AI_TIMEOUT_SECONDS` (8.0).
`get_insight_provider()` only returns the real provider when BOTH
`AI_FEATURES_ENABLED=true` AND a real `ANTHROPIC_API_KEY` are set in
`.env` - either gap (or both) falls back to `NullInsightProvider`, so a
deployment that never touches these settings behaves identically to
before this pass, byte-for-byte.

- **Failure contract**: `annotate_session` catches every exception
  (network error, timeout, non-2xx, malformed JSON, empty content) and
  returns `None` rather than raising - verified for real: a live call
  against `https://api.anthropic.com/v1/messages` with a deliberately
  invalid key during this pass came back a genuine `401 Unauthorized`
  over the real network, was caught, logged as `ai_insight_provider_failed`,
  and `annotate_session` returned `None` exactly as designed - this
  wasn't just unit-tested, it was proven against the real API endpoint.
  A real key would need to be supplied (this environment has none) to
  verify the success path against the live API; that path is covered by
  a mocked `httpx.post` in `tests/test_ai_hooks.py` instead (response
  parsing: content blocks -> summary string).
- **Prompt-injection note, kept honest**: `WorkoutRequest.sport` is
  free-text (`schemas.py` has no enum on it, unlike `experience_level`),
  so it's the one field in the prompt with residual injection risk. The
  prompt truncates it (60 chars) and places it under a labeled "context
  data, not instructions" section with a system prompt reinforcing that
  framing - a reasonable first mitigation, not a proven one; real
  red-teaming of this is follow-up work, not done here.
- **`httpx` moved from a test-only dependency to a real one** in
  `requirements.txt` (it was already installed for the Phase 13 test
  suite; `AnthropicInsightProvider` now uses it too, so no new
  third-party dependency was actually added to the project).
- **New tests in `tests/test_ai_hooks.py`** (9 total): provider selection
  logic for all three states (features off / on-but-no-key /
  on-with-key), successful response parsing (mocked), the
  any-failure-returns-None contract (mocked), empty-content handling, the
  sport-field truncation/labeling check, and the same end-to-end
  no-`ai_insight`-key-by-default check as before. Full suite: **75/75
  pass** (69 from the earlier pass + 6 more here); `pyflakes` on every
  new/touched file is clean.
- **Not done in this pass** (real follow-up work): no program-level hook
  (`program_builder.generate_program` doesn't call this yet - only the
  single-session path does); no response caching (an identical session
  requested twice makes two API calls); no real red-teaming of the
  prompt-injection mitigation (see above); no rate limiting specific to
  this endpoint's AI cost (the existing per-IP rate limits on auth
  endpoints don't cover generate-workout at all, AI-enabled or not - a
  gap for Phase 16's security audit, not something added here).

## Logging + error-handling pass — Phases 9 & 10

Before this pass there was no logging configuration anywhere in the app —
the only signal on an unexpected failure was two hand-rolled `print(f"[gen
erate-workout] unhandled error: {e!r}")`-style calls inside
`generate_workout`/`generate_program_endpoint`, and every other error path
(404s for an unknown sport/exercise/template, a 409 on duplicate
registration, a 401 on bad login) was a bare `HTTPException(status_code=...,
detail=...)` raised inline at the call site with no consistent response
shape across endpoints and nothing logged at all.

- **New `backend/core/logging.py`** (stdlib-only, same in-memory/per-process
  philosophy as `cache.py`/`rate_limit.py` — no `structlog` or similar
  added to `requirements.txt` for this): `configure_logging()` installs one
  JSON-lines formatter on the root logger (called once, at import time, in
  `main.py`, so it's active before the app object itself is even built);
  `get_logger(name)` is the `logging.getLogger("forge." + name)` convenience
  wrapper; `RequestIDMiddleware` assigns (or reuses an inbound
  `X-Request-ID` header from) a request id per request, stores it on
  `request.state.request_id`, echoes it back as a response header on every
  response including error ones, and logs one structured
  `request_handled`/`request_failed` line per request with
  method/path/status/duration.
- **New `backend/core/exceptions.py`**: a small `ForgeError` hierarchy
  (`NotFoundError` 404, `ConflictError` 409, `UnauthorizedError` 401,
  `ValidationError` 422, `RateLimitedError` 429) plus
  `register_exception_handlers(app)`, which wires both `ForgeError` and a
  catch-all `Exception` handler to always return the same JSON envelope —
  `{"error": {"code", "message", "request_id"}}` — instead of FastAPI's
  bare `{"detail": ...}`. The catch-all handler is also where the old
  per-endpoint DEBUG-gated "full exception message only in DEBUG, generic
  message otherwise" logic now lives, centralized, so new endpoints get it
  for free instead of every route needing its own `try/except`.
- **`backend/api/routes.py` migrated**: every existing `404`/`409`/`401`
  `HTTPException` raise (unknown sport, unknown exercise id x2, unknown
  manual template x2, duplicate registration, wrong password, session not
  found) now raises the matching `ForgeError` subclass instead. The two
  `except Exception` blocks in `generate_workout`/`generate_program_
  endpoint` now log via `logger.error(..., exc_info=True)` and re-raise,
  letting the new catch-all handler build the response — no behavior
  change in status code or DEBUG-gating, just centralized.
  **Deliberately not migrated**: `HTTPException` itself is still a
  perfectly valid thing to raise (FastAPI handles it natively) and other
  parts of the codebase (e.g. `auth_service.py`'s dependency functions)
  still raise it directly — this pass touched `routes.py`'s own inline
  raises, not every `HTTPException` call site in the app. A full sweep is
  reasonable follow-up work, not required for the logging/error-handling
  goal itself.
- **`backend/main.py`**: replaced the deprecated `@app.on_event("startup")`
  hook with a `lifespan` context manager (same `init_db()` +
  insecure-`SECRET_KEY` check, now warning through the structured logger
  instead of `print()`) — this incidentally also fixes the
  `DeprecationWarning` `pytest` was emitting on every run. Registered
  `RequestIDMiddleware` and the new exception handlers.
- **New `LOG_LEVEL` setting** (`backend/core/config.py`, default `"INFO"`).
- **New `tests/test_error_handling.py`**: the `{"error": {...}}` envelope
  shape on a real 404 and 409 through the actual app, the `X-Request-ID`
  response header being present on every response (and an inbound one
  being echoed back rather than replaced), and the JSON formatter directly
  (parses as JSON, carries `extra=` fields, includes a traceback on an
  exception record).
- **Verified**: full suite (`python -m pytest tests/ -q`) — this sandbox
  *does* have `pypi.org`/`files.pythonhosted.org` network access (unlike
  every prior pass's sandbox), so `pip install -r requirements.txt` plus
  the real `fastapi`/`uvicorn`/`sqlalchemy`/`networkx` stack were actually
  installed and the full 66-test suite (60 pre-existing + 6 new) was run
  for real, not just `py_compile`'d — **this closes the standing
  "Verification caveat" gap this doc has flagged since the Phase 2 pass**:
  all 66 tests pass. `pyflakes` run against the two new modules plus every
  file this pass touched came back clean (see Phase 15's row above for
  what a full-codebase run still flags, all pre-existing and untouched by
  this pass).
- **Not done in this pass**: shipping these JSON log lines anywhere off-box
  (log aggregation is an infra/deployment choice, not a code gap); log
  *sampling* under high request volume; migrating `HTTPException` raises
  outside `routes.py` (see above); a `RateLimitedError`/`ValidationError`
  call site doesn't exist yet in the app today — both classes exist in
  `exceptions.py` ready for the next endpoint that needs them, but nothing
  currently raises them (rate limiting today still returns its own
  response shape via `backend/core/rate_limit.py` — unifying that with
  `RateLimitedError` is reasonable follow-up work, not done here to avoid
  touching the rate-limiter's own tested behavior in the same pass as
  everything else above).

## Recommendation-engine pass — Phase 5 (scored recommendation engine)

`_apply_profile_defaults` (Phase 6) already prefilled sport/equipment/
injuries for a returning person, but its own docstring flagged that this
was "light-touch personalization, not the full scored-recommendation
engine (roadmap Phase 5)". This pass is that first real pass: real logged
history (the weight x reps sets a person actually logged - `session_logs.
log_json`, written by the frontend's `syncSessionToBackend`/`logSet`) now
feeds back into how the engine *ranks* exercises for that same person's
next session, on top of everything `sport_priority_score` already
computed (sport transfer, movement emphasis, level fit, equipment
priority, hypertrophy bias).

- **New `backend/services/recommendation_engine.py`**: `build_history_signals(db,
  athlete_id, sport)` does one pass over an athlete's last 30 logged
  sessions and returns a per-exercise-id signal (`times_logged`,
  `days_since` last logged, `sessions_since_last`, and a `trend` of
  `"progressing"`/`"plateau"`/`None` from an Epley-style estimated-1RM
  read on the last 3 times it was logged - same formula shape as the
  frontend's own client-side PR detection, `computeScore()`, so the two
  never disagree). `personalization_multiplier(exercise_id, signals)`
  turns one exercise's signal into a small (+-15%) ranking nudge plus a
  plain-language note: a freshness boost for something not logged in 21+
  days, a small variety penalty for something logged in the last session
  or two, a boost for something with a rising trend, a penalty (nudging
  toward its DAG progression/variant instead) for something that's been
  flat for 3+ logged sessions. Deliberately the same "explainable
  heuristic, not a trained model" spirit as `readiness_service.
  compute_suggested_readiness` - every number can be justified in one
  sentence. Gated behind `MIN_SESSIONS_FOR_SIGNAL = 3` logged sessions
  with real set data - below that, `build_history_signals` returns `{}`
  and every multiplier is a no-op (`1.0`, no note), so a new or casual
  account sees zero behavior change.
- **`ProgressionEngine.generate_session`** takes optional `athlete_id`/`db`
  params (both `None` by default - a no-op, identical scoring to before
  this pass for every existing caller that doesn't pass them). When both
  are supplied and there's enough history, each qualifying exercise's
  `sport_priority_score` gets the personalization multiplier folded in
  alongside the existing multipliers, and a `personalization_note` field
  is attached to the exercise when there's something worth telling the
  person (e.g. "Numbers trending up here recently - stays in rotation").
  The response's top level now also carries `personalization_applied`
  (bool) so a caller/UI can tell whether this particular response was
  actually personalized or not.
- **`program_builder.generate_program`** takes the same optional
  `athlete_id`/`db` and threads them into every day's `generate_session`
  call across the mesocycle; the program response's own
  `personalization_applied` is true if any day's session got the nudge.
- **`backend/api/routes.py`**: `generate-workout` and `generate-program`
  now take a `db` dependency and resolve `athlete_id = str(current_user.id)`
  for a logged-in caller (`None` for anonymous, same as everywhere else
  athlete_id is resolved from the JWT) and pass both straight through -
  anonymous requests are completely unaffected. New
  `GET /api/v1/recommendations/history` (requires login - this is
  personal history, unlike the sport/equipment/injury metadata every
  other `GET` here returns for anyone) exposes the raw per-exercise
  signals directly, for a frontend "your training patterns" view that
  doesn't need to generate a fresh session just to see them.
- **Not done in this pass** (real work for a follow-up, same spirit as the
  Auth pass's own "not done" list): the multiplier only reacts to logged
  weight x reps trend and staleness - it doesn't yet account for RPE,
  doesn't cross-reference `progression_roadmap`/DAG progressions to
  proactively suggest the *specific* next-tier exercise on a plateau (the
  note just says "consider its next progression"; the actual progression
  id is already sitting in `knowledge_graph.py`/`base_dag` and is the
  natural next wire-up), and the web UI has no surface for
  `personalization_note` or the new `/recommendations/history` endpoint
  yet. **Verification caveat**: `recommendation_engine.py`'s own logic
  (`build_history_signals`, `personalization_multiplier`, the
  Epley-estimate helper) was unit-tested directly against hand-built fake
  rows/query objects (same "minimal stand-ins" approach every pass since
  Phase 2 has used, since `fastapi`/`sqlalchemy` still aren't installable
  in this network-restricted sandbox) - confirmed: 3-session progressing
  trend correctly boosts, a flat trend correctly penalizes, an
  under-threshold history correctly no-ops, and an exercise with zero
  logged history correctly returns `(1.0, None)`. The wiring into
  `generate_session`/`generate_program`/routes was verified with
  `python -m py_compile` on every touched file only - **still needs the
  same real `uvicorn` smoke test every prior pass has flagged**, now
  additionally exercising: log a few sessions as a real account, call
  `generate-workout` again, and confirm `personalization_applied` flips
  to `true` and a plateaued/progressing exercise's `personalization_note`
  actually shows up.

## Latest pass — Exercise library: equipment depth cleanup (v5.9, batch8)

- `scripts/generate_batch8_equipment_depth.py` + `scripts/enrich_batch8_only.py`
  (+ one follow-up entry appended directly): 558 -> 659 exercises (+101).
  Closes the exact gap batch7 flagged as "not done in this pass" below —
  querying the live file found 50 equipment types still sitting at only 3
  or 4 exercises (mostly single-purpose machines, specialty bars, strongman
  implements, and conditioning tools that batch6's general-machine pass and
  batch7's 1-2-count pass didn't reach: Wrestling Dummy, Sled, Atlas Stone,
  Log Bar, Safety Squat Bar, Hack/Leg Extension/Pec Deck/V Squat/Pendulum
  Squat/Chest Press/Shoulder Press/High Row/Belt Squat/Leg Curl/Plate-Loaded
  Lever Machines, Buffalo/Cambered/Swiss/Axle/EZ Curl/Trap Bar, Captain's
  Chair, Ab Wheel, Suspension Trainer, Weighted Vest, Yoke, Agility Ladder,
  Boxing Heavy Bag, Squat Rack, Belt Squat, Hyperextension Bench, Tire,
  Conan's Wheel, Fingal's Fingers, Husafell Stone, Neck Harness, Farmer
  Handles, Assault Bike, Climbing Hangboard, Parallel Bars, GHD, Jump Rope,
  Reverse Hyper, Seal Row Bench, Keg, Battle Ropes, Rowing Erg, Tackle Bag,
  Balance Board). Every one of the 49 that started at 3-4 got +2 (matching
  the exact per-equipment pattern batch6/7 used); Balance Board started at
  only 2 (from batch7's rehab addition) so it got +3 to reach the same
  floor as everything else. **Every equipment type in the database now has
  at least 5 exercises — none left under 5.**
  - Verified: field-parity check (all 659 exercises share one identical key
    set, no missing/extra fields on the new entries), zero dangling
    progression/regression/alternative id references, zero duplicate ids,
    `python -m py_compile` clean on both new scripts. Same sandbox
    limitation as batch7 — `fastapi`/`pydantic`/`networkx` aren't
    installable here, so `enrich_exercise` was re-run standalone against
    the real file rather than through a live server; **still needs the
    same real `uvicorn` smoke test every prior pass has flagged**.
  - **Not done in this pass**: no equipment-depth gap left to flag — this
    was the last of the three-batch series (6, 7, 8) that started with 14
    thin machines, then 27 near-empty types + the rehab gap, then these
    final 50. Future depth work would be about breadth *within* an
    equipment type (e.g. Barbell's 121 vs. a newly-5-deep type like Neck
    Harness) rather than a missing-equipment gap.

## Latest pass (previous) — Exercise library: equipment depth + neck/ankle rehab (v5.8, batch7)

- `scripts/generate_batch7_equipment_rehab.py` + `scripts/enrich_batch7_only.py`:
  492 -> 558 exercises (+66). Two gaps, both found by inspecting the live data
  rather than guessed at:
  1. **Equipment depth** — 15 equipment types sat at exactly 1 exercise and 12
     at exactly 2 (Battle Ropes, Rowing Erg, Tackle Bag, Captain's Chair, Ab
     Wheel, Yoke, Agility Ladder, Buffalo Bar, Tire, Conan's Wheel, Fingal's
     Fingers, Husafell Stone, V Squat/Pendulum Squat/Belt Squat Machines,
     Assault Bike, Trap Bar, Climbing Hangboard, Parallel Bars, EZ Curl Bar,
     Jump Rope, Reverse Hyper, Seal Row Bench, Cambered Bar, Swiss Bar, Keg,
     Plate-Loaded Lever Machine). Every one of those got +2, so picking that
     equipment in the app now unlocks a real session instead of 1-2 repeats.
  2. **Rehab gap** — querying `is_rehab_candidate()` (`knowledge_graph.py`)
     against the pre-batch7 file: every joint had rehab-candidate exercises
     except **Neck, which had zero at any severity** (no exercise trained
     Neck stability at a low enough difficulty to qualify, even though
     `injury_taxonomy.py` has full Neck injury entries), and Ankle had only 6
     next to Shoulder/Hip/Knee's 50+. Added 6 difficulty=2 Neck-stability and
     6 difficulty=2 Ankle-stability exercises (difficulty=2 is the ceiling
     `is_rehab_candidate()` enforces; `30 + difficulty*8 = 46` clears the
     40-point stability-quality floor). Neck: 0 -> 6 rehab candidates. Ankle:
     6 -> 15. Two new equipment types (Neck Harness, Balance Board) and a new
     "Rehab & Mobility" `EQUIPMENT_CATEGORIES` group in
     `exercise_metadata.py` came with that, so they show up correctly grouped
     in `/api/v1/equipment` instead of falling into "Other".
  - Verified: field-parity check (new exercises have exactly the same key set
    as pre-existing ones, nothing missing/extra), zero dangling
    progression/regression/alternative id references, zero duplicate ids,
    `python -m py_compile` clean on every touched file. `fastapi`/`pydantic`/
    `networkx` still aren't installable in this sandbox, so `is_rehab_candidate`
    and `enrich_exercise` were re-run standalone against the real file (not
    through a live server) to confirm the before/after counts above — **still
    needs the same real `uvicorn` smoke test every prior pass has flagged**,
    plus a check that `/api/v1/equipment` renders the new "Rehab & Mobility"
    group and that `/api/v1/knowledge-graph/{id}` returns `rehab_candidate_for`
    edges for a couple of the new neck/ankle exercise ids.
  - **Not done in this pass**: equipment types still under 4 exercises after
    this batch (mostly narrow/specialty gear like Wrestling Dummy, Sled,
    Atlas Stone, Log Bar, Safety Squat Bar — 2-3 each) — a smaller follow-up
    batch, not urgent since those are inherently niche equipment. Severity-3
    (clinician-directed) rehab candidates are intentionally still 0 for every
    joint — by design, per `injury_taxonomy.py`'s "no loading until cleared"
    rule, not a gap.

## Latest pass — Program Builder integration

- `backend/models/schemas.py` added: `WorkoutRequest`/`ProgramRequest`/etc. pulled
  out of `main.py` (finishes the schema half of Phase 2), plus two new
  `WorkoutRequest` fields (`target_categories`, `target_muscles`, `exercise_limit`)
  and the new `ProgramRequest` model.
- `backend/services/program_builder.py` added: turns a goal + split + days/week +
  weeks into a full multi-week program by calling `ProgressionEngine.generate_session`
  once per (week, day) — reuses all existing equipment/injury/strength/level
  filtering rather than duplicating it. 8 split templates (Full Body, Upper/Lower,
  PPL, Bro Split, Arnold, PHUL, PHAT, Powerbuilding); the spec's other named splits
  (Beginner/Intermediate/Advanced, Home/Dumbbell-only, Bodybuilding/Powerlifting/
  Hybrid) map onto existing `experience_level`/`equipment_available`/`primary_goal`
  parameters instead of being separate templates.
- Three new endpoints on `backend/main.py`: `POST /api/v1/generate-program`,
  `GET /api/v1/splits`, `GET /api/v1/goals`.
- Verified end-to-end against the real `data/exercises.json` (175 exercises):
  every split template generates correctly at every days-per-week it supports,
  auto-split-selection (`preferred_split: "auto"`) picks sensibly, week-over-week
  progressive overload and the auto-appended deload week (3+ week programs) both
  behave as designed, and an unknown split id returns a clean 400. (`fastapi`/
  `pydantic` weren't installable in the verification sandbox — network-restricted —
  so this was checked by calling the route functions and engine directly against
  minimal stand-ins for `BaseModel`/`HTTPException`, not a live HTTP server. Worth
  a real `uvicorn` smoke test before shipping.)
- **Follow-up pass**: `frontend/web/index.html` now has a "Program" nav tab —
  a form (goal, sport, experience, split, days/week, weeks, session duration,
  readiness, equipment; injuries are reused from whatever's set in the
  assessment wizard) that POSTs to `/api/v1/generate-program` and renders the
  result as week tabs over day-by-day exercise cards (reusing the existing
  prescription/pill/exercise-modal rendering helpers, so it's visually
  consistent with the single-session results screen). Not yet done: a
  `save program to history` action (today it's view-only per generation).
  The old Streamlit frontend (`frontend/app.py`) has been removed —
  `frontend/web/index.html` is now the only frontend, so there's no second
  UI to keep in sync with new endpoints going forward.

## Full account-sync pass — first live verification + custom workouts/programs (v5.24)

Two things in one pass, done together because the first is what made the
second trustworthy to build on.

- **The Phase-6 auth pass and its critical-gap follow-up had never actually
  been run.** Every prior verification was `python -m py_compile`/`ast.parse`
  only — the sandbox that built them had no PyPI access, a caveat repeated
  in every pass since Phase 2 and never discharged. This pass had real
  network access, so: `pip install -r requirements.txt` (clean install),
  full `tests/` suite (177/178 passing pre-existing — the one failure,
  `test_generate_program_does_not_repeat_the_same_movement_family_all_week`,
  is an unrelated program-variety bug, not auth), then a live
  `uvicorn backend.main:app` smoke test exercising the real flow end to
  end: register → `/auth/me` → log a session (confirmed `athlete_id`
  resolves to the caller's own account, and an anonymous request can't
  spoof one into it) → refresh (rotates; the old refresh token is rejected
  immediately after) → logout (revokes; reuse afterward is rejected) →
  password-reset request (confirmed it logs a token server-side, no email
  provider wired up, exactly as documented). Everything behaved as
  designed on a real running server for the first time.
- **Closed the one real gap this surfaced**: Custom Mode workouts and
  generated programs were still localStorage-only even after accounts
  shipped — `docs/ROADMAP.md`'s own Auth-pass notes never claimed
  otherwise, but it meant "server-side sync" wasn't actually complete.
  Added `CustomWorkoutDB`/`SavedProgramDB` (`backend/models/db_models.py`),
  a matching repository/service/route layer (`backend/repositories/
  custom_workout_repository.py`, `saved_program_repository.py`,
  `backend/services/sync_service.py`, six new endpoints under
  `/api/v1/custom-workouts` and `/api/v1/programs` in `backend/api/
  routes.py`), and migration `m0002_custom_workouts_and_saved_programs.py`.
  Same athlete_id-resolution/IDOR protection as the existing session-log
  routes, plus upsert-on-(athlete_id, client_id) so re-saving from any
  device updates the same row instead of duplicating.
- **Frontend wiring**: `custom-workout-builder.js`'s save/duplicate/delete
  now sync to the backend in the background when logged in (localStorage
  write always happens first and stays the offline fallback, sync is
  fire-and-forget — same pattern `history.js` already used for session
  logs), and opening Custom Mode now pulls + merges any workouts saved
  from another device. `program-wizard-steps.js` gained a "Save Program"/
  "Update Saved" button on the results toolbar and a "My Saved Programs"
  list (load/delete) on the Program Builder's first step, both gated
  behind login (a generated program is already fully reproducible from
  its own request payload, so unlike custom workouts there's no anonymous-
  localStorage tier for this — saving only means something once there's
  an account to keep it on).
- **Verified**: `tests/test_sync_endpoints.py` (new, 8 tests — anonymous
  default-bucket use, upsert-not-duplicate on repeated saves, account
  scoping/IDOR checks for both tables) plus a live smoke test identical in
  spirit to the auth one above (save → save again same client_id → list →
  delete → confirm anonymous/other accounts can't see it), all against
  the real running server. Full suite: 185/186 (same one pre-existing
  unrelated failure noted above). All touched/new JS files also pass
  `node -c` syntax checking.
- **Still open**: no email provider for password reset (unchanged from
  the Auth pass); `SECRET_KEY`/rate-limiting are still dev-only defaults
  that need real config before shipping; the login gate is still switched
  off in `boot.js` (a product decision, not a bug — accounts work whether
  or not they're required).

## Auth pass — Phase 6 (persistent user profiles)

Adds real accounts on top of the existing `session_logs` table, aimed at the
"commercial app, more than one person will use this" requirement:

- **`UserDB`** (`backend/models/db_models.py`): email/password account with
  profile fields (`primary_sport`, `experience_level`, `equipment_json`,
  `injuries_json`). `session_logs.athlete_id` was already a free-text string
  defaulting to `"default"` (multi-athlete-shaped from the start per its own
  docstring) — an authenticated request now sends `str(user.id)` there
  instead; anonymous use is untouched.
- **`backend/core/security.py`**: password hashing (PBKDF2-HMAC-SHA256,
  stdlib `hashlib` — not bcrypt/passlib, since neither is in
  `requirements.txt` or installed in the dev sandbox this was built in) and
  JWT access tokens (PyJWT, now pinned in `requirements.txt`). Hashing and
  token create/verify/expiry were unit-tested standalone (stdlib +
  PyJWT only, no FastAPI/SQLAlchemy needed) — correct positive/negative
  cases confirmed (right password, wrong password, malformed stored hash,
  expired token, wrong signing key).
- **`backend/services/auth_service.py`**: register/authenticate/update-profile,
  plus two FastAPI dependencies — `get_current_user` (401s without a valid
  token; profile read/update) and `get_current_user_optional` (returns
  `None` instead of raising; every session/readiness/generate-* route uses
  this so anonymous callers keep working exactly as before).
- **New endpoints**: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`,
  `GET /api/v1/auth/me`, `PUT /api/v1/auth/me`.
- **Session/readiness endpoints now account-aware**: `/api/v1/sessions`
  (POST/GET/DELETE) and `/api/v1/readiness/suggested` resolve `athlete_id`
  from the caller's token when present, ignoring/overriding any `athlete_id`
  sent in the request — a logged-in person can no longer read or delete
  another `athlete_id`'s history by passing a different value.
- **`generate-workout`/`generate-program` now personalize automatically**:
  `_apply_profile_defaults()` (`backend/main.py`) fills `sport`,
  `experience_level`, `equipment_available`, `injuries` from the caller's
  saved profile — but only for fields the request body didn't explicitly
  set (checked via Pydantic's `model_fields_set`), so an explicit request
  value always wins. This is deliberately light-touch, not the full Phase 5
  scored-recommendation engine — it just saves a returning person from
  re-entering their sport/equipment/injuries every time.
- **`SECRET_KEY`** (`backend/core/config.py`): new setting, JWTs are signed
  with it. Ships with an insecure dev-only default and a loud startup-log
  warning if it's still set when the app boots — **must** be overridden via
  `.env` before this is exposed to real users, or every login token is
  forgeable.
- **Not done in this pass** (real work for a follow-up): the web frontend
  (`frontend/web/index.html`) has no signup/login UI yet — it still POSTs to
  `generate-workout`/`sessions`/etc. with no Authorization header, so it
  keeps working anonymously (`athlete_id="default"`) exactly as before, but
  nobody can actually create an account through the UI yet. Also not done:
  password-reset flow, email verification, rate-limiting login attempts,
  refresh tokens (access tokens just expire after
  `ACCESS_TOKEN_EXPIRE_MINUTES` and require a fresh login), and the real
  Phase 5 scored-recommendation engine (this pass's `_apply_profile_defaults`
  is a prefill, not a ranking/scoring model).
- **Verification**: every touched/new file passes `python -m py_compile`;
  the password-hashing and JWT logic were exercised directly with stdlib +
  PyJWT (both installed) since `fastapi`/`pydantic`/`sqlalchemy` aren't
  installable in this sandbox (no network access) — **run a real
  `pip install -r requirements.txt` + `uvicorn` smoke test before shipping**,
  same caveat the Program Builder pass above already flagged.

## Phase 2 — modularization pass (finished)

`backend/main.py` (1697 lines) bundled the `ProgressionEngine` class, every
API route, and app setup in one file. Split into:

- `backend/services/progression_engine.py` — the `ProgressionEngine` class,
  `level_fit_multiplier`/`level_fit_label`, `EXPERIENCE_LEVELS`/`LEVEL_RANK`,
  and the module-level `engine = ProgressionEngine()` singleton every route
  already depended on.
- `backend/api/routes.py` — every endpoint as an `APIRouter` (same paths,
  same params, same bodies — only `@app.get/post/put/delete` became
  `@router.*`), plus the route-only helpers `_apply_profile_defaults` and
  `_resolve_manual_exercise`.
- `backend/main.py` — now ~60 lines: `FastAPI()` + CORS + the startup hook
  (`init_db()` and the `SECRET_KEY` warning) + `app.include_router(router)`.

No behavior, endpoint path, or business logic changed — purely mechanical
(each block moved verbatim, imports resolved). Verified with
`python -m py_compile` on all three files, then a full `import backend.main`
against minimal stand-in `fastapi`/`pydantic`/`pydantic-settings`/
`sqlalchemy` modules (still no network access in this sandbox to `pip
install` the real ones) — this executes every decorator and default-arg
`Depends(...)` at import time, so it does catch missing-import/NameError
regressions from the split. Confirmed: all 25 routes register with their
original paths, and the real `ProgressionEngine` loads the actual
`data/exercises.json` (447 exercises, 13 sports) without error. **Still
worth a real `pip install -r requirements.txt` + `uvicorn backend.main:app`
smoke test before shipping** — the stand-ins prove the wiring, not that
`fastapi`'s actual `Depends`/`APIRouter` behave identically to the stubs.

## Critical-gap pass (post-review)

A review of the whole codebase flagged 4 critical gaps before this could
carry real users. Three fixed in this pass, one still genuinely open:

- **Rate limiting** — added (`backend/core/rate_limit.py`, in-memory,
  stdlib-only) to `/auth/register`, `/auth/login`,
  `/auth/password-reset/request`. Documented single-process limitation.
- **`SECRET_KEY` dev-default** — was a warning-only startup check; now hard
  -fails at startup if `ENVIRONMENT=production` and the key is still the
  default (`backend/main.py`).
- **Refresh tokens / password reset** — added. `RefreshTokenDB` +
  `PasswordResetTokenDB` (`backend/models/db_models.py`), opaque-token
  helpers (`backend/core/security.py`), issue/rotate/revoke logic
  (`backend/services/auth_service.py`), 6 new/changed endpoints
  (`backend/api/routes.py`). Access token shortened 7 days → 30 minutes now
  that a refresh token exists to renew it. Email verification was scoped
  out of this pass — no email-sending infra exists anywhere in this repo,
  so it needs a provider decision (SES/SendGrid/etc.) before it can do
  anything real; password reset has the same gap today (token is logged
  server-side, not emailed) until that provider is wired in.
- **Real end-to-end smoke test — still NOT done.** The sandbox this pass
  was built in has no network access, so `pip install -r requirements.txt`
  fails outright (confirmed: `ERROR: No matching distribution found for
  fastapi`). Every verification in this pass was `python -m py_compile` +
  `ast.parse` on the touched files only — this catches syntax errors, not
  runtime wiring bugs (wrong `Depends()` signature, a SQLAlchemy column
  type FastAPI's response model can't serialize, etc.). **Before shipping
  anything from this pass**: `pip install -r requirements.txt`, run
  `uvicorn backend.main:app --reload`, and actually exercise
  register → login → refresh → logout and password-reset request → confirm
  against a live server. This caveat has been repeated in every pass since
  Phase 2 and has never actually been discharged — it should be the very
  next thing done, before any further feature work.

## Exercise-library pass — thin equipment types (v5.7)

Not one of the 17 phases, but requested directly: expand `data/exercises.json`
per-equipment, prioritizing the equipment types that were thinnest relative
to how common they are in a real commercial gym (general-public users, not
just the manual's combat-sport athletes).

- **`scripts/generate_batch6_thin_equipment.py`** (new, follows the exact
  batch2/3 pattern): +45 hand-tagged exercises across 14 equipment types —
  Cable Machine (3→11), Lat Pulldown (3→6), Leg Press (2→5), Leg Curl (2→4),
  Leg Extension (1→3), Seated Row (2→5), Chest Press Machine (1→3), Shoulder
  Press Machine (1→3), Pec Deck (1→3), Smith Machine (3→7), Hack Squat
  Machine (1→3), High Row Machine (1→3), Resistance Band (6→12), Medicine
  Ball (4→8). `injuries_to_avoid` values were checked against the 28-string
  vocabulary already in use elsewhere in the file and aligned to it (e.g.
  "Jumper's Knee (Patellar Tendinopathy)", "Tennis Elbow", "Wrist Pain",
  "Achilles") rather than introducing new ad-hoc strings.
- **`scripts/enrich_batch6_only.py`** (new) — enriches only the 45 new ids
  instead of re-running the general `enrich_exercises.py` over the whole
  file. That was a deliberate deviation from every prior batch's stated
  "then run enrich_exercises.py" instruction, found during verification of
  this pass: `enrich_exercises.py` unconditionally resets `version` back to
  `"4.0.0"` and overwrites `schema_notes`, discarding the accumulated v4.0-
  v5.6 history — and re-running its derivation over already-enriched
  exercises is not perfectly idempotent (confirmed: at least one pre-
  existing exercise's `Shoulder Stability` score drifted 40→46 on a second
  pass with no input change). **This same risk applies to every future
  batch script's "then run enrich_exercises.py" instruction** —
  `enrich_batch6_only.py`'s id-scoped-enrich + version-bump-and-append
  pattern should be copied for future batches instead, or
  `enrich_exercises.py` itself should be fixed to bump forward and append
  rather than overwrite (not done in this pass — out of scope for an
  exercise-library addition, flagged here for whoever picks it up).
- **Verified**: all 447 pre-existing exercises byte-identical before/after
  (diffed old vs. new by id); all 45 new exercises carry every v4+ field
  (`movement_plane` through `athletic_qualities`); zero duplicate ids across
  the full 492-exercise file; new exercises' `progressions`/`regressions`/
  `alternatives` are empty (no dangling DAG references introduced).

## Exercise-library pass — equipment-depth round 2 (v5.10)

Direct follow-up to the v5.9 pass above, requested as "increase the exercise
database." Queried the live file first: v5.9 brought every equipment type
to a floor of 5 exercises, but left 36 types sitting exactly at that floor
(isolation machines, strongman implements, combat/conditioning tools) while
general-purpose equipment (Barbell 121, Dumbbell 37, Kettlebell 37,
Bodyweight 46, Cable Machine 11, Resistance Band 16, Power Rack 19,
Pull-up Bar 26, Rings 27) already had real depth.

- **`scripts/generate_batch9_equipment_depth2.py`** (new, follows the exact
  batch6/7/8 pattern): +72 hand-tagged exercises, +2 for each of those 36
  equipment types (Ab Wheel, Agility Ladder, Atlas Stone, Balance Board,
  Battle Ropes, Belt Squat, Belt Squat Machine, Boxing Heavy Bag, Buffalo
  Bar, Captain's Chair, Chest Press Machine, Conan's Wheel, Fingal's
  Fingers, Hack Squat Machine, High Row Machine, Husafell Stone,
  Hyperextension Bench, Leg Extension Machine, Leg Press Machine, Log Bar,
  Neck Harness, Pec Deck Machine, Pendulum Squat Machine, Rowing Erg,
  Safety Squat Bar, Seated Row Machine, Shoulder Press Machine, Sled,
  Squat Rack, Suspension Trainer, Tackle Bag, Tire, V Squat Machine,
  Weighted Vest, Wrestling Dummy, Yoke — each 5→7). New movement names were
  checked against every existing exercise for that equipment so nothing
  duplicates what's already in the file; `injuries_to_avoid` and muscle
  names reused the vocabulary already established in exercises.json (no new
  strings introduced).
- **`scripts/enrich_batch9_only.py`** (new) — enriches only the 72 new ids,
  same reasoning as enrich_batch6/7/8_only.py: `enrich_exercises.py`
  resets `version`/`schema_notes` wholesale, so batch scripts bump forward
  and append instead.
- **Verified**: all 659 pre-existing exercises byte-identical before/after
  (diffed old vs. new by id); zero duplicate ids across the full
  731-exercise file; no equipment type in the database is under 5
  exercises (min is now 6, the next-lowest tier untouched by this pass);
  all 72 new exercises carry every v4+ field
  (`movement_plane` through `athletic_qualities`); `python -m py_compile`
  clean on both new scripts.
- **Not done**: same real end-to-end `pip install` + `uvicorn` smoke test
  gap noted throughout this doc — still open, this pass only touched
  `data/exercises.json` and didn't need the FastAPI stack to run.

## Latest pass — Test suite + real smoke test, and a security fix (v5.11, Phase 13)

This pass exists because the sandbox's network config changed since every
earlier pass: `pypi.org`/`files.pythonhosted.org` are now reachable, so
`pip install -r requirements.txt` finally succeeds here. Every prior pass's
"still needs the real `uvicorn`/`pip install` smoke test" caveat — repeated
in the Phase 2, Program Builder, Auth, Critical-gap, and every
exercise-library pass above — is what this pass closes.

- **`pip install -r requirements.txt`**: succeeded outright (fastapi 0.141,
  sqlalchemy 2.0.51, pydantic 2.13, pyjwt, pytest, httpx all installed
  cleanly). `from backend.main import app` then boots for real — the
  `openapi.json` spec lists all 28 routes with their real paths, matching
  what routes.py defines. No import/wiring regression from any prior pass's
  stub-only verification.
- **New `tests/` suite, 52 tests, all passing against the real app** (no
  stand-in `fastapi`/`pydantic`/`sqlalchemy` modules anywhere):
  - `tests/conftest.py` — per-test fixture: a throwaway on-disk SQLite file
    (via a temp-dir `DATABASE_URL` env override + re-importing `backend.*`
    fresh + a `get_db` dependency override), so tests never share state and
    can run in any order. `registered_user`/`auth_headers` fixtures cover
    the common "need a logged-in caller" case.
  - `tests/test_metadata_endpoints.py` (12 tests) — every read-only
    reference endpoint (`/metadata`, `/goals`, `/splits`, `/equipment`,
    `/exercises`, `/injuries/grouped`, `/conditioning-protocols`,
    `/training-phases`, `/manual-templates`, `/knowledge-graph/{id}`),
    plus 404-not-500 checks for unknown sport/exercise ids.
  - `tests/test_auth.py` (16 tests) — the exact register → login → refresh
    → logout chain flagged as never-smoke-tested, plus: duplicate-email
    409, short-password 422, wrong-password 401, garbage-token 401 (not
    500), profile update, refresh-token rotation (confirms the *old*
    refresh token stops working after one use), logout revocation, the
    password-reset request's enumeration-safe generic response, and the
    login rate-limiter actually returning 429 on the 11th attempt in a
    minute.
  - `tests/test_generation_endpoints.py` (8 tests) — `generate-workout`
    and `generate-program` against the real `ProgressionEngine`/
    `program_builder` and the real 731-exercise `data/exercises.json`
    (not a stand-in), an unknown split returning 400 not 500, an invalid
    `experience_level` returning 422, and `estimate-level`.
  - `tests/test_sessions_and_readiness.py` (8 tests) — session logging,
    per-account scoping, the Phase-5 `MIN_SESSIONS_FOR_SIGNAL` gate (1
    logged session correctly reports `has_enough_history: False`), and
    `/recommendations/history` requiring auth. **This is the literal
    "log a few sessions as a real account, call generate-workout again,
    confirm personalization_applied" scenario the Recommendation-engine
    pass's own verification caveat asked for** — now automated.
  - `tests/test_exercise_data_integrity.py` (5 tests) — formalizes the
    by-hand verification every `generate_batchN` script's docstring has
    claimed (zero duplicate ids, no dangling `progressions`/
    `regressions`/`alternatives` references, every equipment type at or
    above the 5-exercise floor, every exercise has the required field
    set, total count matches the 731 the batch9 pass claimed) so it's
    checked by CI going forward instead of only asserted in prose.
- **Security fix found by this pass, not gone looking for it — an IDOR /
  broken-access-control bug**: `GET /api/v1/sessions`, `DELETE
  /api/v1/sessions/{id}`, and `GET /api/v1/readiness/suggested` all took an
  `athlete_id` *query parameter* and only overrode it with the caller's own
  id when a valid JWT was present (`if current_user is not None:
  athlete_id = str(current_user.id)`) — meaning an **anonymous, completely
  unauthenticated** request could pass any `athlete_id` string, including a
  real account's own numeric id (sequential integers - trivially
  guessable), and read or delete that account's private session/readiness
  history with no login, no token, nothing. The Auth pass's own writeup
  above claimed "a logged-in person can no longer read or delete another
  athlete_id's history by passing a different value" — true, but that
  protection only ever applied to *authenticated* callers; anonymous
  callers were never checked at all. `tests/test_sessions_and_readiness.py`
  caught this because a test written to prove the opposite (that spoofing
  fails) initially passed for the wrong reason (a coincidental id match),
  and tightening the test to use a definitely-wrong id turned up the real
  gap. **Fixed**: all three routes now compute
  `athlete_id = str(current_user.id) if current_user is not None else
  "default"` — an anonymous caller's query-param value is never trusted,
  full stop. Re-ran the full 52-test suite after the fix; nothing else
  broke.
- **Not done in this pass**: no broader security audit (Phase 16 is still
  only "partial" — this was one bug found while writing unrelated tests,
  not a systematic pass over every endpoint for the same class of issue);
  no CI wiring (GitHub Actions/etc.) to actually run `pytest` on push -
  the suite exists and passes locally but nothing runs it automatically
  yet; no coverage measurement (`pytest-cov` isn't in requirements.txt);
  the Program Builder's 8 split templates and the DAG-progression
  (`knowledge_graph.py`) logic still have no dedicated test file - covered
  only incidentally by `test_generate_program_with_defaults`.

## Security-audit + Web UI audit + lint-cleanup pass (v5.12)

Three small, low-risk items closed out in one pass, each verified before
moving to the next:

- **Security audit (the follow-up the previous pass suggested)**: checked
  every route touching `athlete_id`-shaped caller scoping
  (`/sessions` POST/GET, `/sessions/{id}` DELETE, `/readiness/suggested`,
  `/recommendations/history`) against the same anonymous-bypass shape the
  Phase-13 pass found and fixed. All four already resolve
  `athlete_id = str(current_user.id) if current_user else "default"`, and
  `delete_session_log`/`list_session_logs` filter by `athlete_id` at the
  query level (not just the row id) - confirmed by reading
  `readiness_service.py` directly, not just the route signatures. No new
  bug found. This was one bug-class check, not a full Phase-16 audit -
  Phase 16 stays "partial."
- **Web UI audit**: `docs/ROADMAP.md` and the README's "Web UI" section
  both still described Phase 12 as an open TODO. Reading
  `frontend/web/index.html` directly found a complete, already-wired
  login/register/account flow (see the Phase 12 row above) - the docs were
  just stale, not the code. No code needed here; docs corrected instead.
- **Lint cleanup (Phase 15)**: see the Phase 15 row above for exactly what
  was removed and how it was verified without a real `pyflakes` install.

**Not done in this pass**: no real `pyflakes`/`ruff` run (still blocked by
sandbox network access - re-run once `pip install` reaches PyPI again, the
way the Phase-13 pass's real `pytest` run did); no attempt to run the test
suite here either, for the same reason (`ModuleNotFoundError: No module
named 'fastapi'` in this session) - the touched files are only verified via
`python -m py_compile` plus manual read-through, not a live test run. Treat
that as a standing gap same as every prior pass's smoke-test caveat, and
run `pytest tests/ -q` for real before shipping this pass's changes.

## Database completion pass — Phase 4 (v5.13)

Two pieces, both scoped exactly to what the Phase 4 row had actually
called out as missing: a migration framework, and a repository layer.

- **`backend/migrations/`** (new) — `runner.py` is a small,
  stdlib+SQLAlchemy-only migration runner: a `schema_migrations` tracking
  table (`revision`, `applied_at`) plus a discovery step that imports
  every module under `backend/migrations/versions/`, sorts by `revision`,
  and applies whatever isn't recorded yet, each in its own transaction.
  **Not Alembic** — this sandbox has no PyPI access (same standing gap
  every prior pass has hit for `fastapi`/`pytest`/etc.), so `pip install
  alembic` couldn't even be attempted here, let alone verified working.
  Writing an `alembic.ini`/`env.py` nobody in this environment can prove
  runs would be worse than a small honest substitute that actually does
  run. `runner.py`'s own docstring says exactly this and flags swapping
  to real Alembic as a reasonable follow-up once PyPI access exists.
  `backend/migrations/versions/m0001_initial_schema.py` is the first (and
  so far only) migration — it reuses `Base.metadata.create_all` against
  the existing model classes rather than hand-duplicating column
  definitions in raw DDL, so it's a no-op against any pre-existing v5.x
  database (tables already exist) and a real create against a brand-new
  one, either way now recorded as revision `0001_initial_schema`. Future
  schema changes go in new numbered migration files from here on instead
  of silently re-deriving from whatever the model classes currently say.
  `backend/core/database.py`'s `init_db()` now calls `run_migrations(engine)`
  instead of a bare `Base.metadata.create_all(bind=engine)` — same
  idempotent-on-every-startup behavior as before, now with a tracked
  history.
- **`backend/repositories/`** (new) — one class per table:
  `SessionLogRepository`, `UserRepository`, `RefreshTokenRepository`,
  `PasswordResetTokenRepository`. Every method is a straight extraction of
  a query that used to live inline in `readiness_service.py`/
  `auth_service.py` — same filters, same ordering, same commit points, no
  behavior change. The one case that needed care:
  `auth_service.confirm_password_reset` composes a password-hash change
  with a bulk refresh-token revocation into a single transaction (a
  password reset revoking every other session is one atomic action, not
  two), so `RefreshTokenRepository.revoke_all_for_user` deliberately does
  NOT commit — the service still calls `db.commit()` once at the end,
  exactly where the original inline code did. Every other repository
  method that writes commits immediately, matching what the code it
  replaced did.
- **Verified**: `python -m py_compile` clean on every new/touched file;
  a hand-rolled `ast`-based unused-import scan re-run against the whole
  `backend/` tree came back clean (no new dead imports introduced); the
  exact raw SQL the tracking table uses (`CREATE TABLE IF NOT EXISTS
  schema_migrations (...)`, the insert, the select) was round-tripped
  against Python's stdlib `sqlite3` directly to confirm the SQL itself is
  valid SQLite, since `sqlalchemy` isn't installable in this sandbox
  either (`ModuleNotFoundError` for `sqlalchemy`/`fastapi`/`pydantic` all
  confirmed fresh in this session — same gap as every prior pass, not
  newly discovered here).
- **Not done / real gap**: none of this has run against the real
  `SQLAlchemy` `Engine`/`Connection` objects it's written for, because
  `sqlalchemy` itself isn't installed here — the `sqlite3` round-trip
  above only proves the SQL text is valid, not that `run_migrations()`'s
  actual `engine.begin()`/`conn.execute(text(...))` call sequence behaves
  as designed end-to-end, or that a fresh `python -m backend.main` boots
  clean with the new `init_db()`. **Run `python -m backend.main` (or the
  test suite) for real before shipping this pass** — the same standing
  caveat every prior database/auth pass in this doc has carried, now
  applying to the migration runner and repositories too. If it doesn't
  boot clean, the two likeliest culprits given what changed: (1) a
  circular import between `database.py` and the migration modules importing
  `Base` back from it, or (2) `engine.begin()` handing `create_all` a
  `Connection` instead of the `Engine`/session it might implicitly expect
  somewhere - both are plausible-but-unverified risks worth checking
  first if `init_db()` throws.

## Suggested next phase (superseded — see v5.18 below)

With Phases 4 and 17 now done and Phase 10 closed out fully, **Phase 7**
(adaptive programming is still a heuristic, not a scored model) and
**Phase 11** (API models/versioning - a response-model coverage audit is
still genuinely undone) are the next real feature gaps. The single
highest-leverage next step remains unchanged from every prior pass on
this page: a real `pip install -r requirements.txt` + `pytest tests/ -q`
+ `uvicorn backend.main:app` run. Five passes in a row now (the v5.13
database pass, the v5.12 lint/audit pass, and this v5.14 pass, on top of
the two already named above) have shipped code verified only by reading,
`py_compile`, and logic checks against stubbed dependencies - never by
actually running the app. Whoever picks this up next with real network
access should run that smoke test before adding anything further; it
would very likely surface small issues none of this reading-only
verification can catch.

## Real end-to-end smoke test, finally run for real (v5.18)

This sandbox has real PyPI/network access. This pass did exactly the
thing every prior pass since Phase 2 flagged as the single
highest-leverage next step and never actually did (with the partial
exception of the Phase 9/10 logging pass and v5.11/Phase 13, both of
which also had real network access in their own sandboxes) — no more
stand-in `fastapi`/`sqlalchemy`/`pydantic` modules anywhere in this pass.

- **`pip install -r requirements.txt`** in a fresh venv: clean install,
  zero errors, including `psycopg2-binary` (often the flaky one).
  Versions actually installed: fastapi 0.141.1, uvicorn 0.52.2, pydantic
  2.13.4, pydantic-settings 2.15.0, SQLAlchemy 2.0.52, PyJWT 2.13.0,
  httpx 0.28.1, pytest 9.1.1, networkx 3.6.1 — all newer than the
  `requirements.txt` floors and newer than what any prior pass tested
  against.
- **`from backend.main import app` for real**: boots clean. Note for
  whoever reads this next — `app.routes` itself only lists 4 entries
  plus an `_IncludedRouter`/`Mount` object under fastapi 0.141's newer
  lazy router-inclusion internals; this looks alarming if you inspect
  `app.routes` directly (as prior passes' stand-in modules effectively
  did) but is not a bug. Confirmed via `TestClient(app).get("/openapi.json")`
  that all **34 real route paths** are registered and schema-correct.
- **Full real pytest run**: `python -m pytest tests/ -q` — **153/153
  passing**, ~63s, against the actual installed stack, not stubs. Only
  warnings: a `StarletteDeprecationWarning` (`TestClient` + `httpx`,
  cosmetic, from Starlette itself) and a Python-3.12
  `DeprecationWarning` on SQLite's default datetime adapter (from
  SQLAlchemy's use of stdlib `sqlite3`, not app code) — both pre-existing
  upstream library behavior, not something this app's code causes or can
  fix without moving off stdlib `datetime`-as-SQLite-column, which is out
  of scope for a verification pass.
- **Live `uvicorn backend.main:app` server, hit with a real HTTP
  client** (not `TestClient`) — the actual scenario this doc has asked
  for since the Critical-gap pass: register → login → `/auth/me` →
  refresh → confirm the *old* refresh token is rejected (401, rotation
  confirmed live) → logout (204) → password-reset request (202,
  enumeration-safe generic message, real token logged server-side per
  the existing no-email-provider gap) → `generate-workout` (200, full
  response shape) → `generate-program` (200, full response shape) →
  `/equipment` twice back-to-back to confirm the Phase-8 cache serves
  identical data on the second call. Every step matched expected
  behavior; no 500s, no unexpected status codes anywhere in the chain.
  (Two 422s hit during this pass turned out to be this pass's own test
  payloads using wrong enum casing/values, e.g. `"powerlifting"` instead
  of `"Powerlifting"` and `"Hypertrophy"` instead of the real
  `primary_goal` enum value `"Build Muscle"` — confirmed by re-running
  with corrected payloads and getting clean 200s. Worth noting as a
  minor DX gap, not a bug: neither `WorkoutRequest.sport` nor
  `ProgramRequest.primary_goal`/`experience_level` normalize casing
  before validating against their `Literal`/free-text rules, so a caller
  has to match the exact casing `GET /api/v1/metadata`/`/goals` return.
  Not fixed in this pass — a real behavior change to schema validation,
  not a verification task — but flagged here for a future pass since
  it's a plausible real-world integration papercut for any client that
  doesn't lowercase/normalize before sending.)
- **Not a bug — confirmed correct**: the one non-200 in the smoke test
  that *was* real app behavior rather than a test-payload mistake was
  the enumeration-safe password-reset response (202 with a generic
  message regardless of whether the email exists) — exactly as
  documented in the Critical-gap pass.
- **Not done in this pass**: no fix attempted for the casing papercut
  noted above; no CI wiring (still flagged, unchanged); no coverage
  measurement; no real `pyflakes`/`ruff` run (this pass's network access
  covers PyPI generally, so this is newly unblocked and would be quick
  follow-up work, just not done here since this pass's scope was
  specifically the standing smoke-test gap); the four-uncoordinated-
  deload-signals gap from v5.17 is unchanged and still the most
  significant open design gap in the app.

**This closes the "run the real smoke test" caveat that has been
repeated, verbatim in spirit, in every single pass on this page since
Phase 2.** The next real feature gaps are unchanged: Phase 7 (adaptive
programming is still heuristic, not scored), Phase 11 (API
versioning/response-model audit), Phase 16 (security audit is still only
partial — one bug class checked, not a systematic sweep), and
reconciling the four deload signal sources flagged in v5.17.

## Casing normalization, generate-* rate limiting, real pyflakes/ruff, and deload-magnitude reconciliation (v5.19)

Four fixes in this pass, each closing a specific gap flagged by v5.18's
smoke test or the standing roadmap notes - no new gaps discovered, all
picked directly off items already on this page.

- **Casing normalization on `experience_level`/`primary_goal`/`sport`**:
  v5.18's live smoke test found that `WorkoutRequest.experience_level` and
  `ProgramRequest.primary_goal`/`experience_level` (all `Literal` enums)
  422'd on any casing other than exact - `"intermediate"` was rejected,
  only `"Intermediate"` worked. Fixed with a shared
  `_normalize_to_canonical(value, canonical_values)` helper
  (`backend/models/schemas.py`) wired in as a `mode="before"`
  `field_validator` on all three fields - case-insensitive match against
  the real canonical list, corrected to canonical casing before Literal
  validation runs; a value that doesn't match *anything* (any casing)
  still 422s exactly as before, so this doesn't loosen validation, only
  fixes casing. **The more serious version of the same bug**: `sport` is
  deliberately free text (custom/unlisted sports are a real, supported
  use case), so a casing mismatch there didn't 422 at all - it silently
  fell through every `sport_profiles.py` dict lookup
  (`SPORT_QUALITY_PROFILES.get(sport, {})` etc. all default to `{}` on a
  miss) and produced a generic, non-sport-specific session with zero
  signal anything was wrong. Since `sport` can't get a `Literal` (it's
  genuinely open-ended) and `schemas.py` can't import the runtime-built
  `engine.all_sports` list without creating the exact import cycle its own
  module docstring says the schemas/services split exists to avoid, this
  one's fixed in `backend/api/routes.py` instead: a new
  `_normalize_sport_casing()` case-insensitive-matches the request's
  `sport` against `engine.all_sports` and corrects casing only on a real
  match, leaving genuine free text (no match at any casing) completely
  untouched - verified live against a running server: `"powerlifting"` ->
  `"Powerlifting"` (real sport, casing fixed), `"BODYBUILDING"` ->
  unchanged (not a real sport in this app - `"Look Jacked"` is the closest
  canonical equivalent - correctly left as free text, not silently
  rewritten to something else), `"Underwater Basket Weaving"` -> unchanged.
  New tests in `tests/test_generation_endpoints.py` cover all of this
  (lowercase level/sport accepted and corrected, unknown sport left alone,
  genuinely invalid level still 422s).
- **Rate limiting on `generate-workout`/`generate-program`** (closes the
  Phase 16 gap the AI-hooks pass flagged: "no rate limiting specific to
  this endpoint's AI cost - the existing per-IP rate limits on auth
  endpoints don't cover generate-workout at all, AI-enabled or not"):
  reused the existing `backend/core/rate_limit.py` limiter (same
  `X-Forwarded-For`-aware IP resolution as the auth endpoints) -
  30/minute/IP on `generate-workout`, 10/minute/IP on `generate-program`
  (tighter, since one program request fans out into `weeks x days_per_week`
  underlying session generations, not just one). Verified live: 9
  successful `generate-program` calls then real `429`s with a
  `Retry-After` header from the 10th call on. New tests confirm both
  limits trip at the documented threshold.
- **Real `pyflakes`/`ruff` run** (this sandbox's PyPI access, confirmed in
  v5.18, was previously only used for `pytest`/`fastapi` - this pass used
  it for the lint tooling every prior pass since Phase 15 flagged as
  blocked): found and fixed 2 real issues in `backend/` (an unnecessary
  `f` prefix on a string with no placeholders in
  `injury_taxonomy.py`, one genuinely unused `Optional` import in
  `pl_hypertrophy_manual.py`) and 3 in one-off `scripts/` (unused `sys`
  imports in two generator/data-ops scripts, another `f`-prefix-without-
  placeholder in `tag_manual_exercises.py`). One remaining `pyflakes` hit
  (`backend/migrations/versions/m0001_initial_schema.py`'s
  `db_models` import) is a deliberate, already-`# noqa`'d side-effect
  import (populates `Base.metadata` before `create_all`) - confirmed via
  `ruff` (which respects `noqa`, unlike bare `pyflakes`) that this isn't a
  real finding. Full codebase is clean under both tools now.
- **Deload-magnitude reconciliation** (`frontend/web/js/autoregulation.js`)
  - the concrete part of the v5.17-flagged "four uncoordinated deload
  signals" gap that was actually fixable without new design work: v5.17's
  own note singled out `applyWeekDeloadStep`'s "flat -15 percentage-point
  deload cut vs. `_prescribe_volume_core`'s continuous readiness_factor-
  driven curve" as a concrete divergence. Reading through every one of
  `_prescribe_volume_core`'s per-type deload branches server-side turned
  up that the client's approximation was wrong in more places than just
  that one: a flat `x0.7` reps cut applied to `strength_bodyweight`
  exercises the server never adjusts reps for on deload (only `sets`
  drops, server-side); a `work_seconds x0.8` cut for conditioning work the
  server never applies (work_seconds is untouched by deload for every
  energy system - only the work:rest *ratio* changes, and by different
  amounts per energy system: 2.5x for Mixed, 8x for Alactic, 0.7x for
  Aerobic, 2.2x for Lactic); and a `distance_meters x0.8` cut applied to
  Carry exercises that the server never touches at all during deload
  (only Carry's *load* - `load_pct_bodyweight` - gets cut server-side;
  distance is untouched). `applyWeekDeloadStep` was rewritten to mirror
  every one of `_prescribe_volume_core`'s real per-type deload branches
  exactly (`strength`: `load_pct_1rm *= 0.8` multiplicatively, not a flat
  point cut; `isolation`: reps `-2` floored at 10; `strength_bodyweight`:
  reps left untouched; `conditioning`: work left untouched, rest
  recomputed from work using the correct per-`energy_system` ratio;
  `isometric`: hold `x0.7` - this one was already correct; `carry`: load
  `x0.8`, distance untouched; `ruck`: distance `x0.6` with
  `duration_minutes` recomputed from the new distance at the same 12
  min/km pace the server uses; `technical`/anything else: untouched
  beyond the uniform `sets=2` every type gets). Verified by extracting the
  real function from the actual file (not a reimplementation) and running
  it against hand-computed expected values for all 9 server-side
  prescription types with `node`, confirming exact numeric parity with
  `_prescribe_volume_core`'s documented formulas for every type. **What
  this does NOT resolve** (real, left open, same as v5.17's own framing):
  which of the four sources gets to *decide* a week is a deload in the
  first place is still genuinely uncoordinated - the fixed calendar week
  (`program_builder.py`), the signal-triggered week
  (`checkSignalDeload`, reusing a real server-computed `recommend_deload`
  signal - this part was never a duplicate, just an application of a real
  server signal), and session-generation-time `adaptive_training_load`
  are three independent triggers that don't defer to each other beyond
  `checkSignalDeload`'s own "don't touch a week already flagged deload"
  check. That's a real product decision (which signal should own
  in-progress-program adjustments), not a mechanical fix, and is
  unchanged from v5.17's own assessment. Also clarified in a new code
  comment: `autoregulateNextWeek`/`applyAutoregulationStep` (the
  hold/boost-next-week's-numbers-from-today's-performance mechanism, a
  different function from the deload one above) has no server-side
  equivalent to reconcile against at all - it's a genuinely distinct
  client-only feature (nudging an already-generated future week from a
  single day's just-logged performance, something the session-generation-
  time adaptive-load engine has no concept of), not a duplicate, so its
  own +/-3%-ish constants don't need to match anything server-side.
- **Verified**: `node --check` clean on every file in
  `frontend/web/js/`; full pytest suite - **160/160 passing** (153 +  7
  new casing/rate-limit tests), run against the real installed stack, not
  stubs, same as v5.18.
- **Not done in this pass**: the actual trigger-coordination design
  question above is still open; Phase 7 (adaptive programming still
  heuristic) and Phase 11 (API versioning audit) are untouched; no browser
  actually loaded `autoregulation.js` and clicked through a real deload
  scenario end-to-end (verified via extracted-function unit testing
  against hand-computed expected values instead, since there's no headless
  browser/JS test runner in this sandbox) - worth a real click-through
  before shipping, same spirit as every backend smoke-test caveat on this
  page.

## Real logic-level smoke test + IDOR fix on create_session (v5.15)

This sandbox still has no PyPI access (same standing gap as every prior
pass), so the real `fastapi`/`pydantic`/`sqlalchemy` packages still
couldn't be installed. Instead of repeating the read-only/`py_compile`-only
verification every prior pass used, this pass wrote small local stand-in
modules for `fastapi`/`pydantic`/`sqlalchemy` (HTTPException/APIRouter/
BaseModel+Field+field_validator/a query-object-free ORM stub) - not a
real reimplementation of those libraries, just enough surface for
`WorkoutRequest`/`ProgramRequest` to actually construct and for
`ProgressionEngine.generate_session`/`program_builder.generate_program`
to actually run - and used them to genuinely execute the engine, not just
read it:

- **Fuzzed `generate_session`** across all 15 sports x 5 experience levels
  x randomized equipment/injuries/readiness/manual_only (75 runs), plus
  targeted edge cases (empty equipment, readiness=1 and 100, an unknown
  sport string, `mode="custom"` with a nonexistent exercise id,
  `target_categories`/`target_muscles`, both `training_emphasis` values,
  session_duration_minutes at its 15/180 bounds). Zero exceptions.
- **Fuzzed `generate_program`** across every `SPLIT_TEMPLATES` key (+
  "auto") x all 7 `PRIMARY_GOALS` x days_per_week in {1,3,5,7} (112 runs),
  and separately every `training_phase` x weeks in {1,2,3,8,16}. Zero
  exceptions.
- **Re-verified `data/exercises.json`** programmatically (769 exercises,
  zero duplicate ids, zero dangling progressions/regressions/alternatives
  references, every exercise has the required field set) - confirms the
  existing `tests/test_exercise_data_integrity.py` claims are still true
  today, not just at whichever commit last ran them.
- One false lead worth recording so a future pass doesn't repeat it:
  `"equipment": "Partner / Clinch Bag"` and `"Climbing Hold / Hangboard"`
  on two exercises initially looked like a data bug (a string that could
  never exact-match a canonical equipment tag). It isn't - the frontend
  renders every unique `equipment` string as its own literal checkbox
  (see `frontend/web/index.html`'s equipment-catalog rendering), so these
  are legitimate, distinct, selectable equipment options, not malformed
  data. `tests/test_exercise_data_integrity.py` already documents this
  explicitly via `_NICHE_EQUIPMENT_EXEMPT`. No change needed there.

**Real bug found and fixed - an IDOR gap the Phase-13 pass's own fix
missed on the write side**: `POST /api/v1/sessions` (`create_session` in
`backend/api/routes.py`) only overrode `payload.athlete_id` with the
caller's own account id when `current_user is not None` - for an
anonymous caller, whatever `athlete_id` string was in the POST body was
trusted as-is and written straight to the database. The Phase-13 pass
fixed this exact spoofing shape on `GET /api/v1/sessions`,
`DELETE /api/v1/sessions/{id}`, and `GET /api/v1/readiness/suggested` (all
three now force `athlete_id = str(current_user.id) if current_user else
"default"`), but `create_session` was never brought in line - meaning an
anonymous, unauthenticated request could POST a real account's guessable
sequential numeric id as `athlete_id` and inject a fabricated session-log
row directly into that account's real training history, which then also
fed that account's `/api/v1/readiness/suggested` computation. **Fixed**:
`create_session` now resolves `athlete_id` the exact same way as the
other three routes, unconditionally, before constructing the payload to
persist - a verified JWT is the only way to get a non-"default"
`athlete_id` on any of the four session/readiness routes now, full stop.
Added `test_anonymous_cannot_spoof_athlete_id_on_create` to
`tests/test_sessions_and_readiness.py` to keep this fixed going forward.

**Not done in this pass**: the stand-in `fastapi`/`pydantic`/`sqlalchemy`
modules are deliberately minimal (no real request/response cycle, no real
SQL execution, no dependency-injection resolution) - they prove the
*business logic* (engine scoring, program generation, the athlete_id
resolution fix above) runs correctly against real data, not that the
actual HTTP layer, database, or `pytest` fixtures in `tests/conftest.py`
work end-to-end. The standing recommendation from every prior pass is
unchanged and still the single highest-leverage next step: a real `pip
install -r requirements.txt` + `pytest tests/ -q` + `uvicorn
backend.main:app` run, the first time any of this is verified against the
actual libraries it's written for rather than a stand-in.

## Phase 19: Adaptive load/volume engine, built on real training history

Extended the existing history-personalization layer
(`backend/services/recommendation_engine.py`) rather than creating a
parallel engine - `build_history_signals`/`personalization_multiplier`
already answered "which qualifying exercise should rank higher/lower right
now"; this phase adds `compute_adaptive_load_adjustment`, which answers
"should the *whole next session* run lighter/heavier or bigger/smaller
than today's readiness slider alone would prescribe", from:

- session RPE trend (last 3 vs prior 3 logged sessions), falling back to
  averaged per-set `rpe`/`rir` values inline in `log_json` when the
  session-level `rpe` field is absent (RIR converted onto the same 1-10
  RPE scale via `10 - rir`);
- logged weekly set volume (last 7 days vs the 7 before) - a >=1.4x
  week-over-week spike caps volume, the standard acute:chronic
  overreach read;
- the gap since the last logged session vs the athlete's own typical
  cadence (or a Program Builder request's `days_per_week` when available)
  - a long-enough gap eases the next session back in instead of picking
    up where they left off;
- the aggregate progressing/plateau split already computed per exercise
  by `build_history_signals` (re-read in aggregate, not recomputed) -
  majority-plateaued adds volume for a hypertrophy-leaning goal, trims
  intensity otherwise.

Wired into `ProgressionEngine.generate_session`: the resulting
`intensity_multiplier` folds into `readiness_factor` (so every existing
%1RM/hold/work-interval formula in `_prescribe_volume` reacts to it for
free, no second multiplier threaded through each branch), a strong
RPE-spike can independently flip `deload_mode` true, and
`volume_multiplier` scales each prescribed exercise's `sets` via a new
thin `_prescribe_volume` wrapper around the renamed `_prescribe_volume_core`
(one scaling point after the fact, instead of touching each of that
function's 7 return branches). `generate_program` threads `training_phase`
and `days_per_week` through the same per-day `generate_session` call
(confirmed by `test_fight_week_phase_caps_multipliers_at_baseline`) rather
than reimplementing any of this at the program level - a Fight
Week/Post-Competition phase caps both multipliers at baseline regardless
of what the trend alone would otherwise justify. The whole adjustment
(multipliers, `auto_deload_recommended`, `sessions_considered`, and a
plain-English `reasons` list) rides along in the response as
`adaptive_training_load`, same transparency contract as
`personalization_applied`/`history_signals`. Gated behind
`MIN_SESSIONS_FOR_LOAD_ADJUSTMENT` (4) logged sessions, same "don't assume
more than we've been told" default every other history feature here uses
- below that, or for an anonymous caller, it's a complete no-op (both
multipliers 1.0), identical output to before this phase existed.

10 new tests in `tests/test_adaptive_load_engine.py` (rising/falling RPE,
auto-deload on a high recent-RPE average, weekly volume spikes, returning
from a break, per-set RPE/RIR fallback, the Fight Week cap, anonymous/
below-threshold no-ops, and a `generate-program` smoke test). Full suite:
**153/153 passing** (`pytest tests/ -q`), run against the real installed
`requirements.txt` stack, not a stand-in.

