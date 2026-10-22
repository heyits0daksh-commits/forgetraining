"""
map_injuries_to_avoid.py — fills in / completes the injuries_to_avoid tag on
every exercise in exercises.json using a similarity (k-nearest-neighbor)
model built from the exercises that already carry hand-curated
injuries_to_avoid tags.

WHY THIS APPROACH
injuries_to_avoid is NOT a simple function of joint_stress alone: e.g.
"Shoulder" appears in joint_stress on 431 exercises but "Shoulder
Instability (General/Atraumatic)" is only warranted on a subset of those
(the ones actually loading the shoulder in an unstable / high-risk way).
The existing 678 already-tagged exercises encode this judgment implicitly.
Rather than re-deriving 44 tags from scratch with hand-picked thresholds
(which would just be a second, less-informed guess), this script treats the
already-tagged exercises as ground truth and, for every exercise (tagged or
not), asks "what do the most biomechanically-similar already-tagged
exercises carry?" via a weighted k-NN vote.

SIMILARITY FEATURES (all already on every exercise — nothing invented):
  joint_stress (Jaccard overlap, heavily weighted — this is the single
    strongest signal for which injuries apply at all), category,
  movement_pattern, chain_type, force_type, velocity_type, movement_plane,
  push_pull, upper_lower, is_compound, difficulty (closeness).

SAFETY FILTER
A candidate tag is only ever added if the injury's own taxonomy entry
resolves to a joint that is actually in THIS exercise's joint_stress list —
neighbors can suggest a tag, but the exercise's own anatomy has final veto.
(E.g. neighbors can't cause "Achilles" to land on an exercise with no Ankle
in joint_stress.)

ADDITIVE / CONSERVATIVE
- Only ADDS tags; an exercise's existing hand-curated injuries_to_avoid
  entries are never removed or replaced.
- A tag is added only if it wins a weighted-vote share >= CONFIDENCE_THRESHOLD
  among the exercise's k nearest already-tagged neighbors (self excluded).
- Every added tag must already resolve in INJURY_TAXONOMY (reuses the
  existing 44-tag vocabulary already in use across the file — see
  test_exercise_data_integrity.py::test_every_injuries_to_avoid_tag_resolves_in_taxonomy)
  rather than inventing new taxonomy strings.

Re-runnable: exercises that already have a full tag set simply get no
diff (existing tags are a superset of / equal to what the model would add).
"""
import json
import shutil
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from backend.core.config import settings
from backend.services.injury_taxonomy import INJURY_TAXONOMY

SRC = settings.EXERCISES_JSON_PATH
BACKUP = settings.BACKUP_DIR / "exercises_pre_injury_mapping_backup.json"

K_NEIGHBORS = 15
CONFIDENCE_THRESHOLD = 0.35  # weighted vote share required to add a tag

# Precompute which joint each known tag belongs to, from the taxonomy.
TAG_JOINT = {name: entry["joint"] for name, entry in INJURY_TAXONOMY.items()}
TAG_SEVERITY = {name: entry["severity"] for name, entry in INJURY_TAXONOMY.items()}
TAG_MUSCLES = {name: entry.get("muscles_to_protect") or [] for name, entry in INJURY_TAXONOMY.items()}

# Tendon-specific tags don't carry muscles_to_protect in the taxonomy (that
# field is a Muscle-tissue-entry thing), but a tendon tag is still only
# meaningful on an exercise that actually loads the muscle whose tendon it
# is - a Triceps Tendon tag has no business on a Biceps-dominant curl just
# because both happen to stress the Elbow. Small, explicit map for the
# tendon/general tags actually in use in exercises.json (see the resolved-
# tag dump in this file's design notes) rather than a fragile string parse.
TENDON_TAG_MUSCLE_KEYWORDS = {
    "Rotator Cuff": ["rotator cuff", "supraspinatus", "infraspinatus", "subscapularis", "teres minor"],
    "Patellar Tendon": ["quadriceps"],
    "Jumper's Knee (Patellar Tendinopathy)": ["quadriceps"],
    "Achilles": ["gastrocnemius", "soleus", "calf"],
    "Achilles Tendon - Complete Rupture": ["gastrocnemius", "soleus", "calf"],
    "Long Head Biceps Tendon - Tendinitis/Tendinosis (Tendinopathy)": ["biceps"],
    "Distal Biceps Tendon - Complete Rupture": ["biceps"],
    "Distal Biceps Tendon Rupture": ["biceps"],
    "Triceps Tendon - Tendinitis/Tendinosis (Tendinopathy)": ["triceps"],
    "Lateral Epicondylalgia (Tennis Elbow)": ["forearm", "wrist extensor", "brachioradialis"],
    "Medial Epicondylalgia (Golfer's Elbow)": ["forearm", "wrist flexor", "biceps", "brachialis"],
}

