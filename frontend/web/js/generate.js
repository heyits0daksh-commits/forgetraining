'use strict';

// ============================================================
// GENERATE
// ============================================================

function collectPayload(){
  var payload = {
    mode:S.mode,
    sport:S.sport,
    experience_level:S.experience,
    equipment_available: S.equipment.size ? Array.from(S.equipment) : ['Bodyweight'],
    readiness:S.readiness,
    conditioning_emphasis:S.conditioningEmphasis,
    session_duration_minutes:S.sessionDuration,
    training_emphasis:S.emphasis,
    injuries:Array.from(S.injuries),
    // Optional {injury_name: rehab_stage} narrowing - see injury-browser.js's
    // buildInjuryStagesPayload docstring for why this can be null instead of {}.
    injury_stages: buildInjuryStagesPayload('wiz'),
    // Optional {injury_name: side} - see buildInjurySidesPayload's docstring.
    injury_sides: buildInjurySidesPayload('wiz'),
    // Without this, every "Generate Prescription" call used the engine's
    // default seed (0), so the same request (same sport/equipment/
    // injuries/level) always rotated to the exact same "near-tied"
    // exercise - most visibly Powerlifting's thin Core/Bracing pool
    // (only 3 real candidates), which always resolved to Front Plank no
    // matter how many times you regenerated. A fresh seed per call lets
    // _pick_with_variety actually rotate, same as program_builder.py
    // already does per week/day.
    variety_seed: Math.floor(Math.random() * 1000000),
    biometrics:{
      height_cm: numVal('bioHeight'),
      weight_kg: inputToKg(numVal('bioWeight')),
      bench_press_1rm: inputToKg(numVal('bioBench')),
      squat_1rm: inputToKg(numVal('bioSquat')),
      deadlift_1rm: inputToKg(numVal('bioDeadlift')),
      pullups_max_reps: numVal('bioPullups'),
      pushups_max_reps: numVal('bioPushups'),
      sex: document.getElementById('bioSex').value || null
    }
  };
  if(S.recoveryEnabled){
    payload.readiness_inputs = {
      sleep_hours: numVal('riSleep'),
      soreness: numVal('riSoreness'),
      stress: numVal('riStress'),
      energy: numVal('riEnergy'),
      motivation: numVal('riMotivation')
    };
  }
  if(S.mode === 'custom'){
    payload.selected_exercise_ids = Array.from(S.selectedExercises.keys());
  }
  return payload;
}
function numVal(id){
  var v = parseFloat(document.getElementById(id).value);
  return isNaN(v) ? 0 : v;
}

var _genToken = 0;
var _genController = null;
function cancelGenerate(){
  _genToken++; // any in-flight response is now stale and gets ignored
  if(_genController){ try{ _genController.abort(); }catch(e){} _genController = null; }
}
document.getElementById('btnCancelLoading').addEventListener('click', function(){
  cancelGenerate();
  show('screen-setup');
});

function generate(){
  // Snapshots whatever was just confirmed (full wizard or quick session) as
  // the athlete's saved profile - see profile.js. Every future visit
  // restores this instead of asking again.
  saveAthleteProfile();
  var lt = document.getElementById('loadingText');
  if(lt) lt.textContent = 'Building your session…';
  document.getElementById('btnCancelLoading').parentNode.style.display = '';
  show('screen-loading');
  var payload = collectPayload();
  cancelGenerate();
  var myToken = _genToken;
  var controller = (typeof AbortController !== 'undefined') ? new AbortController() : null;
  _genController = controller;
  var timer = setTimeout(function(){ if(controller) controller.abort(); }, 60000);
  fetch(API_BASE + '/api/v1/generate-workout', {
    method:'POST',
    headers: jsonAuthHeaders(),
    signal: controller ? controller.signal : undefined,
    body:JSON.stringify(payload)
  })
  .then(function(r){ return r.json().then(function(body){ return {ok:r.ok, body:body}; }); })
  .then(function(res){
    clearTimeout(timer);
    if(myToken !== _genToken) return; // cancelled while waiting
    if(!res.ok){
      show('screen-setup');
      showErrorModal(extractErrorMessage(res.body, 'The engine could not build a prescription from what was entered. Double check your inputs and try again.'), {title:'Couldn\'t generate your workout'});
      return;
    }
    S.sessionLog = {};
    res.body._usedInjuries = payload.injuries || [];
    res.body._usedInjuryStages = payload.injury_stages || {};
    res.body._usedInjurySides = payload.injury_sides || {};
    res.body._usedEquipment = payload.equipment_available || [];
    res.body._usedBiometrics = payload.biometrics;
    if(payload.mode === 'custom'){
      applyCustomPrescriptions(res.body.prescribed_workout);
      // Carried through purely for display (results-render.js / history) -
      // never sent back to the engine, same as the prescription fields above.
      res.body._customWorkoutName = customWorkoutDisplayName();
      res.body._customWarmup = S.customWarmup.slice();
      res.body._customGroups = S.customGroups;
    }
    S.lastResult = res.body;
    S.lastResultOriginal = JSON.parse(JSON.stringify(res.body));
    S.quickStart = false;
    renderResults(res.body);
    show('screen-results');
  })
  .catch(function(){
    clearTimeout(timer);
    if(myToken !== _genToken) return; // cancelled on purpose
    // Back to the wizard with everything still filled in, instead of a
    // dead-end error screen that throws away the whole setup.
    show('screen-setup');
    showErrorModal('We couldn\'t reach the server, or it took too long to answer. Your choices are still here — check your connection and try again.', {title:'Couldn\'t generate your workout'});
  });
}

// Custom Mode means every number is the person's own, not the engine's -
// the engine still runs its equipment/injury/strength/level safety checks
// against whatever was picked, but in custom mode an unsafe pick is no
// longer dropped from the session - it comes back with a `safety_warning`
// attached instead (see progression_engine.py), and every prescription
// field here (sets/reps/weight/rest/notes) is exactly what was typed into
// each chip on the exercise-picker step (S.selectedExercises) - nothing
// falls back to an engine default - still fully editable afterwards on the
// results screen via renderPrescriptionEditable.
function applyCustomPrescriptions(prescribedWorkout){
  (prescribedWorkout || []).forEach(function(ex){
    var pick = S.selectedExercises.get(ex.id);
    ex.prescription = {
      type: 'custom',
      sets: (pick && pick.sets) || 3,
      reps: (pick && pick.reps) || 10,
      rest_seconds: (pick && pick.rest_seconds != null) ? pick.rest_seconds : 60,
      working_weight_kg: (pick && pick.weight_kg) || 0,
      notes: (pick && pick.notes) || '',
      // Advanced fields (all optional/Custom-Mode-only — see
      // custom-workout-builder.js) - exactly what was typed into the
      // picker's chip, nothing engine-derived.
      rpe: pick ? pick.rpe : null,
      rir: pick ? pick.rir : null,
      tempo: (pick && pick.tempo) || '',
      set_type: (pick && pick.set_type) || 'working',
      warmup_sets: (pick && pick.warmup_sets) || 0,
      group: pick ? pick.group : null,
    };
  });
}

