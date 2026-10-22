'use strict';

// ============================================================
// PROGRAM BUILDER
// ============================================================

// Same formula as recalcReadinessFromRecovery() in wizard-setup.js (single
// session flow) - kept as a separate function since the Program Builder's
// step uses its own pg-prefixed input IDs, but the math is identical so
// the two flows produce the same readiness for the same inputs.
function recalcPgReadinessFromRecovery(){
  var sleepH = parseFloat(document.getElementById('pgRiSleep').value);
  var soreness = parseFloat(document.getElementById('pgRiSoreness').value);
  var stress = parseFloat(document.getElementById('pgRiStress').value);
  var energy = parseFloat(document.getElementById('pgRiEnergy').value);
  var motivation = parseFloat(document.getElementById('pgRiMotivation').value);
  var sleepScore = Math.min(sleepH / 8, 1) * 100;
  var sorenessScore = (5 - soreness) / 4 * 100;
  var stressScore = (5 - stress) / 4 * 100;
  var energyScore = (energy - 1) / 4 * 100;
  var motivationScore = (motivation - 1) / 4 * 100;
  var score = Math.round((sleepScore + sorenessScore + stressScore + energyScore + motivationScore) / 5);
  score = Math.max(1, Math.min(100, score));
  document.getElementById('pgReadiness').value = score;
  document.getElementById('pgReadinessReadout').textContent = score + '%';
  var pgrmi = document.getElementById('pgReadinessManualInput');
  if(pgrmi){ pgrmi.value = score; document.getElementById('pgReadinessManualReadout').textContent = score + '%'; }
}

function populateProgramForm(){
  var m = S.metadata;
  if(!m) return;

  // Primary Goal is no longer asked on this step (see index.html's Program
  // Basics markup) - always defaults to "General Fitness" behind the
  // scenes, same as before this was hidden.
  var goalSel = document.getElementById('pgGoal');
  goalSel.innerHTML = (S.goals.length ? S.goals : ['General Fitness']).map(function(g){
    return '<option value="'+esc(g)+'"'+(g==='General Fitness'?' selected':'')+'>'+esc(g)+'</option>';
  }).join('');

  // Sport was already chosen on the Train wizard's discipline step - the
  // hidden #pgSport select still carries the real value for every other
  // bit of code that reads it, but the person only ever sees the
  // read-only #pgSportDisplay chip (icon + name) below, not an editable
  // dropdown asking again.
  var sportSel = document.getElementById('pgSport');
  var defaultSport = S.sport || (m.sports.length ? m.sports.slice().sort()[0] : '');
  sportSel.innerHTML = m.sports.map(function(s){
    return '<option value="'+esc(s)+'"'+(s===defaultSport?' selected':'')+'>'+esc(s)+'</option>';
  }).join('');
  var sportDisplay = document.getElementById('pgSportDisplay');
  if(sportDisplay){
    var t = themeFor(defaultSport);
    sportDisplay.innerHTML = '<span class="icon">'+esc(t.mono)+'</span><span>'+esc(defaultSport)+'</span>';
  }

  var expSel = document.getElementById('pgExperience');
  expSel.innerHTML = m.experience_levels.map(function(l){
    return '<option value="'+esc(l)+'"'+(l===S.experience?' selected':'')+'>'+esc(l)+'</option>';
  }).join('');

  var splitSel = document.getElementById('pgSplit');
  var splitOptions = '<option value="auto">Auto (recommended for you)</option>' +
    S.splits.map(function(sp){
      return '<option value="'+esc(sp.id)+'">'+esc(sp.name)+' — '+esc(sp.supported_days_per_week.join('/'))+' days/wk</option>';
    }).join('');
  splitSel.innerHTML = splitOptions;
  splitSel.addEventListener('change', updateSplitInfo);
  updateSplitInfo();

  var eqEl = document.getElementById('pgEquipmentChecks');
  var pgEquipmentSet = new Set(S.equipment.size ? Array.from(S.equipment) : ['Bodyweight']);
  pgEquipmentSet.add('Bodyweight');
  renderEquipmentGroups(eqEl, pgEquipmentSet, S.equipmentCatalog);
  eqEl._equipmentSet = pgEquipmentSet;

  var ri = document.getElementById('pgReadiness');
  ri.value = S.readiness;
  S.pgReadinessManual = false;
  recalcPgReadinessFromRecovery();

  ['pgRiSleep','pgRiSoreness','pgRiStress','pgRiEnergy','pgRiMotivation'].forEach(function(id){
    var input = document.getElementById(id);
    var readout = document.getElementById(id + 'Readout');
    var fmt = id === 'pgRiSleep' ? function(v){ return v+'h'; } : function(v){ return v+'/5'; };
    readout.textContent = fmt(input.value);
    input.addEventListener('input', function(){
      readout.textContent = fmt(input.value);
      if(!S.pgReadinessManual) recalcPgReadinessFromRecovery();
    });
  });

  var pgrmi = document.getElementById('pgReadinessManualInput');
  pgrmi.value = S.readiness;
  document.getElementById('pgReadinessManualReadout').textContent = pgrmi.value + '%';
  pgrmi.addEventListener('input', function(){
    S.pgReadinessManual = true;
    document.getElementById('pgReadinessManualReadout').textContent = pgrmi.value + '%';
    ri.value = pgrmi.value;
    document.getElementById('pgReadinessReadout').textContent = pgrmi.value + '%';
  });

  populateConditioningSelect('pgConditioningEmphasis', 'pgConditioningEmphasisHint', S.pgConditioningEmphasis, function(v){
    S.pgConditioningEmphasis = v;
  });

  populateTrainingPhaseSelect();

  // Seed the program's own injury selection from whatever's currently in
  // the wizard (usually nothing, at startup), then it's edited independently
  // from here on - same pattern as pgEquipmentSet above.
  S.pgInjuries.clear();
  S.injuries.forEach(function(name){ S.pgInjuries.add(name); });
  // Same seed-then-edit-independently pattern for each injury's rehab
  // stage - only copy stages for injuries actually carried over above, so
  // a stale S.injuryStages entry from an injury the wizard no longer has
  // checked can't leak into the freshly-seeded pgInjuryStages.
  S.pgInjuryStages = {};
  S.pgInjuries.forEach(function(name){
    if(S.injuryStages[name]) S.pgInjuryStages[name] = S.injuryStages[name];
  });
  // Same seed-then-edit-independently pattern for each injury's side
  // (v5.15) - only copy sides for injuries actually carried over above,
  // same "no stale leakage" reasoning as pgInjuryStages above.
  S.pgInjurySides = {};
  S.pgInjuries.forEach(function(name){
    if(S.injurySides[name]) S.pgInjurySides[name] = S.injurySides[name];
  });
  renderInjuryBrowser('pg');

  // Biometrics are no longer seeded here - prefillProgramBiometricsFromProfile()
  // (program-wizard-steps.js), called from show('screen-program') in
  // nav-control.js right after this function runs, is now the single place
  // that fills pgBio* and decides whether the Operator Biometrics step can
  // be skipped. Keeping that logic in one place (instead of this function
  // also copying values without setting the skip flag) is what was causing
  // Operator Biometrics to show up pre-filled with real-looking numbers yet
  // never actually skip.
}