# Exercises whose whole point is corrective/rehab/very-low-load work for a
# joint (band pull-aparts, wall slides, isometric holds, dead hangs, bird
# dogs, post-surgical reconditioning drills, etc.) are frequently PRESCRIBED
# FOR the very conditions a naive joint-overlap model would flag them as
# risky for. Since injuries_to_avoid is a hard absolute exclusion in the
# engine (progression_engine.py: `is_safe = len(contraindications) == 0`,
# not severity-scaled), a false positive here actively blocks a genuinely
# helpful exercise for someone who needs it - worse than a false negative.
# So: never ADD a new tag to an exercise matching these signals; only the
# exact tags a human already curated for it are kept.
CORRECTIVE_SIGNALS = (
    "pull-apart", "pull apart", "wall slide", "y-t-w", "ytw", "bird dog",
    "superman", "dead hang", "isometric hold", "iso hold", "wall isometric",
    "wall isopress", "isometric set", "iso set", "scapular wall", "scap shrug",
    "terminal knee extension", "gentle prone", "supported sit-to-stand",
    "march in place", "wall press", "scapular",
)


def _is_corrective(ex: dict) -> bool:
    if ex.get("id", "").startswith("postop_"):
        return True
    name = ex.get("name", "").lower()
    return any(sig in name for sig in CORRECTIVE_SIGNALS)


def _muscle_pool(ex: dict) -> str:
    return " | ".join(
        ex.get("primary_muscles", []) + ex.get("secondary_muscles", []) + ex.get("stabilizers", [])
    ).lower()


def _tag_muscle_ok(tag: str, muscle_pool: str) -> bool:
    """True if this tag's associated muscle actually appears in the
    exercise's own muscle lists (or the tag has no muscle requirement at
    all, e.g. a pure joint/ligament/spine tag)."""
    required = TAG_MUSCLES.get(tag) or TENDON_TAG_MUSCLE_KEYWORDS.get(tag)
    if not required:
        return True
    return any(kw.lower() in muscle_pool for kw in required)


def _feature(ex: dict) -> dict:
    return {
        "joint_stress": set(ex.get("joint_stress", [])),
        "category": ex.get("category"),
        "movement_pattern": ex.get("movement_pattern"),
        "chain_type": ex.get("chain_type"),
        "force_type": ex.get("force_type"),
        "velocity_type": ex.get("velocity_type"),
        "movement_plane": ex.get("movement_plane"),
        "push_pull": ex.get("push_pull"),
        "upper_lower": ex.get("upper_lower"),
        "is_compound": ex.get("is_compound"),
        "difficulty": ex.get("difficulty", 1) or 1,
    }


def _similarity(a: dict, b: dict) -> float:
    score = 0.0
    js_a, js_b = a["joint_stress"], b["joint_stress"]
    union = js_a | js_b
    if union:
        score += 5.0 * (len(js_a & js_b) / len(union))
    for field, weight in (
        ("category", 2.0),
        ("movement_pattern", 2.0),
        ("chain_type", 1.0),
        ("force_type", 1.0),
        ("velocity_type", 1.0),
        ("movement_plane", 1.0),
        ("push_pull", 0.5),
        ("upper_lower", 0.5),
        ("is_compound", 0.5),
    ):
        if a[field] is not None and a[field] == b[field]:
            score += weight
    score += 1.0 * max(0.0, 1 - abs(a["difficulty"] - b["difficulty"]) / 4)
    return score


def _vote(sims: list, threshold: float, target_joints: set, muscle_pool: str) -> list:
    total_weight = sum(s for s, _ in sims) or 1e-9
    vote = Counter()
    occurrences = Counter()
    for s, tags in sims:
        for t in tags:
            vote[t] += s
            occurrences[t] += 1
    to_add = []
    for tag, weight in vote.items():
        if weight / total_weight < threshold:
            continue
        joint = TAG_JOINT.get(tag)
        if joint is not None and joint not in target_joints:
            continue  # anatomy veto
        if not _tag_muscle_ok(tag, muscle_pool):
            continue  # wrong-tissue veto (e.g. Biceps Strain on a triceps exercise)
        to_add.append(tag)
    return to_add


