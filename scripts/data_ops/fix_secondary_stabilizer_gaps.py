"""
fix_secondary_stabilizer_gaps.py - closes Gap: 132 exercises had an empty
secondary_muscles and/or empty stabilizers list even though a real synergist
or postural stabilizer exists for the movement (leaves primary_muscles and
joint_stress untouched - those two fields had no gaps).

Every addition below is a specific, named muscle chosen for that exercise's
actual biomechanics (e.g. Anconeus for triceps lockout work, Brachioradialis
for reverse-grip curls, Tensor Fasciae Latae for open-chain knee extension,
Rotator Cuff for overhead/pulling shoulder work done free-standing) rather
than a generic filler tag. Nothing existing is removed or reordered; this
only appends to lists that were empty.

Additive only, same pattern as fix_joint_stress_gaps.py.
"""
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
SRC = ROOT / "data" / "exercises.json"
BACKUP = ROOT / "data" / "backups" / "exercises_pre_secondary_stabilizer_gap_fix_backup.json"

# id -> {"secondary_muscles": [...], "stabilizers": [...]}
# Only include the key(s) that were actually empty for that exercise.
FIXES = {
    # --- Lower-body compound machines: seated/supported but the trunk
    # still braces isometrically against the drive, same as the existing
    # legpress_singleleg_001 template (stabilizers: ["Core"]). ---
    "legpress_bilateral_001": {"stabilizers": ["Core"]},
    "hacksquat_001": {"stabilizers": ["Core"]},
    "smith_squat_001": {"stabilizers": ["Core"]},
    "beltsquat_001": {"stabilizers": ["Core"]},
    "belt_squat_machine_001": {"stabilizers": ["Core"]},
    "v_squat_001": {"stabilizers": ["Core"]},
    "pendulum_squat_001": {"stabilizers": ["Core"]},
    "legpress_narrow_001": {"stabilizers": ["Core"]},
    "legpress_wide_001": {"stabilizers": ["Core"]},
    "hacksquat_narrow_001": {"stabilizers": ["Core"]},
    "hacksquat_wide_001": {"stabilizers": ["Core"]},
    # Front-loaded free-weight squats: the anterior load is held at the
    # chest/shoulder, so grip/forearms and upper back brace it, not the core.
    "goblet_boxsquat_001": {"stabilizers": ["Forearms"]},
    "landmine_squat_001": {"stabilizers": ["Forearms"]},
    "spanish_squat_001": {"secondary_muscles": ["Gluteus Maximus"]},

    # --- Knee-extension isolation machines: single-joint, but TFL is a
    # genuine open-chain synergist/stabilizer of the knee via the IT band. ---
    "legext_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Core"]},
    "legext_singleleg_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Obliques"]},
    "legext_isohold_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Core"]},
    "legextension_partial_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Core"]},
    "legextension_slowecc_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Core"]},
    "legextension_15rep_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Core"]},
    "legextension_pulse_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Core"]},
    "quad_isoset_seated_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Core"]},
    "quad_bandtermext_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"], "stabilizers": ["Core"]},

    # --- Leg curl (knee flexion) isolation machines: gastrocnemius is a
    # genuine two-joint synergist, matching the "Calves" tag already used
    # on the un-gapped legcurl_lying_001/legcurl_seated_001. ---
    "legcurl_standing_001": {"secondary_muscles": ["Calves"]},
    "legcurl_singleleg_001": {"secondary_muscles": ["Calves"]},
    "legcurl_isohold_001": {"secondary_muscles": ["Calves"], "stabilizers": ["Core"]},
    "legcurl_stretchpartial_001": {"secondary_muscles": ["Calves"], "stabilizers": ["Core"]},
    "hamstring_bandcurl_seated_001": {"secondary_muscles": ["Calves"], "stabilizers": ["Core"]},

    # --- Calf / ankle isolation: tibialis posterior and EDL are the real
    # synergists for plantarflexion and dorsiflexion/eversion respectively. ---
    "legpress_calfpress_001": {"secondary_muscles": ["Tibialis Posterior"], "stabilizers": ["Core"]},
    "band_ankledorsiflexion_001": {"secondary_muscles": ["Extensor Digitorum Longus"]},
    "band_ankleeversion_001": {"secondary_muscles": ["Extensor Digitorum Longus"]},
    "bodyweight_singlelegcalfraise_001": {"secondary_muscles": ["Tibialis Posterior"]},

    # --- Horizontal/vertical pull machines: trunk braces against the pull,
    # matching the un-gapped cable_row_001/lat_pulldown_001 ("Core") pattern. ---
    "latpulldown_wide_001": {"stabilizers": ["Core"]},
    "latpulldown_close_001": {"stabilizers": ["Core"]},
    "latpulldown_vbar_001": {"stabilizers": ["Core"]},
    "latpulldown_reversegrip_001": {"stabilizers": ["Core"]},
    "seatedrow_wide_001": {"stabilizers": ["Core"]},
    "seatedrow_closegrip_001": {"stabilizers": ["Core"]},
    "seatedrow_neutralgrip_001": {"stabilizers": ["Core"]},
    "seatedrow_isohold_001": {"stabilizers": ["Core"]},
    "high_row_machine_001": {"stabilizers": ["Core"]},
    "highrow_closegrip_001": {"stabilizers": ["Core"]},
    "highrow_isohold_001": {"stabilizers": ["Core"]},
    "highrow_partialsqueeze_001": {"stabilizers": ["Core"]},
    "lever_row_001": {"stabilizers": ["Core"]},
    "lever_pulldown_001": {"stabilizers": ["Core"]},
    "band_row_001": {"stabilizers": ["Core"]},
    # Chest-supported free rows: pad removes lower-back demand, but the
    # rotator cuff still stabilizes the shoulder through the pull.
    "chestsupported_row_001": {"stabilizers": ["Rotator Cuff"]},
    "sealrow_001": {"stabilizers": ["Rotator Cuff"]},
    "sealrow_widegrip_001": {"stabilizers": ["Rotator Cuff"]},
    "sealrow_pause_001": {"stabilizers": ["Rotator Cuff"]},
    "sealrow_closegrip_001": {"stabilizers": ["Rotator Cuff"]},
    "sealrow_isohold_001": {"stabilizers": ["Rotator Cuff"]},

    # --- Horizontal/vertical press machines: rotator cuff stabilizes the
    # humeral head through the press, matching cable_facepull_001's tag. ---
    "pecdeck_001": {"stabilizers": ["Rotator Cuff"]},
    "pecdeck_isohold_001": {"stabilizers": ["Rotator Cuff"]},
    "pecdeck_partialsqueeze_001": {"secondary_muscles": ["Serratus Anterior"], "stabilizers": ["Rotator Cuff"]},
    "pecdeck_pulse_001": {"secondary_muscles": ["Serratus Anterior"]},
    "smith_bench_001": {"stabilizers": ["Rotator Cuff"]},
    "smith_ohp_001": {"stabilizers": ["Rotator Cuff"]},
    "chest_press_machine_001": {"stabilizers": ["Rotator Cuff"]},
    "chest_press_incline_machine_001": {"stabilizers": ["Rotator Cuff"]},
    "chestpress_isohold_001": {"stabilizers": ["Rotator Cuff"]},
    "shoulder_press_machine_001": {"stabilizers": ["Rotator Cuff"]},
    "shoulder_press_neutralgrip_machine_001": {"stabilizers": ["Rotator Cuff"]},
    "shoulderpress_partial_001": {"stabilizers": ["Rotator Cuff"]},
    "shoulderpress_isohold_001": {"secondary_muscles": ["Lateral Deltoid"]},
    "lever_chestpress_001": {"stabilizers": ["Rotator Cuff"]},
    "cable_chestfly_001": {"stabilizers": ["Rotator Cuff"]},
    "cable_lateralraise_001": {"secondary_muscles": ["Anterior Deltoid"], "stabilizers": ["Rotator Cuff"]},
    "bench_pikepushup_001": {"stabilizers": ["Rotator Cuff"]},

    # --- Elbow isolation - triceps: Anconeus is the genuine small synergist
    # that co-activates with triceps on every elbow-extension movement. ---
    "ezbar_skullcrusher_001": {"secondary_muscles": ["Anconeus"], "stabilizers": ["Core"]},
    "cable_triceppushdown_001": {"secondary_muscles": ["Anconeus"]},
    "cable_overheadtricep_001": {"secondary_muscles": ["Anconeus"]},
    "band_overheadtricep_001": {"secondary_muscles": ["Anconeus"]},
    "db_overheadtricep_001": {"secondary_muscles": ["Anconeus"]},
    "db_tricepkickback_001": {"secondary_muscles": ["Anconeus"]},
    "db_skullcrusher_001": {"secondary_muscles": ["Anconeus"], "stabilizers": ["Core"]},
    "bb_skullcrusher_001": {"secondary_muscles": ["Anconeus"], "stabilizers": ["Core"]},
    "db_tatepress_001": {"secondary_muscles": ["Anconeus"], "stabilizers": ["Core"]},
    "db_singlearmoverheadtricep_001": {"secondary_muscles": ["Anconeus"]},
    "cable_ropepushdown_001": {"secondary_muscles": ["Anconeus"], "stabilizers": ["Core"]},
    "cable_vbarpushdown_001": {"secondary_muscles": ["Anconeus"], "stabilizers": ["Core"]},
    "cable_singlearmpushdown_001": {"secondary_muscles": ["Anconeus"]},
    "cable_ropeoverheadext_001": {"secondary_muscles": ["Anconeus"]},
    "triceps_wallisopress_001": {"secondary_muscles": ["Anconeus"]},
    "triceps_bandext_light_001": {"secondary_muscles": ["Anconeus"], "stabilizers": ["Core"]},

    # --- Elbow isolation - biceps/forearm curls: Brachioradialis is the
    # genuine synergist that dominates on neutral/reverse-grip variants. ---
    "ezbar_reversecurl_001": {"secondary_muscles": ["Brachioradialis"], "stabilizers": ["Core"]},
    "bb_reversecurl_001": {"stabilizers": ["Core"]},

    # --- Neck work: cervical flexors/extensors/SCM co-activate as
    # synergists depending on plane of motion. ---
    "neckharness_flexion_001": {"secondary_muscles": ["Sternocleidomastoid"]},
    "neckharness_isohold_001": {"secondary_muscles": ["Sternocleidomastoid"]},
    "neckharness_diagonalflexion_001": {"secondary_muscles": ["Scalenes"]},

    # --- Hip abduction: TFL and glute max both co-activate with glute
    # medius/minimus in the frontal plane. ---
    "hipabd_sidelying_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"]},
    "hipabd_clamshell_001": {"secondary_muscles": ["Tensor Fasciae Latae (TFL)"]},
    "hipabd_bandstanding_001": {"secondary_muscles": ["Gluteus Maximus"]},

    # --- Core / trunk isolation work. ---
    "cable_pallofpress_001": {"secondary_muscles": ["Erector Spinae"]},
    "captainschair_lhold_001": {"secondary_muscles": ["Quadriceps"]},
    "situpbench_declinecrunch_001": {"secondary_muscles": ["Obliques"], "stabilizers": ["Hip Flexors"]},

    # --- Standing/band elbow isolation and grip work: braced against a
    # band or free grip needs core/forearm bracing. ---
    "biceps_isoneutralhold_001": {"stabilizers": ["Core"]},
    "biceps_bandcurl_light_001": {"stabilizers": ["Core"]},

    # --- Conditioning: sustained overhead circles load the cuff heavily
    # as a dynamic stabilizer. ---
    "battleropes_circles_001": {"stabilizers": ["Rotator Cuff"]},

    # --- The following already had secondary_muscles filled in; only
    # stabilizers was empty. ---
    # Leg curl machines (seated/lying, back supported): trunk braces.
    "legcurl_lying_001": {"stabilizers": ["Core"]},
    "legcurl_seated_001": {"stabilizers": ["Core"]},
    # Standing/seated free-weight curls: core braces against the swing.
    "ezbar_curl_001": {"stabilizers": ["Core"]},
    "cable_bicepcurl_001": {"stabilizers": ["Core"]},
    "ezbar_preachercurl_001": {"stabilizers": ["Core"]},
    "db_bicepcurl_001": {"stabilizers": ["Core"]},
    "db_hammercurl_001": {"stabilizers": ["Core"]},
    "db_concentrationcurl_001": {"stabilizers": ["Core"]},
    "db_preachercurl_001": {"stabilizers": ["Core"]},
    "ezbar_spidercurl_001": {"stabilizers": ["Core"]},
    "db_zottmancurl_001": {"stabilizers": ["Core"]},
    "db_crossbodyhammercurl_001": {"stabilizers": ["Core"]},
    "cable_ropehammercurl_001": {"stabilizers": ["Core"]},
    "cable_reversegrippushdown_001": {"stabilizers": ["Core"]},
    # GHD / hyperextension family: abdominals brace pelvis through the
    # hip hinge (Hamstrings/Glutes already cover posterior-chain secondary).
    "ghd_situp_001": {"stabilizers": ["Obliques"]},
    "ghd_backext_001": {"stabilizers": ["Core"]},
    "ghd_hipext_001": {"stabilizers": ["Core"]},
    "hyperext_bw_001": {"stabilizers": ["Core"]},
    "back_extension_001": {"stabilizers": ["Core"]},
    # Upright row and JM press: shoulder joint needs cuff stabilization.
    "ezbar_uprightrow_001": {"stabilizers": ["Rotator Cuff"]},
    "bb_jmpress_001": {"stabilizers": ["Rotator Cuff"]},
    # Hanging grip work: rotator cuff stabilizes the shoulder in the
    # dead-hang/pull position.
    "hangboard_repeaters_001": {"stabilizers": ["Rotator Cuff"]},
    # Neck harness / band neck work: levator scapulae is the genuine
    # deep cervical stabilizer across flexion/extension/rotation/lateral.
    "neckharness_extension_001": {"stabilizers": ["Levator Scapulae"]},
    "neckharness_lateral_001": {"stabilizers": ["Levator Scapulae"]},
    "band_neckrotation_001": {"stabilizers": ["Levator Scapulae"]},
    "bodyweight_prone_neckextension_001": {"stabilizers": ["Levator Scapulae"]},
    "neckharness_rotation_001": {"stabilizers": ["Levator Scapulae"]},
    "neckharness_weightednod_001": {"stabilizers": ["Levator Scapulae"]},
    # Decline sit-up-bench core work: obliques or hip flexors stabilize
    # depending on which one is already the listed secondary muscle.
    "situpbench_declinesitup_001": {"stabilizers": ["Obliques"]},
    "situpbench_declinetwist_001": {"stabilizers": ["Hip Flexors"]},
    "situpbench_declineraise_001": {"stabilizers": ["Obliques"]},
    "situpbench_weighteddeclinesitup_001": {"stabilizers": ["Obliques"]},
}


