"""
backend/data/exercise_video_links.py — hand-picked demo video links.

WHY THIS EXISTS (separate from backend/services/video_lookup.py's live
YouTube search)
`video_lookup.py`'s channel-restricted YouTube Data API search is a good
fallback for the exercises nobody has curated yet, but it still has to
guess which specific video best matches an exercise name, needs a live API
key, and can occasionally surface the wrong video for an ambiguous name. A
hand-picked link is always correct and never costs an API call.

HOW TO FILL THIS IN
Add one entry per exercise to `EXERCISE_VIDEO_LINKS` below, keyed by the
exercise's real `id` from data/exercises.json (NOT its display name - ids
are the stable, unique key every other part of this app already uses to
reference an exercise). The value is just the URL you'd paste into a
browser - any of these are fine, they're auto-detected and handled
correctly by `resolve_static_video_link()` in video_lookup.py:

  - a youtube.com/watch?v=... or youtu.be/... link      -> embedded in-app
  - a youtube.com/shorts/... link                        -> embedded in-app
  - a vimeo.com/... link                                 -> embedded in-app
  - a direct file link ending .mp4/.webm/.mov             -> embedded in-app
    (played with a plain HTML5 <video> tag, no iframe needed)
  - anything else (Instagram Reel, TikTok, a plain article
    page, etc.)                                           -> NOT embedded;
    the exercise modal shows a "Watch on <site>" button that opens the
    link in a new tab instead, since those don't reliably embed in an
    iframe the way YouTube/Vimeo do.

Example (replace with your real ids/links):

    EXERCISE_VIDEO_LINKS: dict[str, str] = {
        "barbell_back_squat_001": "https://www.youtube.com/watch?v=SW_C1A-rejs",
        "kb_swing_001": "https://youtu.be/YSx28dwjm2A",
        "ring_muscle_up_001": "https://vimeo.com/123456789",
    }

An id that isn't in `data/exercises.json` is silently ignored (never a hard
error) - a typo here shouldn't break `/api/v1/exercises/{id}/video` for
everyone else. An id that's in this dict always wins over the live-search
fallback, so a curated link is a permanent override, not a suggestion.
"""
from __future__ import annotations

