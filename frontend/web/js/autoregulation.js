'use strict';

// ============================================================
// AUTOREGULATION — real week-to-week progression from what actually
// happened, not just a fixed +3%/week formula.
//
// generate-program builds every week's numbers up front (program_builder.
// py's _apply_week_progression), before the person has trained a single
// day of it — so week 2's "+3% load" is a plan, not yet earned. This closes
// that loop client-side, the same moment a day gets saved: it compares what
// got logged against what was actually prescribed for THAT day, and nudges
// the *next* occurrence of that same day-label (next week, same
// dayIndex/day_label — the split repeats week to week) up, down, or leaves
// the static formula's number alone.
//
//   - Missed reps on multiple sets, or high reported soreness/fatigue
//     -> hold next week's numbers at this week's actual level instead of
//        applying the planned bump (a small step down, not a full reset).
//   - Every set met or beat its target AND recovery looked good
//     -> an extra bump on top of the planned one.
//   - Anything in between (the common case) -> untouched; the existing
//     linear-progression formula's number stands.
//
// Deliberately narrow and explainable (same spirit as readiness_service.
// compute_suggested_readiness and recommendation_engine's multipliers):
// only ever touches ONE week ahead (no cascading compounding across the
// whole mesocycle from one bad session), never touches a week already
// flagged deload_mode (that lightening is intentional, not a signal to
// override), and never rewrites a week the person has already saved/
// trained (S.programSavedDays already knows that).
//
// v5.19 note on the "four uncoordinated deload signals" gap flagged in
// the roadmap's v5.17 pass: this hold/boost mechanism (autoregulateNextWeek/
// applyAutoregulationStep) has NO server-side equivalent to reconcile
// against - backend/services/recommendation_engine.py's adaptive-load
// engine only ever adjusts the CURRENT session at generation time, it has
// no concept of "nudge a specific future week's already-generated numbers
// based on what just got logged for today." This file's job here is
// genuinely distinct, not a duplicate: it reacts to one day's just-saved
// performance against an already-generated program sitting in the
// browser, something only the client can do without a full program
// regeneration round-trip. What WAS a real duplicate - checkSignalDeload/
// applyWeekDeloadStep's deload MAGNITUDE, further below - has been fixed
// to mirror the server's real formulas exactly; this function's own
// +/-3%-ish nudge constants are intentionally this file's own heuristic
// and don't need a server equivalent to match, since none exists.
// ============================================================

function computeDayPerformanceSignal(day, dayLog){
  var byId = {};
  (day.prescribed_workout || []).forEach(function(ex){ byId[ex.id] = ex; });
  var totalSets = 0, metOrExceeded = 0;
  Object.keys(dayLog).forEach(function(exId){
    var ex = byId[exId];
    var target = ex && ex.prescription && ex.prescription.reps;
    if(target == null) return; // no rep target on this prescription type (e.g. a timed carry) - not usable here
    (dayLog[exId].sets || []).forEach(function(s){
      totalSets++;
      if(s.reps >= target) metOrExceeded++;
    });
  });
  if(totalSets === 0) return null; // nothing comparable logged this time - no signal, no adjustment
  return {hitRate: metOrExceeded / totalSets, loggedSets: totalSets};
}
function autoregulateNextWeek(day, weekNumber, dayIndex, dayLabel, dayLog, postSoreness, postFatigue){
  if(!S.lastProgram) return;
  var signal = computeDayPerformanceSignal(day, dayLog);
  if(!signal) return;

  var nextWeek = S.lastProgram.program.find(function(w){ return w.week_number === weekNumber + 1; });
  if(!nextWeek || nextWeek.is_deload) return; // don't second-guess a scheduled deload
  var nextDay = nextWeek.days[dayIndex];
  if(!nextDay || nextDay.day_label !== dayLabel) return; // split shifted somehow - don't guess, skip
  var nextDayKey = (weekNumber + 1) + '|' + dayIndex;
  if(S.programSavedDays[nextDayKey]) return; // already trained/logged - don't rewrite it after the fact

  var badRecovery = (postSoreness != null && postSoreness >= 4) || (postFatigue != null && postFatigue >= 4);
  var greatRecovery = (postSoreness != null && postSoreness <= 2) && (postFatigue != null && postFatigue <= 2);

  var mode, reason;
  if(signal.hitRate < 0.6 || badRecovery){
    mode = 'hold';
    reason = signal.hitRate < 0.6
      ? 'you missed reps on multiple sets last time'
      : 'high soreness/fatigue reported after last time';
  } else if(signal.hitRate >= 0.9 && greatRecovery){
    mode = 'boost';
    reason = 'you hit every target easily and recovery looked good';
  } else {
    return; // within normal range - leave the static week-progression number alone
  }

  var note = 'Auto-adjusted from last week\u2019s ' + dayLabel + ' — ' + reason + '.';
  nextDay.prescribed_workout.forEach(function(ex){
    ex.prescription = applyAutoregulationStep(ex.prescription, mode);
    ex.prescription.progression_note = note;
    ex.prescription.autoregulated = true;
  });
}
function applyAutoregulationStep(p, mode){
  var result = Object.assign({}, p);
  var sign = mode === 'boost' ? 1 : -1;
  if(result.type === 'strength'){
    var oldPct = result.load_pct_1rm;
    var newPct = Math.max(1, Math.min(95, oldPct + sign * 3));
    if(result.working_weight_kg != null && oldPct){
      result.working_weight_kg = result.working_weight_kg * (newPct / oldPct);
    }
    result.load_pct_1rm = newPct;
  } else if(result.type === 'strength_bodyweight' || result.type === 'isolation'){
    result.reps = Math.max(1, result.reps + sign);
  } else if(result.type === 'conditioning'){
    result.work_seconds = Math.max(5, Math.round(result.work_seconds * (1 + sign * 0.05)));
    result.rest_seconds = Math.max(15, Math.round(result.rest_seconds * (1 - sign * 0.05)));
  } else if(result.type === 'isometric'){
    result.hold_seconds = Math.max(5, Math.round(result.hold_seconds * (1 + sign * 0.05)));
  } else if(result.type === 'carry'){
    result.distance_meters = Math.max(1, Math.round(result.distance_meters * (1 + sign * 0.05)));
  }
  return result;
}

