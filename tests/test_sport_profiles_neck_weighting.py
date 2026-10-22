"""
Regression coverage for sport_profiles.SPORT_QUALITY_PROFILES neck weighting.

Bug (fixed): the manual gives neck training its own universal table
(frequency + per-sport rationale) exactly parallel to how it treats grip,
but before this pass Grip Strength/Grip Endurance was weighted into nearly
every sport's SPORT_QUALITY_PROFILES row while Neck Strength appeared in
exactly one (Boxing). That meant a neck exercise's real Neck Strength
quality score contributed ZERO to blended_transfer_score for Wrestling,
Judo, Sambo, and Rugby - despite the manual training their necks 3x+/week
for reasons it states explicitly (Wrestling's own "Primary Physical
Qualities" line names "a bulletproof neck").

These tests pin the corrected behavior: sports the manual trains neck
work into 3x+/week carry a real Neck Strength weight, and Rock Climbing
(which the manual explicitly says has neck as "not a primary demand")
correctly has none.
"""
from backend.services.sport_profiles import SPORT_QUALITY_PROFILES, quality_overlap_score


def test_high_frequency_neck_sports_have_neck_strength_weight():
    """Manual trains neck 3x/week+ for these sports with explicit rationale
    (Wrestling: named Primary Physical Quality; Sambo: "non-negotiable";
    Judo: injury risk; Rugby: injury-prevention pillar; Boxing: concussion
    risk) - all must carry a real (non-trivial) weight."""
    for sport in ["Wrestling", "Sambo", "Judo", "Rugby", "Boxing"]:
        weight = SPORT_QUALITY_PROFILES[sport].get("Neck Strength", 0)
        assert weight >= 40, f"{sport} should weight Neck Strength >= 40, got {weight}"


def test_wrestling_has_the_highest_neck_weight():
    """Wrestling's manual chapter is the only one naming neck strength
    directly in its Primary Physical Qualities line ("a bulletproof
    neck") - it should outweigh every other sport."""
    wrestling_weight = SPORT_QUALITY_PROFILES["Wrestling"]["Neck Strength"]
    for sport, profile in SPORT_QUALITY_PROFILES.items():
        if sport == "Wrestling":
            continue
        assert profile.get("Neck Strength", 0) <= wrestling_weight


def test_rock_climbing_has_no_neck_strength_weight():
    """Manual: neck is "not a primary demand of the sport" for climbing
    (1x/week, maintenance only) - deliberately left out of the model."""
    assert "Neck Strength" not in SPORT_QUALITY_PROFILES["Rock Climbing"]


def test_neck_exercise_now_scores_nonzero_for_wrestling():
    """A pure neck-training exercise (no grip/leg/push qualities) must
    contribute real transfer score to Wrestling now that the weight
    exists, not just whatever incidental overlap other qualities gave it."""
    pure_neck_qualities = {"Neck Strength": 80}
    score = quality_overlap_score(pure_neck_qualities, "Wrestling")
    assert score > 0
