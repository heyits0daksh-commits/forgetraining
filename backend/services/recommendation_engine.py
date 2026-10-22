"""Phase 5 (docs/ROADMAP.md): a lightweight scored-recommendation layer
built on top of REAL logged history (session_logs.log_json - the actual
weight x reps sets a person logged, see frontend's syncSessionToBackend /
logSet), on top of the static sport/equipment/injury/level scoring
ProgressionEngine already did.

This is deliberately the same "explainable heuristic, not a trained model"
spirit as readiness_service.compute_suggested_readiness - every number
here can be justified in one sentence to the person looking at it, and
it's a *ranking nudge only*: it never changes which exercises pass the
safety/equipment/strength/level gate in generate_session, only how the
qualifying ones are ordered - same contract every other multiplier that
already feeds sport_priority_score (sport_profiles.py) already has.

Gated behind a minimum amount of history (MIN_SESSIONS_FOR_SIGNAL) so a
brand-new or casual account never sees ranking shift under it, and behind
being logged in at all (routes.py only calls this for an authenticated
athlete_id) - there's no meaningful "history" for the shared anonymous
"default" athlete_id across many unrelated people.
"""
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from backend.models.db_models import SessionLogDB

# Below this many logged sessions (with actual set data - readiness-only
# check-ins don't count), personalization is a complete no-op. Matches the
# "don't assume more than we've been told" principle conservative_default_ratios
# and compute_suggested_readiness both already use.
MIN_SESSIONS_FOR_SIGNAL = 3

# How many sessions of history to look back over per athlete/sport.
_HISTORY_LOOKBACK_SESSIONS = 30

# An exercise not logged in this many days is treated as "stale" - worth
# resurfacing rather than always reaching for whatever was trained most
# recently. 21 days ~= 3 weekly cycles for most splits.
STALENESS_DAYS = 21

# Multiplier nudges. All small (5-15%) on purpose - this rides on top of
# sport/level/equipment scoring, it doesn't override it. A single stale or
# plateaued exercise can still easily be out-scored by a much better
# sport-transfer pick; this only breaks ties among otherwise-similar
# candidates, the same job _pick_with_variety's tie-band already does for
# raw repetition.
FRESHNESS_BOOST = 1.15
RECENT_REPEAT_PENALTY = 0.93
PROGRESSING_BOOST = 1.08
PLATEAU_PENALTY = 0.90

# The generic plateau note text, exported so progression_engine.py can
# recognize it and (when the plateaued exercise has an authored next-tier
# progression) rewrite it to name that specific exercise instead of
# speaking generically - see progression_engine._name_plateau_progression.
PLATEAU_NOTE = "Flat for a few sessions - consider its next progression"


def _estimated_1rm(weight: float, reps: int) -> float:
    """Epley-style estimate - same shape as the frontend's own
    computeScore() (weight * (1 + reps/30)) used for its client-side PR
    detection, so a server-side 'progressing/plateaued' read agrees with
    what the person already sees as a PR in the UI."""
    if reps <= 0 or weight <= 0:
        return 0.0
    return weight * (1 + reps / 30.0)