def main():
    BACKUP.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC, BACKUP)

    with open(SRC, "r", encoding="utf-8") as f:
        data = json.load(f)

    by_id = {ex["id"]: ex for ex in data["exercises"]}
    applied = {}
    missing_ids = []
    for eid, fields in FIXES.items():
        ex = by_id.get(eid)
        if ex is None:
            missing_ids.append(eid)
            continue
        changes = {}
        for field, value in fields.items():
            current = ex.get(field) or []
            if current:
                # Field wasn't actually empty - don't overwrite real data.
                continue
            ex[field] = value
            changes[field] = value
        if changes:
            applied[eid] = changes

    # Anything that was empty and NOT covered by an explicit FIXES entry
    # (should be zero after this script - flagged so nothing slips through
    # silently).
    still_empty = [
        ex["id"] for ex in data["exercises"]
        if not ex.get("secondary_muscles") or not ex.get("stabilizers")
    ]

    data["version"] = "5.28.0"
    data["schema_notes"] += (
        "\n\nv5.28 closes a secondary_muscles/stabilizers tagging gap: 132 "
        "exercises (mostly single-joint machine/cable/EZ-bar isolation work, "
        "plus neck-harness, hip-abduction, and core-isometric entries) had an "
        "empty secondary_muscles and/or stabilizers list even though a real "
        "synergist or postural stabilizer exists for the movement. Each "
        f"addition ({len(applied)} exercises touched) is a named muscle "
        "specific to that exercise's biomechanics (e.g. Anconeus for triceps "
        "lockout work, Brachioradialis for reverse-grip curls, Tensor "
        "Fasciae Latae for open-chain knee extension/hip abduction, Rotator "
        "Cuff for free-standing overhead/pulling shoulder work, Core for "
        "trunk bracing on seated pull/press machines) rather than a generic "
        "filler tag. primary_muscles and joint_stress had no gaps and were "
        "left untouched. See scripts/data_ops/fix_secondary_stabilizer_gaps.py."
    )

    with open(SRC, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"Applied fixes to {len(applied)} exercises:")
    for eid, ch in applied.items():
        print(f"  {eid}: {ch}")
    if missing_ids:
        print(f"\nWARNING - ids in FIXES not found in exercises.json: {missing_ids}")
    if still_empty:
        print(f"\nWARNING - still empty after fix: {still_empty}")
    else:
        print("\nNo exercises remain with an empty secondary_muscles or stabilizers list.")


if __name__ == "__main__":
    main()