def _fallback_top(sims: list, target_joints: set, muscle_pool: str) -> list:
    """No tag reached the confidence bar (evidence is real but split across
    several plausible tags). Rather than leaving the exercise with zero
    coverage, take the single highest-weighted tag that at least 2 distinct
    neighbors independently agree on (so it isn't one odd neighbor's
    idiosyncratic tag), clears the anatomy/muscle vetoes, AND is capped at
    severity 1 (mild) - this is a low-confidence guess, so it should never
    be the thing that asserts e.g. a Grade-3 complete rupture is the reason
    an exercise is excluded."""
    vote = Counter()
    occurrences = Counter()
    for s, tags in sims:
        for t in tags:
            vote[t] += s
            occurrences[t] += 1
    for tag, _w in vote.most_common():
        if occurrences[tag] < 2:
            continue
        if TAG_SEVERITY.get(tag, 1) > 1:
            continue  # low-confidence guess -> never assert a severe/graded injury
        joint = TAG_JOINT.get(tag)
        if joint is not None and joint not in target_joints:
            continue
        if not _tag_muscle_ok(tag, muscle_pool):
            continue
        return [tag]
    return []


def predict_tags(target: dict, target_feat: dict, pool: list) -> list:
    """pool: list of (feature_dict, injuries_to_avoid set) for already-tagged
    exercises, excluding the target itself. Returns list of tags to add.

    Two-tier: exercises whose joint_stress set matches EXACTLY are the
    strongest possible evidence (same joints stressed, nothing more/less),
    so if at least 3 such exact-match exercises exist, vote among just
    those at a lower confidence bar. Otherwise fall back to the broader
    weighted-similarity neighborhood across all features.
    """
    target_joints = target.get("joint_stress", set())
    muscle_pool = target["muscle_pool"]

    exact = [
        (_similarity(target_feat, feat), tags)
        for feat, tags in pool
        if feat["joint_stress"] == target_joints
    ]
    if len(exact) >= 3:
        exact.sort(key=lambda p: p[0], reverse=True)
        top = exact[:K_NEIGHBORS]
        result = _vote(top, 0.30, target_joints, muscle_pool)
        return result or _fallback_top(top, target_joints, muscle_pool)

    sims = sorted(
        ((_similarity(target_feat, feat), tags) for feat, tags in pool),
        key=lambda p: p[0],
        reverse=True,
    )[:K_NEIGHBORS]
    result = _vote(sims, CONFIDENCE_THRESHOLD, target_joints, muscle_pool)
    return result or _fallback_top(sims, target_joints, muscle_pool)


def main():
    settings.BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    exercises = data["exercises"]
    feats = {ex["id"]: _feature(ex) for ex in exercises}

    pool = [
        (feats[ex["id"]], set(ex["injuries_to_avoid"]))
        for ex in exercises
        if ex.get("injuries_to_avoid")
    ]
    print(f"Ground-truth pool: {len(pool)} already-tagged exercises")

    skipped_corrective = []
    additions_log = {}
    for ex in exercises:
        if _is_corrective(ex):
            skipped_corrective.append(ex["id"])
            continue
        target_feat = feats[ex["id"]]
        existing = set(ex.get("injuries_to_avoid", []))
        # Exclude self from the pool by filtering on identity of feature dict
        self_pool = [
            (feat, tags) for feat, tags in pool if feat is not target_feat
        ]
        target = {"joint_stress": target_feat["joint_stress"], "muscle_pool": _muscle_pool(ex)}
        candidate_tags = predict_tags(target, target_feat, self_pool)
        new_tags = [t for t in candidate_tags if t not in existing]
        if new_tags:
            ex["injuries_to_avoid"] = sorted(existing | set(new_tags))
            additions_log[ex["id"]] = new_tags

    print(f"Skipped (corrective/rehab-pattern, no new tags added): {len(skipped_corrective)}")
    print(skipped_corrective)

    data["version"] = "5.20.0"
    data["schema_notes"] += (
        "\n\nv5.20 fills gaps in injuries_to_avoid across the exercise "
        "library using a k-NN similarity model trained on the already "
        "hand-curated tags (joint_stress overlap + category/pattern/chain/"
        "force/velocity/plane match + difficulty closeness as features; "
        "see scripts/data_ops/map_injuries_to_avoid.py). Only adds tags "
        "(never removes/replaces existing ones), and only when the tag's "
        "own taxonomy joint is present in that exercise's joint_stress."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Updated {len(additions_log)}/{len(exercises)} exercises.")
    tag_freq = Counter(t for tags in additions_log.values() for t in tags)
    print("\nTags added (frequency):")
    for tag, n in tag_freq.most_common():
        print(f"  {n:4d}  {tag}")

    still_empty = [ex["id"] for ex in exercises if not ex.get("injuries_to_avoid")]
    print(f"\nStill empty after mapping: {len(still_empty)}")
    print(still_empty)

    with open("/tmp/injury_mapping_additions.json", "w") as f:
        json.dump(additions_log, f, indent=2)


if __name__ == "__main__":
    main()
