'use strict';

// ============================================================
// IN-WORKOUT SWAP — injury/equipment-aware alternatives for one already-
// prescribed exercise (GET /api/v1/exercises/{id}/injury-swap), same
// underlying find_alternatives() search generate-workout already runs for
// exercises it excludes outright, offered here for one still in the
// session (e.g. sitting at injury_caution) without a full regeneration
// just to see options. Picking one re-runs generate-workout in custom mode
// with the swap applied, so equipment/injury/strength/level safety checks
// still apply to whatever gets picked (same contract the manual-template
// swap-options endpoint already documents).
// ============================================================

// {injury_name: rehab_stage} -> "injury_name:rehab_stage,injury_name:rehab_stage",
// the flattened query-string shape GET .../injury-swap?injury_stages= expects
// (see routes.py's get_injury_aware_swap docstring). Names never contain a
// literal ":" (they're the same taxonomy strings injuries= already sends),
// so a plain join is safe here.
function flattenInjuryStages(stagesMap){
  return Object.keys(stagesMap || {}).map(function(name){
    return name + ':' + stagesMap[name];
  }).join(',');
}

// Same flattening for {injury_name: side} -> "injury_name:side,..." (v5.15),
// the shape GET .../injury-swap?injury_sides= expects (see routes.py's
// get_injury_aware_swap docstring).
function flattenInjurySides(sidesMap){
  return Object.keys(sidesMap || {}).map(function(name){
    return name + ':' + sidesMap[name];
  }).join(',');
}

function toggleSwapPanel(exId){
  var panel = document.querySelector('[data-swap-panel="'+cssEsc(exId)+'"]');
  if(!panel) return;
  if(panel.dataset.open === '1'){ panel.innerHTML = ''; panel.dataset.open = '0'; return; }
  panel.dataset.open = '1';
  panel.innerHTML = '<div class="progression-note">Finding alternatives…</div>';
  var injuries = (S.lastResult && S.lastResult._usedInjuries) || [];
  var equipment = (S.lastResult && S.lastResult._usedEquipment) || [];
  var stages = (S.lastResult && S.lastResult._usedInjuryStages) || {};
  var sides = (S.lastResult && S.lastResult._usedInjurySides) || {};
  var url = API_BASE + '/api/v1/exercises/' + encodeURIComponent(exId) + '/injury-swap' +
    '?injuries=' + encodeURIComponent(injuries.join(',')) +
    '&equipment=' + encodeURIComponent(equipment.join(',')) +
    '&injury_stages=' + encodeURIComponent(flattenInjuryStages(stages)) +
    '&injury_sides=' + encodeURIComponent(flattenInjurySides(sides));
  fetch(url).then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); })
    .then(function(data){
      if(!data.options || !data.options.length){
        panel.innerHTML = '<div class="progression-note">No safe alternative found in the database for your equipment/injuries.</div>';
        return;
      }
      panel.innerHTML = data.options.map(function(o){
        var tag = o.rehab_pick ? '<span class="stag">rehab pick</span>'
          : (o.equipment_available ? '<span class="stag">you have this</span>' : '<span class="stag unavailable">need equipment</span>');
        return '<div class="swap-option"><div><div class="sname">'+esc(o.name)+'</div>'+
          '<div class="smeta">'+esc(o.equipment)+' · difficulty '+esc(String(o.difficulty||''))+'</div></div>'+
          '<div>'+tag+' <button type="button" class="btn small" data-swap-pick="'+esc(o.id)+'" data-swap-old="'+esc(exId)+'" data-swap-name="'+esc(o.name)+'">Use this</button></div>'+
          '</div>';
      }).join('');
    })
    .catch(function(){ panel.innerHTML = '<div class="progression-note">Could not load alternatives — check your connection.</div>'; });
}
function applySwap(oldId, newId, newName){
  if(!S.lastResult) return;
  var flat = flatExIds(S.lastResult);
  var pos = flat.indexOf(oldId);
  if(pos === -1) return;
  flat[pos] = newId;
  // Carry over each exercise's current name AND its own custom sets/reps/
  // weight (if it has one already) into the rebuilt selection - so
  // swapping one exercise doesn't reset everyone else's numbers back to
  // engine defaults. The freshly-picked swap has no prior prescription, so
  // it just gets the same 3x10x0 starting point any newly-added exercise gets.
  var byId = {};
  (S.lastResult.prescribed_workout || []).forEach(function(ex){
    var p = ex.prescription || {};
    byId[ex.id] = {name: ex.name, sets: p.sets || 3, reps: p.reps || 10, weight_kg: p.working_weight_kg || 0};
  });
  byId[newId] = {name: newName, sets:3, reps:10, weight_kg:0};
  S.mode = 'custom';
  S.selectedExercises = new Map(flat.map(function(id){ return [id, byId[id] || {name:id, sets:3, reps:10, weight_kg:0}]; }));
  showToast('Swapped — rebuilding your session with the new pick…');
  generate();
}

