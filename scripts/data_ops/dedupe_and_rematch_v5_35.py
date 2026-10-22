"""
dedupe_and_rematch_v5_35.py — v5.35 data-integrity pass.

Two independent fixes, run together and documented together because they
were both found while auditing the FORGE S&C Template Libraries
(data/sc_templates/*.json, ~19.8k exercise-name references across the ten
sport libraries) against data/exercises.json:

1. DUPLICATE EXERCISE — "Prone Y-T-W Raise" existed under two ids:
   prone_ytw_raise_001 (the fuller entry: populated sport_priority,
   movement_family, in_manual, push_pull, and a progressions link to
   doorframe_row_001) and back_prone_ytw_001 (a thinner duplicate — same
   name/muscles/joint_stress/injuries_to_avoid, missing those extra
   fields). back_prone_ytw_001 was not referenced anywhere else in
   exercises.json (no other exercise's progressions/regressions/
   alternatives pointed at it), so it was safe to drop outright. Kept
   prone_ytw_raise_001. 828 -> 827 exercises. This was the only duplicate
   in the file — every other exercise name and every exercise id is
   unique (checked case-insensitively for names).

2. TEMPLATE <-> DATABASE NAME MATCHING — auditing all ~19.8k template
   exercise-name references against exercises.json via the production
   matcher (sc_template_library.normalize_exercise_name /
   fuzzy_resolve_exercise_name — the same functions program_builder.py
   uses to equipment/injury-check a template exercise before serving it)
   found ~8.1k references (165 distinct names) falling through both the
   exact and fuzzy match and landing as an unchecked "Unverified"
   passthrough. Two targeted, conservative widenings of that matcher
   (still equipment-vocabulary-only, still refuses to guess across a
   genuine movement difference, still backs off to None on any ambiguous
   tie) recovered a meaningful share of those without touching either
   the template JSON or exercises.json:
     - Added "med" -> "medicine" to _ABBREVIATIONS, so "Med-Ball Russian
       Twist" normalizes the same as exercises.json's own "Medicine Ball
       Russian Twist" (was previously two different token bags).
     - Added "rack" / "belt" / "vest" to _EQUIPMENT_WORDS, and
       generalized fuzzy_resolve_exercise_name from a one-directional
       subset check to a symmetric-difference check — every token either
       side adds or drops must be equipment vocabulary, not just the
       tokens on one side. This resolves cases like "Back Squat (Rack)"
       -> "Barbell Back Squat" (diff {rack, barbell}, both equipment
       words) that the old one-directional subset check missed because
       neither name's token set was a subset of the other's.
   See backend/services/sc_template_library.py for the actual matcher
   code and tests/test_sc_template_library.py for the regression tests
   covering both the newly-bridged cases and the cases that must keep
   failing (e.g. "Trap-Bar Squat" has no real equivalent in
   exercises.json and correctly still resolves to None — a template
   wording gap, not a matcher gap; see the NOT-YET-RESOLVED list below).

NOT touched: the sc_templates/*.json source files themselves (exercise
names there are the template authors' own wording and are left as-is —
this is a matching fix, not a rewrite of the templates), and the ~60
remaining unmatched template names that are genuinely absent from
exercises.json (mostly sport-specific conditioning/skill work — swim
drills, sled sprints/pulls by distance, running intervals, hangboard/
campus-board climbing drills, shadowboxing/bag rounds — plus a handful of
real gym-lift gaps exercises.json doesn't have an equivalent for yet,
e.g. a plain barbell shoulder shrug, a triceps pushdown, a seated calf
raise machine, an ab crunch machine, a barbell skull crusher, a dumbbell
lateral raise, a cable glute kickback). Adding new exercises to close
those gaps is a separate, larger content task (each needs the full
schema: primary/secondary/stabilizer muscles, joint_stress,
injuries_to_avoid, tendons/ligaments, sport_priority, etc.) and wasn't
guessed at here rather than risk under-specified safety-relevant data.

This script is a record of the change, not a re-runnable transform —
both edits were applied directly to data/exercises.json and
backend/services/sc_template_library.py.
"""
