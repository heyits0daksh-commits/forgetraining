"""
Tests for grappling_playbook.py (Iowa State Grappling S&C Playbook) and its
two wiring points: the standalone /api/v1/grappling-playbook reference
endpoint, and generate-program's grappling_guidance block for the four
sports the playbook covers.
"""
from backend.services.grappling_playbook import (
    GRAPPLING_SPORTS,
    LEVELS,
    LEVEL_LOADING,
    WAVE_PROGRESSION,
    armor_protocol_for_joint,
    discipline_supplemental_block,
    grappling_playbook_reference,
    level_loading_table,
    macrocycle_phase_for_week,
    session_card,
    wave_week_pct,
    autoregulation_status_for_readiness,
)


def test_every_level_has_a_full_seven_quality_loading_grid():
    qualities = {
        "Max Strength", "Explosive/Ballistic", "Grappling Accessory",
        "Hypertrophy/Isolation", "Loaded Carry / Grip",
        "Olympic / Power Derivative", "Prehab / Armor",
    }
    for level in LEVELS:
        assert level in LEVEL_LOADING
        assert set(LEVEL_LOADING[level]["qualities"].keys()) == qualities


def test_every_grappling_sport_has_a_supplemental_block():
    for sport in GRAPPLING_SPORTS:
        block = discipline_supplemental_block(sport)
        assert block is not None
        assert len(block["additions"]) == 5


def test_non_grappling_sport_has_no_supplemental_block():
    assert discipline_supplemental_block("Special Forces") is None
    assert discipline_supplemental_block("Rock Climbing") is None


def test_wave_week_pct_covers_all_four_weeks_every_level():
    for level in LEVELS:
        for week in range(1, 5):
            assert wave_week_pct(level, week) == WAVE_PROGRESSION[level][f"week_{week}"]


def test_wave_week_pct_clamps_out_of_range_weeks():
    assert wave_week_pct("Intermediate", 0) == wave_week_pct("Intermediate", 1)
    assert wave_week_pct("Intermediate", 99) == wave_week_pct("Intermediate", 4)


def test_wave_week_pct_unknown_level_returns_none():
    assert wave_week_pct("Grandmaster", 1) is None


def test_armor_protocol_resolves_lower_back_and_hip_to_combined_slot():
    combined = armor_protocol_for_joint("Low Back / Hip")
    assert armor_protocol_for_joint("Lower Back") == combined
    assert armor_protocol_for_joint("Hip") == combined


def test_armor_protocol_direct_joints():
    assert armor_protocol_for_joint("Shoulder")["template"].startswith("Band pull-aparts")
    assert armor_protocol_for_joint("Knee") is not None
    assert armor_protocol_for_joint("Neck") is not None
    assert armor_protocol_for_joint("Ankle") is not None


def test_macrocycle_phase_for_week_hits_named_deload_weeks():
    assert macrocycle_phase_for_week(4)["phase"] == "Deload / Test"
    assert macrocycle_phase_for_week(8)["phase"] == "Deload / Retest"
    assert macrocycle_phase_for_week(12)["phase"] == "Deload"
    assert macrocycle_phase_for_week(16)["phase"] == "Peak / Competition"
    assert macrocycle_phase_for_week(2)["phase"] == "General Prep"
    assert macrocycle_phase_for_week(10)["phase"] == "Power-Strength"


def test_macrocycle_phase_out_of_range_returns_none():
    assert macrocycle_phase_for_week(17) is None
    assert macrocycle_phase_for_week(0) is None


def test_session_card_returns_ordered_blocks():
    blocks = session_card("Olympic Power")
    assert blocks[0] == "Hang pull/clean progression"
    assert blocks[-1] == "Optional prehab"
    assert session_card("Not A Real Card") is None


def test_autoregulation_status_bands():
    assert autoregulation_status_for_readiness(90)["status"] == "Green"
    assert autoregulation_status_for_readiness(65)["status"] == "Yellow"
    assert autoregulation_status_for_readiness(40)["status"] == "Orange"
    assert autoregulation_status_for_readiness(10)["status"] == "Red"


def test_reference_filters_to_requested_sport_and_level():
    ref = grappling_playbook_reference(sport="BJJ", level="Advanced")
    assert ref["discipline_supplemental_block"] == discipline_supplemental_block("BJJ")
    assert ref["level_loading"] == level_loading_table("Advanced")
    assert ref["wave_progression"] == WAVE_PROGRESSION["Advanced"]


def test_reference_omits_sport_and_level_filters_by_default():
    ref = grappling_playbook_reference()
    assert ref["discipline_supplemental_block"] is None
    assert ref["level_loading"] == LEVEL_LOADING
    assert ref["wave_progression"] == WAVE_PROGRESSION


def test_grappling_playbook_endpoint(client):
    r = client.get("/api/v1/grappling-playbook", params={"sport": "Judo", "level": "Novice"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discipline_supplemental_block"]["demands"].startswith("Grip fighting")
    assert body["level_loading"]["key_rule"] == "Own the patterns before loading them"


def test_grappling_playbook_endpoint_no_filters(client):
    r = client.get("/api/v1/grappling-playbook")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["discipline_supplemental_block"] is None
    assert len(body["macrocycle_phases"]) == 8
    assert len(body["session_cards"]) == 7


def test_generate_program_includes_grappling_guidance_for_wrestling(client):
    r = client.post(
        "/api/v1/generate-program",
        json={"sport": "Wrestling", "experience_level": "Intermediate", "weeks": 4, "days_per_week": 3},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    guidance = body["grappling_guidance"]
    assert guidance is not None
    assert guidance["sport"] == "Wrestling"
    assert guidance["supplemental_block"] is not None
    assert guidance["level_loading"]["qualities"]["Max Strength"]["pct_1rm"] == "75-87%"


def test_generate_program_omits_grappling_guidance_for_non_grappling_sport(client):
    r = client.post(
        "/api/v1/generate-program",
        json={"sport": "Special Forces", "experience_level": "Intermediate", "weeks": 4, "days_per_week": 3},
    )
    assert r.status_code == 200, r.text
    assert r.json()["grappling_guidance"] is None