// ------------------------------------------------------------
// Program-day equivalent of the two functions above. A program day is
// session-shaped (session_structure + prescribed_workout, per the comment
// on removeExerciseFrom/moveExerciseIn), so the swap-options lookup itself
// is identical — only "how do I get a fully-prescribed replacement" and
// "where do I write the result back to" differ, since there's no single
// S.lastResult here: it has to be the one active day inside S.lastProgram,
// found via the same S.programWeek/S.programDayIndex the rest of the
// program-editing code already keys off. Rebuilding that day is done via
// generate-workout(mode=custom) using the sport/experience/equipment/
// injuries/biometrics the whole program was generated with (saved onto
// S.lastProgram by generateProgram) rather than a full program
// regeneration, so the other days/weeks are left untouched.
// ------------------------------------------------------------
function toggleProgramSwapPanel(exId){
  var panel = document.querySelector('[data-pg-swap-panel="'+cssEsc(exId)+'"]');
  if(!panel) return;
  if(panel.dataset.open === '1'){ panel.innerHTML = ''; panel.dataset.open = '0'; return; }
  panel.dataset.open = '1';
  panel.innerHTML = '<div class="progression-note">Finding alternatives…</div>';
  var injuries = (S.lastProgram && S.lastProgram._usedInjuries) || [];
  var equipment = (S.lastProgram && S.lastProgram._usedEquipment) || [];
  var stages = (S.lastProgram && S.lastProgram._usedInjuryStages) || {};
  var sides = (S.lastProgram && S.lastProgram._usedInjurySides) || {};
  var url = API_BASE + '/api/v1/exercises/' + encodeURIComponent(exId) + '/injury-swap' +
    '?injuries=' + encodeURIComponent(injuries.join(',')) +
    '&equipment=' + encodeURIComponent(equipment.join(',')) +
    '&injury_stages=' + encodeURIComponent(flattenInjuryStages(stages)) +
    '&injury_sides=' + encodeURIComponent(flattenInjurySides(sides));
  fetch(url).then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); })
    .then(function(data){
      if(!data.options || !data.options.length){
        panel.innerHTML = '<div class="progression-note">No safe alternative found in the database for your equipment/injuries.</div>';
        return;
      }
      panel.innerHTML = data.options.map(function(o){
        var tag = o.rehab_pick ? '<span class="stag">rehab pick</span>'
          : (o.equipment_available ? '<span class="stag">you have this</span>' : '<span class="stag unavailable">need equipment</span>');
        return '<div class="swap-option"><div><div class="sname">'+esc(o.name)+'</div>'+
          '<div class="smeta">'+esc(o.equipment)+' · difficulty '+esc(String(o.difficulty||''))+'</div></div>'+
          '<div>'+tag+' <button type="button" class="btn small" data-pg-swap-pick="'+esc(o.id)+'" data-pg-swap-old="'+esc(exId)+'" data-pg-swap-name="'+esc(o.name)+'">Use this</button></div>'+
          '</div>';
      }).join('');
    })
    .catch(function(){ panel.innerHTML = '<div class="progression-note">Could not load alternatives — check your connection.</div>'; });
}
function applyProgramSwap(oldId, newId, newName){
  if(!S.lastProgram) return;
  var week = S.lastProgram.program.find(function(w){ return w.week_number === S.programWeek; });
  var day = week && week.days[S.programDayIndex];
  if(!day) return;
  var flat = flatExIds(day);
  var pos = flat.indexOf(oldId);
  if(pos === -1) return;
  flat[pos] = newId;

  var payload = {
    mode: 'custom',
    sport: S.lastProgram.sport,
    experience_level: S.lastProgram.experience_level,
    equipment_available: (S.lastProgram._usedEquipment && S.lastProgram._usedEquipment.length) ? S.lastProgram._usedEquipment : ['Bodyweight'],
    readiness: S.lastProgram._usedReadiness,
    conditioning_emphasis: S.lastProgram._usedConditioningEmphasis,
    session_duration_minutes: S.lastProgram._usedDuration,
    injuries: S.lastProgram._usedInjuries || [],
    injury_stages: (S.lastProgram._usedInjuryStages && Object.keys(S.lastProgram._usedInjuryStages).length) ? S.lastProgram._usedInjuryStages : null,
    injury_sides: (S.lastProgram._usedInjurySides && Object.keys(S.lastProgram._usedInjurySides).length) ? S.lastProgram._usedInjurySides : null,
    biometrics: S.lastProgram._usedBiometrics,
    selected_exercise_ids: flat
  };

  showToast('Swapped — rebuilding this day with the new pick…');
  fetch(API_BASE + '/api/v1/generate-workout', {
    method: 'POST',
    headers: jsonAuthHeaders(),
    body: JSON.stringify(payload)
  })
    .then(function(r){ return r.json().then(function(body){ return {ok:r.ok, body:body}; }); })
    .then(function(res){
      if(!res.ok){
        showToast('Could not rebuild this day: ' + extractErrorMessage(res.body, 'engine error'));
        return;
      }
      // Only the parts of `day` that came from the exercise-selection engine
      // get replaced — phase label, deload flag, emphasis etc. all stay as
      // the program builder set them for this day.
      day.prescribed_workout = res.body.prescribed_workout;
      day.session_structure = res.body.session_structure;
      day.exercise_count = res.body.prescribed_workout.length;
      renderProgramWeek(S.lastProgram);
    })
    .catch(function(){ showToast('Could not rebuild this day — check your connection.'); });
}