// Combat Sports & Rugby S&C Manual, Part 9.3 - the competition-calendar
// phase (Off-Season through Post-Competition). Optional: "Auto" (empty
// value, the default) omits training_phase from the request entirely and
// the split/volume come from the days/goal/sport heuristic exactly as
// before this field existed. Picking a phase overrides which split gets
// chosen and scales weekly volume per that phase's table - see
// program_builder.PHASE_GUIDANCE and this fetch's own /api/v1/training-phases.
function populateTrainingPhaseSelect(){
  var sel = document.getElementById('pgTrainingPhase');
  var hint = document.getElementById('pgTrainingPhaseHint');
  if(!sel) return;
  var phases = S.trainingPhases || [];
  sel.innerHTML = '<option value="">Auto (no phase — use goal/split as set above)</option>' +
    phases.map(function(p){
      return '<option value="'+esc(p.id)+'">'+esc(p.id)+' — '+esc(p.duration || '')+'</option>';
    }).join('');
  function reflectHint(){
    var chosen = phases.find(function(p){ return p.id === sel.value; });
    hint.textContent = chosen ? (chosen.lifting_focus + ' ' + chosen.conditioning_focus) : '';
  }
  reflectHint();
  sel.addEventListener('change', reflectHint);
}

function updateSplitInfo(){
  var splitSel = document.getElementById('pgSplit');
  var info = document.getElementById('pgSplitInfo');
  var chosen = S.splits.find(function(sp){ return sp.id === splitSel.value; });
  if(!chosen){ info.style.display = 'none'; return; }
  info.style.display = 'block';
  info.innerHTML = '<b>'+esc(chosen.name)+'.</b> '+esc(chosen.description);
}

function updateProgramInjuryNote(){
  // Program Builder has its own standalone injury browser now (bound to
  // S.pgInjuries) - just keep its selected-count badge and joint filter
  // chips in sync whenever this screen becomes visible.
  updateInjSelectedCount('pg');
}