def build_history_signals(
    db: Session, athlete_id: str, sport: Optional[str] = None,
) -> Dict[str, Dict]:
    """One pass over an athlete's logged sessions -> {exercise_id: signal}.

    Returns {} below MIN_SESSIONS_FOR_SIGNAL (nothing to react to yet) -
    callers should treat an empty dict as "no personalization this call",
    not as an error.
    """
    query = db.query(SessionLogDB).filter(SessionLogDB.athlete_id == athlete_id)
    if sport:
        query = query.filter(SessionLogDB.sport == sport)
    rows = query.order_by(SessionLogDB.date.desc()).limit(_HISTORY_LOOKBACK_SESSIONS).all()

    # Sport-scoped history first (a bench-press trend from Boxing sessions
    # says more about today's Boxing session than nothing would), but fall
    # back to all-sport history if there isn't enough of it yet - same
    # fallback compute_suggested_readiness already uses for the same reason.
    if len(rows) < MIN_SESSIONS_FOR_SIGNAL and sport:
        rows = (
            db.query(SessionLogDB)
            .filter(SessionLogDB.athlete_id == athlete_id)
            .order_by(SessionLogDB.date.desc())
            .limit(_HISTORY_LOOKBACK_SESSIONS)
            .all()
        )

    if len(rows) < MIN_SESSIONS_FOR_SIGNAL:
        return {}

    now = datetime.now(timezone.utc)
    per_exercise: Dict[str, List[tuple]] = {}  # exId -> [(sessions_ago, date, best_e1rm)]
    for sessions_ago, row in enumerate(rows):
        try:
            entries = json.loads(row.log_json or "[]")
        except (TypeError, ValueError):
            continue
        if not entries:
            continue
        row_date = row.date if row.date.tzinfo else row.date.replace(tzinfo=timezone.utc)
        for entry in entries:
            ex_id = entry.get("exId")
            sets = entry.get("sets") or []
            if not ex_id or not sets:
                continue
            best = max(
                (_estimated_1rm(s.get("weight", 0), s.get("reps", 0)) for s in sets),
                default=0.0,
            )
            per_exercise.setdefault(ex_id, []).append((sessions_ago, row_date, best))

    signals: Dict[str, Dict] = {}
    for ex_id, history in per_exercise.items():
        history.sort(key=lambda h: h[0])  # index 0 = most recently logged
        sessions_since_last, most_recent_date, _ = history[0]
        days_since = max(0, (now - most_recent_date).days)

        trend = None
        if len(history) >= 3:
            # Oldest-of-the-last-3 -> newest, so a rising sequence reads as
            # a genuinely rising trend rather than most-recent-first.
            recent = [h[2] for h in history[:3]][::-1]
            if recent[0] > 0:
                if recent[-1] > recent[0] * 1.02:
                    trend = "progressing"
                elif all(abs(v - recent[0]) <= recent[0] * 0.02 for v in recent):
                    trend = "plateau"

        signals[ex_id] = {
            "times_logged": len(history),
            "days_since": days_since,
            "sessions_since_last": sessions_since_last,
            "trend": trend,
        }
    return signals


def personalization_multiplier(ex_id: str, signals: Dict[str, Dict]) -> Dict:
    """{"multiplier": float, "note": str|None} for one exercise, given the
    signals dict build_history_signals returned. (1.0, None) - a complete
    no-op - for any exercise with no history signal, which in practice is
    most of the database for most athletes, always."""
    sig = signals.get(ex_id)
    if sig is None:
        return {"multiplier": 1.0, "note": None}

    multiplier = 1.0
    note = None

    if sig["sessions_since_last"] <= 1 and sig["times_logged"] >= 2:
        multiplier *= RECENT_REPEAT_PENALTY
        note = "Logged in your last session or two - mixing in variety"
    elif sig["days_since"] >= STALENESS_DAYS:
        multiplier *= FRESHNESS_BOOST
        note = f"Haven't logged this in {sig['days_since']} days"

    # Trend read takes priority over the freshness/repeat note above when
    # both apply - "you're progressing on this" is more actionable to see
    # than "you did this recently", and a plateau is worth flagging even on
    # something that would otherwise get a freshness boost.
    if sig["trend"] == "progressing":
        multiplier *= PROGRESSING_BOOST
        note = "Numbers trending up here recently - stays in rotation"
    elif sig["trend"] == "plateau":
        multiplier *= PLATEAU_PENALTY
        note = PLATEAU_NOTE

    return {"multiplier": round(multiplier, 3), "note": note}


# --- Adaptive load/volume adjustment (session-level, not per-exercise) -----
#
# Everything above this point (build_history_signals/personalization_multiplier)
# answers "which of the qualifying exercises should rank higher/lower right
# now" - a ranking nudge only. This section answers a different question:
# "given this athlete's actual recent training - not just today's readiness
# slider - should the NEXT session run lighter/heavier or bigger/smaller than
# what today's readiness alone would prescribe?" Same "explainable heuristic,
# not a trained model" spirit as everything else in this file, reusing the
# exact session-log rows/lookback pattern build_history_signals already
# established. It only ever *nudges* generate_session's existing
# readiness_factor/deload_mode/_prescribe_volume path - it never bypasses the
# safety/equipment/injury/level gate, same contract every other multiplier
# here already has.

# A bit higher than MIN_SESSIONS_FOR_SIGNAL - an aggregate week-over-week /
# RPE-trend read needs a little more history to trust than a single
# exercise's own repeat count does.
MIN_SESSIONS_FOR_LOAD_ADJUSTMENT = 4
_LOAD_LOOKBACK_SESSIONS = 14