// click delegation on results body: open modal / log a set
document.getElementById('resultBody').addEventListener('click', function(e){
  var whyToggleResult = e.target.closest('[data-why-toggle-result]');
  if(whyToggleResult){
    var rWhyId = whyToggleResult.getAttribute('data-why-toggle-result');
    var rWhyBox = whyToggleResult.nextElementSibling;
    var rNowOpen = !S.resultWhyOpen[rWhyId];
    S.resultWhyOpen[rWhyId] = rNowOpen;
    if(rWhyBox && rWhyBox.classList.contains('why')){ rWhyBox.classList.toggle('open', rNowOpen); }
    whyToggleResult.textContent = rNowOpen ? 'Hide why this exercise ▲' : 'Why this exercise? ▾';
    return;
  }
  var nameEl = e.target.closest('[data-open-modal]');
  if(nameEl){ openExerciseModal(nameEl.getAttribute('data-open-modal')); return; }
  var swapOpenBtn = e.target.closest('[data-swap-open]');
  if(swapOpenBtn){ toggleSwapPanel(swapOpenBtn.getAttribute('data-swap-open')); return; }
  var swapPickBtn = e.target.closest('[data-swap-pick]');
  if(swapPickBtn && !swapPickBtn.disabled){
    applySwap(swapPickBtn.getAttribute('data-swap-old'), swapPickBtn.getAttribute('data-swap-pick'), swapPickBtn.getAttribute('data-swap-name'));
    return;
  }
  var moveBtn = e.target.closest('[data-ex-move]');
  if(moveBtn && !moveBtn.disabled){
    var mvId = moveBtn.getAttribute('data-ex-id');
    var dir = moveBtn.getAttribute('data-ex-move') === 'up' ? -1 : 1;
    if(S.lastResult && moveExerciseIn(S.lastResult, mvId, dir)){ renderResults(S.lastResult); }
    return;
  }
  var removeBtn = e.target.closest('[data-ex-remove]');
  if(removeBtn){
    var rmId = removeBtn.getAttribute('data-ex-remove');
    if(S.lastResult){ removeExerciseFrom(S.lastResult, rmId); renderResults(S.lastResult); }
    return;
  }
  // "Keep Exercise" on a safety warning — the final decision always stays
  // with the person (see WorkoutRequest docstring); this just dismisses the
  // prompt in place, it never touches the exercise or its prescription.
  var keepBtn = e.target.closest('[data-warn-keep]');
  if(keepBtn){
    keepBtn.disabled = true;
    keepBtn.textContent = 'Kept ✓';
    return;
  }
  if(e.target.id === 'btnResetOrder' && S.lastResultOriginal){
    S.lastResult = JSON.parse(JSON.stringify(S.lastResultOriginal));
    renderResults(S.lastResult);
    return;
  }
  var toggleAddBtn = e.target.closest('[data-toggle-add-ex]');
  if(toggleAddBtn){
    S.addExPanelOpen = !S.addExPanelOpen;
    S.addExQuery = '';
    var resPanel = document.getElementById('resAddExPanel');
    if(resPanel){
      resPanel.style.display = S.addExPanelOpen ? 'block' : 'none';
      if(S.addExPanelOpen) renderAddExResults('res', '', '');
    }
    return;
  }
  var addPickBtn = e.target.closest('[data-add-ex-pick]');
  if(addPickBtn){
    if(!S.lastResult) return;
    addExerciseTo(S.lastResult, {
      id: addPickBtn.getAttribute('data-add-ex-pick'),
      name: addPickBtn.getAttribute('data-add-ex-name'),
      category: addPickBtn.getAttribute('data-add-ex-cat'),
      equipment: addPickBtn.getAttribute('data-add-ex-equip'),
      experience_level: addPickBtn.getAttribute('data-add-ex-lvl'),
      difficulty: parseInt(addPickBtn.getAttribute('data-add-ex-diff'), 10) || 1,
    });
    renderResults(S.lastResult);
    return;
  }

  var logBtn = e.target.closest('[data-log-set]');
  if(logBtn){
    var exId = logBtn.getAttribute('data-log-set');
    var exName = logBtn.getAttribute('data-log-name');
    var card = logBtn.closest('.exercise');
    var weight = inputToKg(parseFloat(card.querySelector('.logw').value));
    var reps = parseFloat(card.querySelector('.logr').value);
    if(isNaN(weight) || isNaN(reps) || reps <= 0){ return; }
    logSet(exId, exName, weight, reps);
    card.querySelector('.logw').value = '';
    card.querySelector('.logr').value = '';
  }
});