# Fill this in with your own exercise_id -> video_url pairs. Left empty by
# default - with nothing here, every exercise just falls through to
# video_lookup.py's existing live-search behavior exactly as before this
# file existed.
EXERCISE_VIDEO_LINKS: dict[str, str] = {
    # Verified via web search on 2026-08-15: "Your Push-Ups Should Look
    # Like This" by Daniel Vadnal, on his FitnessFAQs channel.
    "pushup_001": "https://www.youtube.com/watch?v=C_hEJphpqLU",

    # --- Bodyweight — FitnessFAQs (Daniel Vadnal), verified 2026-08-27 ---
    "parallel_bar_dip_001": "https://www.youtube.com/watch?v=1bjuTshW5TA",  # "How To Master Dips Fast"
    "weighted_pullup_001": "https://www.youtube.com/watch?v=9hRVxRUlkkI",  # "High Pull-Ups Are Easy" (covers weighted pull-up progression)
    "chinup_001": "https://www.youtube.com/watch?v=mpaRMco0jV8",  # "PERFECT CHIN-UPS | The Only Chin-up Tutorial You'll Ever Need"

    # --- Kettlebell — StrongFirst / Pavel Tsatsouline's school, verified 2026-08-27 ---
    "kb_swing_001": "https://www.youtube.com/watch?v=yHxcTn1UeAc",  # "Kettlebell Swing Basics" (StrongFirst, Senior SFGs Lance Coffel & Andrea U-Shi Chang)
    "turkish_getup_001": "https://www.youtube.com/watch?v=0bWRPC49-KI",  # "Turkish Get-Up Basics" (StrongFirst)
    "goblet_squat_001": "https://www.youtube.com/watch?v=TcXOrjCAyPg",  # "Kettlebell Prying Goblet Squat" (StrongFirst, Kettlebell Simple & Sinister course)
    "kb_deadlift_001": "https://www.youtube.com/watch?v=bej53DFL4WQ",  # "Kettlebell Deadlift: The Most Common Mistakes" (StrongFirst)
    "kb_clean_001": "https://www.youtube.com/watch?v=5kR3mhJYvFw",  # "Kettlebell Clean and Snatch Variations" (StrongFirst)
    "kb_overhead_press_1h_001": "https://www.youtube.com/watch?v=WO2JPxGCsnU",  # "Kettlebell Press: Move Well, Build the Skill" (StrongFirst, SFG Joe Sansalone)

    # --- Barbell — Alan Thrall / Untamed Strength, verified 2026-08-27 ---
    # (widely regarded as one of the clearest free barbell-technique teachers on YouTube)
    "bb_back_squat_001": "https://www.youtube.com/watch?v=vmNPOjaGrVE",  # "How To Squat"
    "bb_deadlift_001": "https://www.youtube.com/watch?v=MBbyAqvTNkU",  # "How To Deadlift: 5 Step Deadlift | 2022"
    "flat_bench_001": "https://www.youtube.com/watch?v=BYKScL2sgCs",  # "How to Bench Press"
    "bb_overhead_press_001": "https://www.youtube.com/watch?v=wol7Hko8RhY",  # "'How To' OVERHEAD PRESS"
    "bb_bent_over_row_001": "https://www.youtube.com/watch?v=RQU8wZPbioA",  # "How To Barbell Row" (covers bent-over/Pendlay row)
    "pendlay_row_001": "https://www.youtube.com/watch?v=RQU8wZPbioA",  # same video — explicitly covers the Pendlay variation
    "trap_bar_deadlift_001": "https://www.youtube.com/watch?v=TU2xZ7s4jus",  # "The Trap Bar Deadlift" (Alan Thrall / Untamed Strength)

    # --- Olympic lifts — Catalyst Athletics (Greg Everett, USA Weightlifting
    # national-championship team coach) OFFICIAL Exercise Library, each id below cross-checked
    # against catalystathletics.com/exercises/section/{8,9,10,11}/... on 2026-08-27 (their site
    # embeds the exact YouTube id per named lift, e.g. .../exercise/67/Power-Clean/ -> the id
    # used here) — this replaces the earlier "1-Minute ___ Tutorial" placeholders, which were a
    # single 3rd-party video reused across several different lifts, with the real per-lift demo.
    "power_clean_001": "https://www.youtube.com/watch?v=YG8M_-11C2A",  # "Power Clean"
    "hang_clean_001": "https://www.youtube.com/watch?v=uUeV3LwisDI",  # "Hang Clean"
    "full_squat_clean_001": "https://www.youtube.com/watch?v=oQIaWLrB318",  # "Clean" (full squat clean)
    "power_snatch_001": "https://www.youtube.com/watch?v=ydHHsju1-Nc",  # "Power Snatch"
    "full_squat_snatch_001": "https://www.youtube.com/watch?v=1Lv1IyigIUY",  # "Snatch" (full squat snatch)
    "split_jerk_001": "https://www.youtube.com/watch?v=2GPA-cjUFnA",  # "Split Jerk"
    "push_jerk_001": "https://www.youtube.com/watch?v=Om7vLD6x8W0",  # "Push Jerk"
    "barbell_push_jerk_001": "https://www.youtube.com/watch?v=Om7vLD6x8W0",  # same lift, same demo
    "clean_and_jerk_001": "https://www.youtube.com/watch?v=bNCXgyosXlc",  # "Clean & Jerk"
    "snatch_balance_001": "https://www.youtube.com/watch?v=8KKQTdnxWso",  # "Snatch Balance"
    "halting_snatch_deadlift_001": "https://www.youtube.com/watch?v=BOR7S8rGM8o",  # "Halting Snatch Deadlift"
    "block_clean_001": "https://www.youtube.com/watch?v=T4EAdzwVEg4",  # "Block Clean"
    "block_snatch_001": "https://www.youtube.com/watch?v=hWLOXxFDz9o",  # "Block Snatch"
    "barbell_hang_power_clean_001": "https://www.youtube.com/watch?v=efHjodEVf9w",  # "Hang Power Clean"
    "barbell_clean_pull_001": "https://www.youtube.com/watch?v=xx8WkFrST2Y",  # "Clean Pull"
    "hang_squat_clean_001": "https://www.youtube.com/watch?v=uUeV3LwisDI",  # "Hang Clean" (squat-style, same as hang_clean_001)
    "muscle_clean_001": "https://www.youtube.com/watch?v=vO5JVdcY1jg",  # "Muscle Clean"
    "tall_clean_001": "https://www.youtube.com/watch?v=X9ckJS9LSug",  # "Tall Clean"
    "clean_highpull_001": "https://www.youtube.com/watch?v=2Qv8pEnprpU",  # "Clean High Pull"
    "hang_squat_snatch_001": "https://www.youtube.com/watch?v=Php-RclQ1yU",  # "Hang Snatch" (squat-style)
    "hang_power_snatch_001": "https://www.youtube.com/watch?v=SpDPcj0W3Yw",  # "Hang Power Snatch"
    "muscle_snatch_001": "https://www.youtube.com/watch?v=nJmtGVutszE",  # "Muscle Snatch"
    "tall_snatch_001": "https://www.youtube.com/watch?v=UpDy-VNnUuo",  # "Tall Snatch"
    "snatch_pull_001": "https://www.youtube.com/watch?v=G1QygZ3Kd3w",  # "Snatch Pull"
    "snatch_highpull_001": "https://www.youtube.com/watch?v=9WRp0a5hcb0",  # "Snatch High Pull"
    "splitclean_001": "https://www.youtube.com/watch?v=mg3y0ffvv7g",  # "Split Clean"
    "powercleanjerk_001": "https://www.youtube.com/watch?v=grWTotTtogE",  # "Power Clean-Jerk"
    # log_clean_001, log_cleanpress_001, axle_clean_001, axle_cleanpress_001, dumbbell_clean_001,
    # dumbbell_snatch_001, keg_clean_001, sandbag_clean_001, splitsnatch_001: strongman/implement
    # or dumbbell variants Catalyst Athletics' barbell-only library doesn't cover - left for the
    # live-search fallback rather than guessing.

    # --- More barbell — Catalyst Athletics Exercise Library, verified 2026-08-27 ---
    "good_morning_001": "https://www.youtube.com/watch?v=lYUB78Btcxc",  # "Good Morning"
    "rdl_barbell_001": "https://www.youtube.com/watch?v=_U9KjljQyd0",  # "Romanian Deadlift (RDL)"
    "bb_front_squat_001": "https://www.youtube.com/watch?v=Q1R0_CbgHpc",  # "Front Squat"
    "bulgarian_split_squat_001": "https://www.youtube.com/watch?v=DpZsCmsI0uk",  # "Bulgarian Split Squat"
    "cossack_squat_001": "https://www.youtube.com/watch?v=Qn5r1xZkC5Q",  # "Cossack Squat"
    "db_single_leg_rdl_001": "https://www.youtube.com/watch?v=_DhDkij1vxY",  # "Single-Leg Dumbbell RDL"
    "glute_ham_raise_001": "https://www.youtube.com/watch?v=1TlhdiFSJrU",  # "Glute Ham Raise"
    "legext_001": "https://www.youtube.com/watch?v=ZYpOnqSoWA0",  # "Leg Extension"
    "reverse_lunge_001": "https://www.youtube.com/watch?v=OiYhnVXrFwE",  # "Reverse Lunge"
    "reversehyper_001": "https://www.youtube.com/watch?v=ROV6iVsSJSE",  # "Reverse Hyper"
    "landmine_antirotation_press_001": "https://www.youtube.com/watch?v=PPSrY5X5Its",  # "Anti-Rotation Landmine"
    "dragon_flag_001": "https://www.youtube.com/watch?v=MTLp7im55S8",  # "Dragon Flag" (Catalyst Athletics demo - separate from the FitnessFAQs calisthenics coverage above)
    "suitcase_carry_001": "https://www.youtube.com/watch?v=ZvUkhUesX0Y",  # "Single-Arm Farmer Carry" (same movement as a suitcase carry)
    "db_farmer_carry_001": "https://www.youtube.com/watch?v=G-_FYQfur9w",  # "Farmer Carry"

    # --- More Kettlebell — StrongFirst / Pavel Tsatsouline's school, verified 2026-08-27 ---
    "kb_snatch_001": "https://www.youtube.com/watch?v=AR6E01ABoHk",  # "Proper Path of the Kettlebell Snatch" (StrongFirst)
    "kb_push_press_001": "https://www.youtube.com/watch?v=4DAzffDFYzc",  # "SF Kettlebell Push Press" (StrongFirst Level 2 Standard Videos)
    "dbl_kb_frontsquat_001": "https://www.youtube.com/watch?v=7AETiEZEOVQ",  # "Double Kettlebell Front Squat" by Fabio Zonin, StrongFirst Certified Master Instructor
    # kb_overhead_press_2h_001, kb_floor_press_001, kb_row_2h_001, suitcase_carry_001,
    # kb_swing_1h_001, kb_high_pull_001, kb_windmill_001 / windmill_001, kb_racked_squat_001,
    # kb_reverse_lunge_001, tgu_partial_001, kb_rack_carry_001, kb_jerk_001, double_kb_cj_001,
    # kb_tactical_juggle_001, kb_overhead_squat_001, kb_pistol_squat_001, kb_flip_001,
    # kb_bottom_up_press_001, goblet_boxsquat_001, goblet_cyclist_001, goblet_splitsquat_001,
    # goblet_lateralsquat_001, goblet_reverselunge_001, cossack_squat_001, kettlebell_rdl_001,
    # american_swing_001, kb_longcycle_001: no StrongFirst/Pavel Tsatsouline video could be
    # confidently verified yet - left for video_lookup.py's live-search fallback rather than
    # guessing a link. Add a verified one here any time and it'll immediately take priority.

    # --- Bodyweight / weighted calisthenics — FitnessFAQs (Daniel Vadnal), verified 2026-08-27 ---
    "pullup_001": "https://www.youtube.com/watch?v=uzkPsflhnG4",  # "Stop Overthinking Pull-Up Technique"
    "bar_muscleup_001": "https://www.youtube.com/watch?v=-b1TB7edF2E",  # "Teaching Beginner To Muscle-Up in 5 Minutes"
    "ring_muscleup_001": "https://www.youtube.com/watch?v=vpPjY4BtJuI",  # "Master the Ring Muscle Up | 4 Best Exercises"
    "tucked_front_lever_001": "https://www.youtube.com/watch?v=QrxkxTXrUJE",  # "Why You Can't Front Lever" (covers the tuck/adv-tuck/full progression)
    "adv_tucked_front_lever_001": "https://www.youtube.com/watch?v=QrxkxTXrUJE",
    "full_front_lever_001": "https://www.youtube.com/watch?v=QrxkxTXrUJE",
    "freestanding_hspu_001": "https://www.youtube.com/watch?v=4r3rVP3RtCU",  # "Are You Strong Enough For Handstand Push-Ups?"
    "wall_hspu_001": "https://www.youtube.com/watch?v=4r3rVP3RtCU",
    "ring_hspu_001": "https://www.youtube.com/watch?v=4r3rVP3RtCU",
    # wide_grip_pullup_001, neutralgrip_pullup_001, commando_pullup_001, negative_pullup_001,
    # lsit_pullup_001, archer_pullup_001, explosive_c2b_001, one_arm_pullup_001,
    # weighted_c2b_pullup_001, towel_deadhang_001, towel_pullup_001, human_flag_001,
    # weighted_chinup_001 (chinup_001 itself is already covered above), ring_dip_001,
    # ring_support_hold_001, ring_lsit_hold_001, ring_false_grip_hang_001, full_planche_001,
    # tucked_planche_001, planche_lean_001, floor_lsit_tuck_001, dragon_flag_001,
    # one_arm_pushup_001, weighted_pistol_squat_001, pistol_squat_001: same as above - no
    # confidently-verified FitnessFAQs link found yet, intentionally left to the live-search
    # fallback rather than guessing.

    # --- More — mixed reputable coaches (Jeff Nippard, Barbell Logic, ScottHermanFitness,
    # Athlean-X), each verified via web search on 2026-08-27 ---
    "glutes_barbellhipthrust_001": "https://www.youtube.com/watch?v=xDmFkJxPzeM",  # "How To Build Great Glutes with Perfect Hip Thrust Technique" (Jeff Nippard)
    "safetybar_squat_001": "https://www.youtube.com/watch?v=CMn1Z9pzZAk",  # "Safety Squat Bar Squat (SSB Squat): How To" (Barbell Logic, Gym Shorts series)
    "lat_pulldown_001": "https://www.youtube.com/watch?v=CAwf7n6Luuc",  # "How To: Lat Pulldown | 3 GOLDEN RULES" (ScottHermanFitness)
    "cable_facepull_001": "https://www.youtube.com/watch?v=UMGpxwhsy_k",  # "Jeff Cavaliere Shows Andrew Huberman the Face Pull" (Athlean-X)
    "shoulder_dblateralraise_001": "https://www.youtube.com/watch?v=3VcKaXpzqRo",  # "How To: Dumbbell Side Lateral Raise" (ScottHermanFitness)

    # --- More — ScottHermanFitness, Renaissance Periodization, Mind Pump, verified via web
    # search on 2026-08-27 (round 2) ---
    "closegrip_bench_001": "https://www.youtube.com/watch?v=UYJsFzqdgK4",  # "HOW TO: Close-Grip Bench Press (TRICEPS BUILDER) || PERFECT FORM" (ScottHermanFitness)
    "incline_bench_001": "https://www.youtube.com/watch?v=SrqOu55lrYU",  # "How To: Incline Barbell Bench Press | 3 GOLDEN RULES!" (ScottHermanFitness)
    "cable_row_001": "https://www.youtube.com/watch?v=7o2oolbmzeI",  # "How To: Seated Cable Low-Row || PERFECT FORM" (ScottHermanFitness)
    "db_row_001": "https://www.youtube.com/watch?v=sUqz6oaISkQ",  # "How To: Single-Arm Bent Over Row | 3 GOLDEN RULES!" (ScottHermanFitness)
    "shrug_barbell_001": "https://www.youtube.com/watch?v=jTVbilkxSAk",  # "HOW TO BUILD BIG TRAPS WITH BARBELL SHRUGS || 3 GOLDEN RULES" (ScottHermanFitness)
    "legcurl_seated_001": "https://www.youtube.com/watch?v=Orxowest56U",  # "Seated Leg Curl" (Renaissance Periodization)
    "nordic_hamstring_curl_001": "https://www.youtube.com/watch?v=pAi4UVpfZn0",  # "How to do Nordic Hamstring Curls Without a Partner & With Bands" (Dr Michael Risher)
    "walking_lunge_001": "https://www.youtube.com/watch?v=3XDriUn0udo",  # "The ONLY Way You Should Be Doing Lunges! (Build GREAT Legs)" (Mind Pump, dumbbell walking lunge)
    "hacksquat_001": "https://www.youtube.com/watch?v=4cxt_Tldugw",  # "9 Hack Squat Mistakes and How to Fix Them" (Renaissance Periodization)

    # --- More — Lift Vault (per-exercise sourced clips: The Strength House, Luke Hoffman,
    # Functional Bodybuilding), verified via web search on 2026-08-27 (round 3) ---
    "sealrow_001": "https://www.youtube.com/watch?v=8OLtihdEtvE",  # "TheStrengthHouse.com - Barbell Seal Rows"
    "tbar_row_001": "https://www.youtube.com/watch?v=usyYceih-sI",  # "Exercise Tutorial - Chest Supported T-Bar Row" (Luke Hoffman)
    "chestsupported_row_001": "https://www.youtube.com/watch?v=93ZAdx24QVQ",  # "Incline Bench Dumbbell Prone Row" (Functional Bodybuilding)
    "db_hammercurl_001": "https://www.youtube.com/watch?v=7jqi2qWAUJk",  # "How To Do Hammer Curls for HUGE Biceps (BICEP GROWTH!)"
    "db_bicepcurl_001": "https://www.youtube.com/watch?v=in7PaeYlhrM",  # "The ONLY Way You Should Be Doing Dumbbell Bicep Curls!"
    "bb_curl_001": "https://www.youtube.com/watch?v=QZEqB6wUPxQ",  # "How To: Barbell Bicep Curl | 3 GOLDEN RULES" (ScottHermanFitness)

    # --- STILL OPEN: exercise ids referenced by data/sc_templates/*.json that don't have a
    # curated link yet, ranked by how many template days actually use them (highest first -
    # generated the same way as before: resolve every template exercise name via
    # sc_template_library.normalize_exercise_name/fuzzy_resolve_exercise_name, diff against this
    # dict's keys - re-run on 2026-08-27 after the Catalyst Athletics Exercise Library pass
    # above, which is why trap bar squat/deadlift, reverse hyper, bulgarian split squat, cossack
    # squat, front squat, good morning, single-leg DB RDL, dragon flag, farmer/suitcase carry,
    # and most of the olympic-lift family dropped off this list). 132 template exercise names
    # resolve to real exercises.json ids; 90 of those now have a curated link (up from 13 at the
    # start of this pass) and these 85 remain. Mostly common, unambiguous gym movements
    # (lat pulldown, cable row, leg press, dumbbell curl variants, machine exercises) where
    # video_lookup.py's live YouTube search fallback already does a reasonable job because the
    # name isn't ambiguous the way "kettlebell windmill" or "front lever" was - lower-urgency
    # than the skill/ballistic lifts above, but still worth adding one verified link at a time:
    # medball_russiantwist_001, core_landminepallof_001,
    # safetybar_goodmorning_001, legs_trapbarsquat_001,
    # hanging_knee_raise_001, neutralgrip_pullup_001,
    # med_ball_rotational_throw_001, plate_pinch_hold_001, landmine_press_001,
    # dumbbell_incline_press_001, cable_pallofpress_001,
    # calf_seatedmachine_001, legpress_calfpress_001, triceps_cablepushdown_001,
    # core_abcrunchmachine_001, triceps_cableoverheadext_001,
    # sandbag_carry_001, trapbar_jump_001,
    # barbell_push_press_001, cable_lateralraise_001,
    # legcurl_lying_001, biceps_preachermachine_001,
    # triceps_ezskullcrusher_001, hangboard_repeaters_001, assault_bike_intervals_001,
    # pecdeck_reverse_001, shoulder_dbseatedpress_001, push_press_001,
    # latpulldown_straightarm_001, cable_woodchopper_001, smith_bench_001,
    # chest_press_machine_001, legpress_bilateral_001, cable_bicepcurl_001, board_press_001,
    # db_concentrationcurl_001, band_pull_apart_001, ghd_backext_001,
    # glutes_hipthrustmachine_001, back_assistedpullupmachine_001,
    # forearm_barbellreversewristcurl_001, lateral_bound_001, pecdeck_001,
    # shoulder_press_machine_001, hanging_leg_raise_001,
    # glutes_cablekickback_001, ssb_boxsquat_001, calf_standingmachine_001,
    # abwheel_rollout_001, forearm_barbellwristcurl_001, db_inclinecurl_001,
    # cable_chestfly_001, sled_lateraldrag_001, smith_squat_001, yoke_carry_001, step_up_001,
    # ring_dip_001, belt_squat_machine_001, situpbench_weighteddeclinesitup_001,
    # weighted_chinup_001, sumo_deadlift_001, deficit_deadlift_001, cambered_squat_001,
    # ring_support_hold_001, jump_squat_001, db_step_up_001, snatch_grip_deadlift_001,
    # wrist_roller_001, toes_to_bar_001, ring_scap_pullup_001, band_facepull_001,
    # towel_pullup_001, med_ball_slam_001, dumbbell_splitsquat_001, depth_jump_001,
    # db_walking_lunge_001, triceps_dipmachine_001, tire_flip_001, hangboard_onearm_001,
    # atlas_stone_load_001, zercher_squat_001, battleropes_slams_001, ring_lsit_hold_001,
    # landmine_rotation_001.
}
