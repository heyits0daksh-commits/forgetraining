"""
Tests for sc_template_library.py (the ten FORGE S&C Template Libraries -
grappling/striking/MMA/climbing/rugby/special_forces/hyrox/powerlifting/
natural_bodybuilding/strength_hypertrophy, 1,730 named templates total)
and its two wiring points: the /api/v1/sc-templates (list) +
/api/v1/sc-templates/{global_id} (detail) endpoints, and
generate-program's sc_template_guidance block.
"""
from backend.services.sc_template_library import (
    LIBRARY,
    LIBRARY_SPORTS,
    get_template,
    library_summary,
    list_templates,
    sports_covered,
    templates_for_program,
)
from backend.services.program_builder import build_template_fidelity_program
from backend.services.progression_engine import engine


def test_total_template_count_across_all_ten_libraries():
    assert len(LIBRARY.templates_by_global_id) == 1730
    assert len(LIBRARY.templates_by_library["grappling"]) == 150
    assert len(LIBRARY.templates_by_library["striking"]) == 110
    assert len(LIBRARY.templates_by_library["mma"]) == 150
    assert len(LIBRARY.templates_by_library["climbing"]) == 200
    assert len(LIBRARY.templates_by_library["rugby"]) == 440
    assert len(LIBRARY.templates_by_library["special_forces"]) == 200
    assert len(LIBRARY.templates_by_library["hyrox"]) == 120
    assert len(LIBRARY.templates_by_library["powerlifting"]) == 120
    assert len(LIBRARY.templates_by_library["natural_bodybuilding"]) == 120
    assert len(LIBRARY.templates_by_library["strength_hypertrophy"]) == 120


def test_global_ids_are_namespaced_and_unambiguous():
    # Both the grappling and striking source files independently number
    # their templates starting at "SC-001" - global_id must disambiguate.
    grappling_first = get_template("grappling:SC-001")
    striking_first = get_template("striking:SC-001")
    assert grappling_first is not None and striking_first is not None
    assert grappling_first["id"] == striking_first["id"] == "SC-001"
    assert grappling_first["name"] != striking_first["name"]


def test_get_template_unknown_id_returns_none():
    assert get_template("grappling:NOT-REAL") is None
    assert get_template("not_a_library:SC-001") is None


def test_sports_covered_matches_known_sport_names():
    covered = sports_covered()
    for sport in [
        "BJJ", "Judo", "Wrestling", "Boxing", "Muay Thai", "Kickboxing", "MMA",
        "Rock Climbing", "Rugby", "Special Forces / Military Operator", "HYROX",
        "Powerlifting (Squat / Bench / Deadlift)",
        "General Physique / Natural Bodybuilding",
        "General / Off-Season-GPP for Combat Athletes",
    ]:
        assert sport in covered


def test_sanda_has_templates_in_both_grappling_and_striking():
    assert set(LIBRARY_SPORTS["Sanda"]) == {"grappling", "striking"}
    assert len(list_templates(sport="Sanda", library="grappling")) > 0
    assert len(list_templates(sport="Sanda", library="striking")) > 0


def test_list_templates_filters_combine_with_and():
    results = list_templates(sport="BJJ", level="Intermediate", include_generic=False)
    assert len(results) > 0
    for t in results:
        assert t["sport"] == "BJJ"
        assert t["level"] == "Intermediate"


def test_list_templates_includes_generic_pool_by_default():
    with_generic = list_templates(sport="BJJ", level="Novice")
    without_generic = list_templates(sport="BJJ", level="Novice", include_generic=False)
    assert len(with_generic) > len(without_generic)
    assert any(t["sport"] == "General / Cross-Sport (Grappling)" for t in with_generic)


def test_list_templates_library_filter_ignores_sport_scope():
    mma_only = list_templates(library="mma")
    assert len(mma_only) == 150
    assert all(t["library"] == "mma" for t in mma_only)


def test_list_templates_single_sport_libraries_have_no_generic_pool():
    with_generic = list_templates(sport="HYROX", level="Novice")
    without_generic = list_templates(sport="HYROX", level="Novice", include_generic=False)
    assert len(with_generic) == len(without_generic) > 0


def test_list_templates_unmatched_filters_return_empty_list():
    assert list_templates(sport="Soccer") == []
    assert list_templates(sport="BJJ", level="Grandmaster") == []


def test_templates_for_program_returns_empty_for_uncovered_sport():
    assert templates_for_program("Soccer", "Advanced") == []


def test_templates_for_program_respects_limit_and_matches_level():
    matches = templates_for_program("MMA", "Advanced", days_per_week=3, limit=5)
    assert 0 < len(matches) <= 5
    for t in matches:
        assert t["level"] == "Advanced"


def test_templates_for_program_covers_newly_added_libraries():
    for sport, level in [
        ("Rugby", "Advanced"),
        ("HYROX", "Novice"),
        ("Rock Climbing", "Intermediate"),
        ("Special Forces / Military Operator", "Novice Operator"),
        ("Powerlifting (Squat / Bench / Deadlift)", "Intermediate"),
    ]:
        matches = templates_for_program(sport, level, limit=5)
        assert len(matches) > 0, f"expected template matches for {sport}/{level}"