// ------------------------------------------------------------
// SIGNAL-TRIGGERED DELOAD — the program builder only ever schedules a
// deload on a fixed calendar week (program_builder.py: the last week of a
// mesocycle >= 3 weeks, decided at generation time, before a single day of
// it has actually been trained). GET /api/v1/readiness/suggested already
// computes a real, explainable trend signal off logged soreness/fatigue
// (readiness_service.compute_suggested_readiness's `recommend_deload`/
// `trending_worse`) for the single-session readiness slider — this reuses
// that exact same signal after a program day gets saved, to catch
// "fatigue is genuinely accumulating" even in a week the fixed schedule
// never flagged, instead of waiting for the calendar to catch up.
//
// Deliberately conservative about where it's allowed to act: only the very
// next, not-yet-started week (never touches a week already underway or
// already the scheduled deload), and it downgrades that whole week the
// same way the engine's own deload_mode does server-side (progression_
// engine.py's _prescribe_volume: flat 2 sets, lighter load/holds/work) so
// a deloaded week looks and behaves like every other deload in the app,
// not like a one-off nerf.
// ------------------------------------------------------------
function checkSignalDeload(weekNumber){
  if(!S.lastProgram) return;
  var nextWeek = S.lastProgram.program.find(function(w){ return w.week_number === weekNumber + 1; });
  if(!nextWeek || nextWeek.is_deload) return; // already scheduled, or no such week - nothing to add
  var alreadyStarted = Object.keys(S.programSavedDays).some(function(k){ return k.indexOf((weekNumber + 1) + '|') === 0; });
  if(alreadyStarted) return; // don't retroactively deload a week the person is already partway through

  fetch(API_BASE + '/api/v1/readiness/suggested?athlete_id=' + encodeURIComponent(ATHLETE_ID) +
    '&sport=' + encodeURIComponent(S.lastProgram.sport), {headers: authHeaders()})
    .then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); })
    .then(function(data){
      if(!data.recommend_deload) return;
      // Re-check right before applying - state (which week is "next"/
      // already-started) could have shifted while this request was in flight.
      if(nextWeek.is_deload) return;
      var stillNotStarted = !Object.keys(S.programSavedDays).some(function(k){ return k.indexOf((weekNumber + 1) + '|') === 0; });
      if(!stillNotStarted) return;

      nextWeek.is_deload = true;
      nextWeek.deload_reason = 'signal';
      nextWeek.deload_explanation = data.explanation;
      nextWeek.days.forEach(function(d){
        d.deload_mode = true;
        (d.prescribed_workout || []).forEach(function(ex){
          ex.prescription = applyWeekDeloadStep(ex.prescription);
          ex.prescription.progression_note = 'Auto-deload — ' + data.explanation;
          ex.prescription.autoregulated = true;
        });
      });
      showToast('Week ' + (weekNumber + 1) + ' flagged as an extra deload based on your recent recovery trend.');
      if(S.programWeek === weekNumber || S.programWeek === weekNumber + 1){ renderProgramWeek(S.lastProgram); }
    })
    .catch(function(){ /* best-effort signal - a failed check just means no auto-deload this time */ });
}
// ------------------------------------------------------------
// v5.19 fix: applyWeekDeloadStep's magnitudes were an independent, hand-
// rolled approximation of the server's real deload math - the exact "four
// uncoordinated deload signals" gap the v5.17 pass flagged and explicitly
// left unfixed as "a bigger design decision than this pass's scope."
// The *decision* of which signal gets to trigger a deload (fixed calendar
// week vs. this file's signal-triggered week) is still a real, unresolved
// design question, genuinely out of scope for a mechanical fix - but the
// *magnitude* of what a deload actually does once triggered has no such
// ambiguity: backend/services/progression_engine.py's _prescribe_volume_core
// already defines exactly what a deloaded exercise looks like for every
// prescription type, and this file was silently reimplementing a different,
// close-but-not-equal version of it (flat -15 percentage points on load
// instead of the server's multiplicative x0.8, a uniform 0.7x reps cut
// applied to types the server never touches on deload, a work/rest ratio
// change with different numbers than the server's per-energy-system
// ratios, and a distance cut applied to Carry exercises the server doesn't
// touch at all during deload - only Carry's LOAD gets cut). Rewritten to
// mirror _prescribe_volume_core's actual per-type deload branches exactly
// (same constants, same conditionals), so a signal-triggered deload here
// produces the identical numbers a server-side deload_mode=true response
// would have produced for the same exercise - not a coincidentally-similar
// approximation. See that function's own deload branches for the source
// of truth every constant below is copied from.
// ------------------------------------------------------------
var CONDITIONING_DELOAD_REST_RATIO = {
  'Alactic': 8,      // matches work_s * 8 in _prescribe_volume_core
  'Aerobic': 0.7,
  'Lactic': 2.2,
  'Mixed': 2.5,       // also the default when energy_system is absent
};
function applyWeekDeloadStep(p){
  var result = Object.assign({}, p);
  if(result.type === 'strength'){
    // Matches every is_loaded_strength/kb_ballistic/carry-adjacent branch:
    // load_pct_1rm = round(load_pct_1rm * 0.8) - multiplicative, not a flat
    // percentage-point cut, so it scales correctly at both low and high
    // starting %1RM instead of over- or under-cutting at the extremes.
    var oldPct = result.load_pct_1rm;
    if(oldPct != null){
      var newPct = Math.max(20, Math.round(oldPct * 0.8));
      if(result.working_weight_kg != null){
        result.working_weight_kg = result.working_weight_kg * (newPct / oldPct);
      }
      result.load_pct_1rm = newPct;
    }
  } else if(result.type === 'isolation'){
    // Matches: iso_reps = max(10, iso_reps - 2) - a flat rep cut with a
    // floor of 10, not a percentage cut (isolation reps never scale
    // proportionally server-side).
    if(result.reps != null){ result.reps = Math.max(10, result.reps - 2); }
  } else if(result.type === 'strength_bodyweight'){
    // Matches: the bodyweight-equipment loaded-strength branch and the
    // Core/Grip branch both leave `reps` completely untouched on deload -
    // only `sets` drops to 2 (handled uniformly below, same as every
    // other type). A pull-up/push-up/plank-variant's rep target doesn't
    // change in a deload week server-side; only volume (sets) does.
  } else if(result.type === 'conditioning'){
    // Matches: work_seconds is NEVER reduced on deload for ANY energy
    // system server-side - only the work:rest ratio changes (rest gets
    // longer, work stays exactly as prescribed). work_seconds is left
    // untouched here; rest_seconds is recomputed from it using the same
    // per-energy-system ratio the server uses (falls back to "Mixed"'s
    // 2.5 when energy_system wasn't set, matching the server's own
    // default branch).
    var ratio = CONDITIONING_DELOAD_REST_RATIO[result.energy_system] || CONDITIONING_DELOAD_REST_RATIO.Mixed;
    if(result.work_seconds != null){
      result.rest_seconds = Math.round(result.work_seconds * ratio);
    }
  } else if(result.type === 'isometric'){
    // Matches: hold_s = round(hold_s * 0.7)
    if(result.hold_seconds != null){ result.hold_seconds = Math.max(5, Math.round(result.hold_seconds * 0.7)); }
  } else if(result.type === 'carry'){
    // Matches: load_pct_bodyweight = round(load_pct_bodyweight * 0.8) -
    // distance_meters is NEVER touched during deload server-side (only
    // Ruck March, a different type below, cuts distance).
    if(result.load_pct_bodyweight != null){
      result.load_pct_bodyweight = Math.round(result.load_pct_bodyweight * 0.8);
    }
  } else if(result.type === 'ruck'){
    // Matches: distance_km = round(distance_km * 0.6, 1), then
    // duration_minutes recomputed from the new distance at the same
    // 12 min/km pace the server uses - not scaled independently.
    if(result.distance_km != null){
      result.distance_km = Math.round(result.distance_km * 0.6 * 10) / 10;
      result.duration_minutes = Math.round(result.distance_km * 12);
    }
  }
  // 'technical' and any other type: server applies no per-exercise deload
  // adjustment beyond sets=2 (handled uniformly below) - left untouched
  // here too, matching that exactly rather than guessing at a cut.
  result.sets = Math.min(result.sets || 2, 2); // matches progression_engine.py's flat deload sets=2
  return result;
}