// Separate delegated listener for typing/changing values (number inputs +
// the add-exercise search box use 'input', not 'click') on the same
// resultBody container the click handler above covers.
var resAddExSearchTimer = null;
document.getElementById('resultBody').addEventListener('input', function(e){
  var pFieldEl = e.target.closest('[data-presc-field]');
  if(pFieldEl){
    setPrescriptionField(S.lastResult, pFieldEl.getAttribute('data-presc-exid'), pFieldEl.getAttribute('data-presc-field'), pFieldEl.value);
    return;
  }
  if(e.target.id === 'resAddExSearch'){
    S.addExQuery = e.target.value;
    clearTimeout(resAddExSearchTimer);
    resAddExSearchTimer = setTimeout(function(){ renderAddExResults('res', S.addExQuery, ''); }, 250);
  }
});

function computeScore(weight, reps){ return weight * (1 + reps/30); }
function bestPriorScore(exId){
  var best = 0;
  loadHistory().forEach(function(sess){
    (sess.log || []).forEach(function(entry){
      if(entry.exId === exId){
        entry.sets.forEach(function(s){ best = Math.max(best, computeScore(s.weight, s.reps)); });
      }
    });
  });
  return best;
}
function logSet(exId, exName, weight, reps){
  var score = computeScore(weight, reps);
  var isPR = score > bestPriorScore(exId) && score > 0;
  if(!S.sessionLog[exId]) S.sessionLog[exId] = {name: exName, sets:[]};
  S.sessionLog[exId].sets.push({weight:weight, reps:reps, isPR:isPR});
  var ex = S.lastResult && (S.lastResult.prescribed_workout || []).find(function(e){ return e.id === exId; });
  var isDb = ex && ex.equipment === 'Dumbbell';
  var container = document.querySelector('.logged-sets[data-logged-for="'+cssEsc(exId)+'"]');
  if(container){
    var row = document.createElement('div');
    row.className = 'logged-set';
    row.innerHTML = '<span>'+fmtWeight(weight)+(isDb ? ' each hand' : '')+' × '+reps+'</span>' + (isPR ? '<span class="pr">PR</span>' : '');
    container.appendChild(row);
  }
  if(isPR){
    checkOneRMUpdate(ex, weight, reps, S.lastResult && S.lastResult._usedBiometrics);
  }
}