def test_library_summary_all_and_single():
    all_libs = library_summary()
    assert set(all_libs.keys()) == {
        "grappling", "striking", "mma", "climbing", "rugby", "special_forces",
        "hyrox", "powerlifting", "natural_bodybuilding", "strength_hypertrophy",
    }
    striking = library_summary("striking")
    assert striking["library"] == "striking"
    assert striking["template_count"] == 110
    assert library_summary("not_a_library") == {}


def test_get_template_full_shape_has_days_and_exercises():
    tpl = get_template("mma:MMA-SC-001")
    assert tpl["days"], "template should have at least one training day"
    assert tpl["days"][0]["exercises"], "day should list at least one exercise"


def test_sc_templates_list_endpoint(client):
    r = client.get("/api/v1/sc-templates", params={"sport": "Wrestling", "level": "Beginner"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body["templates"]) > 0
    assert "MMA" in body["sports_covered"]
    assert body["libraries"]["grappling"]["template_count"] == 150


def test_sc_templates_detail_endpoint(client):
    r = client.get("/api/v1/sc-templates/mma:MMA-SC-001")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == get_template("mma:MMA-SC-001")["name"]


def test_sc_templates_detail_endpoint_404_for_unknown_id(client):
    r = client.get("/api/v1/sc-templates/grappling:NOT-REAL")
    assert r.status_code == 404


def test_generate_program_includes_sc_template_guidance_for_covered_sport(client):
    r = client.post(
        "/api/v1/generate-program",
        json={"sport": "MMA", "experience_level": "Intermediate", "weeks": 4, "days_per_week": 3},
    )
    assert r.status_code == 200, r.text
    guidance = r.json()["sc_template_guidance"]
    assert guidance is not None
    assert guidance["sport"] == "MMA"
    assert len(guidance["matching_templates"]) > 0
    for t in guidance["matching_templates"]:
        assert t["library"] == "mma"


def test_build_template_fidelity_unknown_id_returns_none():
    assert build_template_fidelity_program(engine, "grappling:NOT-REAL", equipment_available=["Bodyweight"], injuries=[]) is None


def test_build_template_fidelity_keeps_every_exercise_with_full_equipment_no_injury():
    tpl = LIBRARY.templates_by_library["mma"][0]
    full_equip = [
        "Trap Bar", "Seal Row Bench", "Landmine", "Safety Squat Bar",
        "Reverse Hyper", "Dumbbell", "Barbell", "Medicine Ball", "Kettlebell",
    ]
    result = build_template_fidelity_program(
        engine, tpl["global_id"], equipment_available=full_equip, injuries=[],
    )
    assert result["substitutions_made"] == 0
    assert result["exercises_excluded"] == 0
    for day in result["days"]:
        for ex in day["exercises"]:
            assert ex["template_source"] is True
    template_names = [e["name"] for d in tpl["days"] for e in d["exercises"]]
    result_names = [e["name"] for d in result["days"] for e in d["exercises"]]
    assert result_names == template_names


def test_build_template_fidelity_substitutes_when_equipment_missing():
    tpl = LIBRARY.templates_by_library["mma"][0]
    result = build_template_fidelity_program(
        engine, tpl["global_id"], equipment_available=["Bodyweight"], injuries=[],
    )
    assert result["substitutions_made"] > 0
    substituted = [
        ex for day in result["days"] for ex in day["exercises"]
        if ex.get("substituted_for")
    ]
    assert substituted
    for ex in substituted:
        assert "Equipment not available" in ex["substitution_reason"]


def test_build_template_fidelity_endpoint(client):
    tpl = LIBRARY.templates_by_library["mma"][0]
    r = client.post(
        f"/api/v1/sc-templates/{tpl['global_id']}/build",
        json={"equipment_available": ["Bodyweight"], "injuries": []},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["global_id"] == tpl["global_id"]
    assert "days" in body


def test_build_template_fidelity_endpoint_404_for_unknown_id(client):
    r = client.post(
        "/api/v1/sc-templates/grappling:NOT-REAL/build",
        json={"equipment_available": ["Bodyweight"], "injuries": []},
    )
    assert r.status_code == 404


def test_generate_program_omits_sc_template_guidance_for_uncovered_sport(client):
    r = client.post(
        "/api/v1/generate-program",
        json={"sport": "Soccer", "experience_level": "Intermediate", "weeks": 4, "days_per_week": 3},
    )
    assert r.status_code == 200, r.text
    assert r.json()["sc_template_guidance"] is None


# ------------------------------------------------------------
# fuzzy_resolve_exercise_name - covers the equipment-selection bug where a
# template's own wording ("Front Squat (Rack)", "Chest-Supported DB Row",
# "Weighted Hanging Knee Raise (Dip Belt)") didn't exact-match exercises.json's
# name for the same lift, so it never got equipment/injury-checked at all
# and just showed up "Unverified" with no chance of a substitution.
# ------------------------------------------------------------
from backend.services.sc_template_library import fuzzy_resolve_exercise_name


def test_fuzzy_resolve_bridges_equipment_only_naming_gap():
    cases = {
        "Front Squat (Rack)": "Barbell Front Squat",
        "Chest-Supported DB Row": "Chest Supported Row",
        "Weighted Hanging Knee Raise (Dip Belt)": "Hanging Knee Raise",
    }
    for query, expected in cases.items():
        resolved = fuzzy_resolve_exercise_name(query, engine.exercises_by_id)
        assert resolved is not None, query
        assert resolved["name"] == expected, query


def test_fuzzy_resolve_never_bridges_a_real_movement_difference():
    # "Pause"/"Tempo"/"Zombie" are technique words, not equipment words -
    # these must stay unresolved rather than silently guessing a different
    # lift just because the token-count difference is the same size as the
    # genuine equipment-only case above.
    resolved = fuzzy_resolve_exercise_name("Squat Variant That Does Not Exist", engine.exercises_by_id)
    assert resolved is None


def test_fuzzy_resolve_returns_none_for_genuinely_absent_exercise():
    # "Belt Squat Lunge Combo" isn't a real exercise and has no equipment-
    # only-diff sibling to bridge to - must stay unresolved, not get
    # matched to a different lift. ("Trap-Bar Squat" used to be this
    # test's example, back when it genuinely had no exercises.json match -
    # v5.36 (batch21) added a real "Trap Bar Squat" exercise to close that
    # gap, so it now correctly resolves and no longer illustrates "absent".)
    assert fuzzy_resolve_exercise_name("Belt Squat Lunge Combo", engine.exercises_by_id) is None


def test_build_template_fidelity_resolves_and_substitutes_fuzzy_named_slots():
    # End-to-end: a template exercise whose name only exact-matches after
    # the fuzzy fallback should still go through the normal equipment
    # check, and get substituted (not left "Unverified") when the athlete
    # has no matching equipment.
    tpl = LIBRARY.templates_by_library["mma"][0]
    result = build_template_fidelity_program(
        engine, tpl["global_id"], equipment_available=["Bodyweight"], injuries=[],
    )
    # Every exercise the fuzzy resolver can actually match to real exercise
    # data must have gone through a real check (verified True, possibly
    # substituted/excluded) - never silently left as a raw "Unverified"
    # passthrough it could have avoided.
    for day in result["days"]:
        for ex in day["exercises"]:
            if ex.get("verified") is False:
                assert fuzzy_resolve_exercise_name(ex["name"], engine.exercises_by_id) is None


def test_fuzzy_resolve_never_bridges_an_equipment_swap():
    # v5.35 regression: an earlier widening of the token-diff algorithm let
    # ANY symmetric difference made of equipment vocabulary through, which
    # silently matched genuinely different tools to each other instead of
    # refusing to guess - the opposite of what the equipment/injury gate
    # needs. Each of these pairs differs by two competing _BASE_TOOL_WORDS
    # (e.g. dumbbell vs cable), so they must never resolve to one another,
    # no matter how short the token-diff looks.
    swaps = [
        "DB Lateral Raise",       # must not become "Cable Lateral Raise"
        "Barbell Curl",           # must not become "EZ Bar Curl" (aliased
                                   # to its own Standing Barbell Curl instead)
        "Preacher Curl (Machine)",  # must not become "Dumbbell Preacher Curl"
        "Assisted Pull-Up Machine",  # must not become "Band-Assisted Pull-Up"
    ]
    for query in swaps:
        resolved = fuzzy_resolve_exercise_name(query, engine.exercises_by_id)
        if resolved is not None:
            assert resolved["name"] != {
                "DB Lateral Raise": "Cable Lateral Raise",
                "Barbell Curl": "EZ Bar Curl",
                "Preacher Curl (Machine)": "Dumbbell Preacher Curl",
                "Assisted Pull-Up Machine": "Band-Assisted Pull-Up",
            }[query], query


def test_fuzzy_resolve_never_invents_an_unstated_equipment_requirement():
    # "belt" and "vest" are real, different props for adding load - neither
    # should ever be bridged as an implicit default the way "barbell" is
    # for a plain "Front Squat". A generic "Box Jump" must not turn into
    # "Weighted Vest Box Jump" and invent a vest requirement the template
    # never asked for.
    assert fuzzy_resolve_exercise_name("Box Jump", engine.exercises_by_id) is None


def test_fuzzy_resolve_handles_common_colloquial_lift_names():
    # These are common gym names whose exercises.json equivalent carries
    # its own base-tool word too ("Barbell Back Squat"), so neither name is
    # a token subset of the other - the token-diff algorithm alone can't
    # bridge them safely, hence the small hand-checked alias list.
    cases = {
        "Back Squat": "Barbell Back Squat",
        "Bench Press": "Flat Bench Press",
        "Reverse Hyper": "Reverse Hyperextension",
    }
    for query, expected in cases.items():
        resolved = fuzzy_resolve_exercise_name(query, engine.exercises_by_id)
        assert resolved is not None, query
        assert resolved["name"] == expected, query