# Session-RPE (1-10) moving up this much between two 3-session windows reads
# as accumulating fatigue, not day-to-day noise.
RPE_SPIKE_DELTA = 1.0
# A recent-window average RPE at/above this is "grinding every session" -
# worth an outright deload flag, not just a small nudge.
RPE_HIGH_RECENT_AVG = 8.5
# This week's logged sets vs last week's - the classic acute:chronic
# workload-spike ratio (>1.4-1.5x is the commonly-cited injury-risk zone).
VOLUME_SPIKE_RATIO = 1.4
_MIN_VOLUME_SETS_FOR_COMPARISON = 6
# A gap this long since the last logged session (or 2.5x the athlete's own
# typical inter-session gap, whichever is bigger) reads as "returning from a
# break", not just a normal rest day.
RETURNING_FROM_BREAK_DAYS = 10

_INACTIVE_ADAPTIVE_ADJUSTMENT = {
    "active": False,
    "volume_multiplier": 1.0,
    "intensity_multiplier": 1.0,
    "auto_deload_recommended": False,
    "sessions_considered": 0,
    "reasons": [],
}


def compute_adaptive_load_adjustment(
    db: Session,
    athlete_id: str,
    sport: Optional[str] = None,
    exercise_signals: Optional[Dict[str, Dict]] = None,
    training_emphasis: Optional[str] = None,
    training_phase: Optional[str] = None,
    expected_days_per_week: Optional[int] = None,
    forced_deload: bool = False,
) -> Dict:
    """Whole-session read of an athlete's recent training history -> a small
    volume/intensity nudge for the *next* session, layered on top of
    whatever readiness the person entered. Every signal here is something a
    coach could point to in one sentence:

      1. Session RPE trending up/down across recent sessions (self-reported
         effort, the same `rpe` field logged on SessionLogCreate).
      2. Logged set volume spiking week-over-week (acute:chronic overreach).
      3. An unusually long gap since the last logged session - returning
         from a break, so the next session eases back in rather than
         picking up exactly where the person left off.
      4. The aggregate progressing/plateau read `build_history_signals`
         already computed per exercise, if the caller passes it in
         (`exercise_signals`) - re-read here in aggregate rather than
         per-exercise: mostly-plateaued reads differently depending on
         whether the goal is hypertrophy (add volume to break it) or
         strength/general (back off intensity instead of grinding).

    `forced_deload` (v5.35 - closes the "four uncoordinated deload signals"
    gap flagged in docs/ROADMAP.md's v5.19/v5.17 notes): the caller
    (`ProgressionEngine.generate_session`) sets this when the session is
    ALREADY going into deload_mode for a reason this function has no
    visibility into on its own - a low readiness slider, a 5/5 soreness
    report, or (via `program_builder.generate_program`'s readiness clamp on
    its calendar deload week) a fixed mesocycle deload week. When set, this
    caps both multipliers at "never push harder than baseline" - identical
    treatment to the existing Fight Week/Post-Competition cap below - so a
    progressing-trend or plateau-busting nudge can't partially fight a
    deload some other, earlier-decided signal already committed to. It can
    still recommend backing off FURTHER (a bad RPE trend during an already-
    light week is still worth flagging), just never harder-than-baseline.
    This doesn't make the four signal sources one unified decision-maker
    (a real design change, still open - see the roadmap) - it closes the
    one concrete way they could actively contradict each other.

    Returns a copy of `_INACTIVE_ADAPTIVE_ADJUSTMENT` (both multipliers
    1.0, a total no-op) below `MIN_SESSIONS_FOR_LOAD_ADJUSTMENT` logged
    sessions - same "don't assume more than we've been told" gate every
    other history-based feature in this file already uses, and the same
    shape as build_history_signals returning {} - callers should treat
    `active: False` as "no adjustment this call", not an error.
    """
    query = db.query(SessionLogDB).filter(SessionLogDB.athlete_id == athlete_id)
    if sport:
        query = query.filter(SessionLogDB.sport == sport)
    rows = query.order_by(SessionLogDB.date.desc()).limit(_LOAD_LOOKBACK_SESSIONS).all()

    # Same sport-scoped-first-then-fall-back-to-all-sport pattern as
    # build_history_signals/compute_suggested_readiness, for the same reason:
    # a brand-new sport shouldn't read as "no history" just because every
    # OTHER sport this athlete trains has logs.
    if len(rows) < MIN_SESSIONS_FOR_LOAD_ADJUSTMENT and sport:
        rows = (
            db.query(SessionLogDB)
            .filter(SessionLogDB.athlete_id == athlete_id)
            .order_by(SessionLogDB.date.desc())
            .limit(_LOAD_LOOKBACK_SESSIONS)
            .all()
        )

    if len(rows) < MIN_SESSIONS_FOR_LOAD_ADJUSTMENT:
        return dict(_INACTIVE_ADAPTIVE_ADJUSTMENT, sessions_considered=len(rows))

    now = datetime.now(timezone.utc)

    def _dated(row):
        d = row.date if row.date.tzinfo else row.date.replace(tzinfo=timezone.utc)
        return d, row

    dated_rows = sorted((_dated(r) for r in rows), key=lambda t: t[0], reverse=True)

    reasons: List[str] = []
    volume_multiplier = 1.0
    intensity_multiplier = 1.0
    auto_deload = False

    def _session_effort(row) -> Optional[float]:
        """One RPE-scale (1-10) number for a session: the logged overall
        `rpe` field when present, otherwise averaged from whatever per-set
        rpe/rir values the frontend happened to log inline on `log_json`
        (both are free-form pass-through fields - see SessionLogCreate's
        docstring - so this is a best-effort read, not a guaranteed one).
        RIR (reps in reserve, 0-5ish, lower = harder) is converted onto the
        same 1-10 RPE scale as `10 - rir`, the standard RPE/RIR correspondence,
        so the two never get silently averaged together on mismatched scales.
        None when nothing usable is present either way."""
        if row.rpe is not None:
            return row.rpe
        try:
            entries = json.loads(row.log_json or "[]")
        except (TypeError, ValueError):
            return None
        per_set_efforts = []
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            for s in (entry.get("sets") or []):
                if not isinstance(s, dict):
                    continue
                if s.get("rpe") is not None:
                    per_set_efforts.append(s["rpe"])
                elif s.get("rir") is not None:
                    per_set_efforts.append(max(1.0, 10.0 - s["rir"]))
        return sum(per_set_efforts) / len(per_set_efforts) if per_set_efforts else None

    # 1) Session effort trend: last 3 sessions with a usable RPE/RIR-derived
    # effort number vs the 3 before that.
    rpe_series = [(d, e) for d, r in dated_rows if (e := _session_effort(r)) is not None]
    if len(rpe_series) >= 4:
        recent = [v for _, v in rpe_series[:3]]
        prior = [v for _, v in rpe_series[3:6]]
        if prior:
            recent_avg = sum(recent) / len(recent)
            prior_avg = sum(prior) / len(prior)
            if recent_avg - prior_avg >= RPE_SPIKE_DELTA:
                intensity_multiplier *= 0.92
                volume_multiplier *= 0.90
                reasons.append(
                    f"Session RPE trending up ({prior_avg:.1f} -> {recent_avg:.1f} over your last "
                    f"{len(recent) + len(prior)} logged sessions) - backing off load and volume"
                )
                if recent_avg >= RPE_HIGH_RECENT_AVG:
                    auto_deload = True
            elif prior_avg - recent_avg >= RPE_SPIKE_DELTA and recent_avg <= 6.5:
                intensity_multiplier *= 1.05
                reasons.append(
                    f"Session RPE trending down ({prior_avg:.1f} -> {recent_avg:.1f}) with room to "
                    "spare - nudging intensity up"
                )

    # 2) Weekly logged-set volume: last 7 days vs the 7 days before that.
    def _set_count(row) -> int:
        try:
            entries = json.loads(row.log_json or "[]")
        except (TypeError, ValueError):
            return 0
        return sum(len(e.get("sets") or []) for e in entries if isinstance(e, dict))

    last_7 = sum(_set_count(r) for d, r in dated_rows if (now - d).days <= 7)
    prior_7 = sum(_set_count(r) for d, r in dated_rows if 7 < (now - d).days <= 14)
    if prior_7 >= _MIN_VOLUME_SETS_FOR_COMPARISON and last_7 >= _MIN_VOLUME_SETS_FOR_COMPARISON:
        ratio = last_7 / prior_7
        if ratio >= VOLUME_SPIKE_RATIO:
            volume_multiplier *= 0.85
            reasons.append(
                f"Logged set volume jumped {ratio:.1f}x week-over-week ({prior_7} -> {last_7} sets) - "
                "capping volume to avoid an acute spike"
            )

    # 3) Missed sessions / returning from a break. expected_days_per_week
    # (from a Program Builder request, when available) gives a precise
    # expected inter-session gap; otherwise fall back to the athlete's own
    # median gap across their logged history.
    most_recent_date = dated_rows[0][0]
    days_since_last = max(0, (now - most_recent_date).days)
    if expected_days_per_week and expected_days_per_week > 0:
        expected_gap_days = 7.0 / expected_days_per_week
    else:
        gaps = [(dated_rows[i][0] - dated_rows[i + 1][0]).days for i in range(len(dated_rows) - 1)]
        gaps = [g for g in gaps if g > 0]
        expected_gap_days = (sum(gaps) / len(gaps)) if gaps else 4.0

    break_threshold = max(RETURNING_FROM_BREAK_DAYS, expected_gap_days * 2.5)
    missed_sessions_est = max(0, round(days_since_last / expected_gap_days) - 1) if expected_gap_days > 0 else 0
    if days_since_last >= break_threshold:
        volume_multiplier *= 0.75
        intensity_multiplier *= 0.85
        missed_note = f", ~{missed_sessions_est} session(s) likely missed" if missed_sessions_est >= 1 else ""
        reasons.append(
            f"{days_since_last} day(s) since your last logged session (typical gap ~{expected_gap_days:.0f}"
            f"{missed_note}) - easing back in rather than picking up where you left off"
        )

    # 4) Aggregate performance trend, reusing the per-exercise read
    # build_history_signals already computed for ranking (not recomputed
    # here). Majority-plateaued reads differently by goal: more volume for a
    # hypertrophy-leaning goal (more stimulus is the usual plateau-breaker),
    # less intensity otherwise (fatigue management, not more sets, is what
    # actually fixes a stalled strength number).
    if exercise_signals:
        trends = [sig.get("trend") for sig in exercise_signals.values() if sig.get("trend")]
        if len(trends) >= 3:
            plateau_n = trends.count("plateau")
            progressing_n = trends.count("progressing")
            if plateau_n / len(trends) >= 0.5:
                if training_emphasis in ("hypertrophy", "strength_hypertrophy"):
                    volume_multiplier *= 1.08
                    reasons.append(
                        f"{plateau_n}/{len(trends)} tracked exercises are flat recently - adding a bit "
                        "more volume to help break the plateau"
                    )
                else:
                    intensity_multiplier *= 0.95
                    reasons.append(
                        f"{plateau_n}/{len(trends)} tracked exercises are flat recently - backing off "
                        "intensity slightly rather than grinding the same numbers"
                    )
            elif progressing_n / len(trends) >= 0.6 and not auto_deload:
                intensity_multiplier *= 1.04
                reasons.append(
                    f"{progressing_n}/{len(trends)} tracked exercises are trending up - keeping "
                    "intensity on the front foot"
                )

    # A fight-week/taper or post-competition phase caps this at "never push
    # harder than baseline" - the whole point of that phase is shedding
    # fatigue, not chasing a plateau-busting bump. A session already forced
    # into deload_mode by readiness/soreness/a calendar deload week (see
    # `forced_deload`'s docstring above) gets the identical cap, for the
    # identical reason - a different signal already decided this session
    # should be lighter, so this one shouldn't quietly push back the other
    # way.
    if training_phase in ("Fight Week", "Post-Competition") or forced_deload:
        volume_multiplier = min(volume_multiplier, 1.0)
        intensity_multiplier = min(intensity_multiplier, 1.0)

    volume_multiplier = round(max(0.6, min(1.15, volume_multiplier)), 3)
    intensity_multiplier = round(max(0.7, min(1.1, intensity_multiplier)), 3)

    return {
        "active": bool(reasons),
        "volume_multiplier": volume_multiplier,
        "intensity_multiplier": intensity_multiplier,
        "auto_deload_recommended": auto_deload,
        "sessions_considered": len(rows),
        "reasons": reasons,
    }
