'use strict';

// ============================================================
// CUSTOM WORKOUT BUILDER — everything Custom Mode needs beyond the basic
// exercise picker (custom-mode-picker.js): superset/groups, a dedicated
// warm-up section, workout naming, local persistence (save/load/duplicate/
// delete), a pre-generate safety precheck with Keep/Remove, and a "last
// time" progression lookup. Nothing here talks to the engine's own
// exercise-selection/prescription logic — it only organizes what the
// person already picked (see WorkoutRequest.selected_exercise_ids docstring:
// "you choose the exercises, FORGE organizes/validates/tracks it").
// ============================================================

var SET_TYPE_LABELS = {
  working:'Working set', warmup:'Warm-up', backoff:'Back-off', top_set:'Top set',
  amrap:'AMRAP', drop_set:'Drop set', failure:'Failure set', rest_pause:'Rest-pause', cluster:'Cluster set',
};
function setTypeLabel(t){ return SET_TYPE_LABELS[t] || 'Working set'; }

// ------------------------------------------------------------
// GROUPS / SUPERSETS
// ------------------------------------------------------------
function nextGroupId(){
  var letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  for(var i=0;i<letters.length;i++){ if(!S.customGroups[letters[i]]) return letters[i]; }
  return 'G' + (S.customGroupOrder.length + 1); // fallback past 26 groups
}
function createCustomGroup(){
  var id = nextGroupId();
  S.customGroups[id] = {name: 'Superset ' + id};
  S.customGroupOrder.push(id);
  renderCustomGroupBar();
  renderExPickerSelected();
}
function renameCustomGroup(id, name){
  if(!S.customGroups[id]) return;
  S.customGroups[id].name = String(name || '').slice(0, 60) || ('Superset ' + id);
}
function deleteCustomGroup(id){
  if(!S.customGroups[id]) return;
  S.selectedExercises.forEach(function(pick){ if(pick.group === id) pick.group = null; });
  delete S.customGroups[id];
  S.customGroupOrder = S.customGroupOrder.filter(function(g){ return g !== id; });
  renderCustomGroupBar();
  renderExPickerSelected();
}
// Small bar above the selected-exercises list: existing groups (rename
// inline, delete) plus "+ New Group". Assigning a chip TO a group happens
// on the chip itself (the "Group" select inside its Advanced panel) —
// this bar only manages which groups exist.
function renderCustomGroupBar(){
  var el = document.getElementById('exGroupBar');
  if(!el) return;
  if(!S.customGroupOrder.length && !S.selectedExercises.size){
    el.innerHTML = '';
    return;
  }
  el.innerHTML = '<div class="group-bar-row">' +
    S.customGroupOrder.map(function(id){
      var count = Array.from(S.selectedExercises.values()).filter(function(p){ return p.group === id; }).length;
      return '<span class="group-chip"><input type="text" class="group-name-input" maxlength="60" value="'+esc(S.customGroups[id].name)+'" data-group-rename="'+esc(id)+'">' +
        '<span class="group-count">'+count+'</span>' +
        '<button type="button" data-group-delete="'+esc(id)+'" title="Delete this group (exercises stay, unlinked)">×</button></span>';
    }).join('') +
    '<button type="button" class="btn secondary small" id="btnNewGroup">+ New Group</button>' +
  '</div>';
  var newBtn = document.getElementById('btnNewGroup');
  if(newBtn) newBtn.addEventListener('click', createCustomGroup);
  el.querySelectorAll('[data-group-rename]').forEach(function(input){
    input.addEventListener('input', function(){
      renameCustomGroup(input.getAttribute('data-group-rename'), input.value);
    });
  });
  el.querySelectorAll('[data-group-delete]').forEach(function(btn){
    btn.addEventListener('click', function(){ deleteCustomGroup(btn.getAttribute('data-group-delete')); });
  });
}

// ------------------------------------------------------------
// WARM-UP SECTION — kept separate from the working-exercise list (S.selectedExercises)
// so it never counts toward working-set totals or gets treated as a "real" pick.
// ------------------------------------------------------------
function addWarmupItem(){
  var nameInput = document.getElementById('warmupNameInput');
  var detailInput = document.getElementById('warmupDetailInput');
  var name = (nameInput && nameInput.value || '').trim().slice(0, 120);
  var detail = (detailInput && detailInput.value || '').trim().slice(0, 120);
  if(!name) return;
  S.customWarmup.push({id: 'w' + Date.now() + Math.floor(Math.random()*1000), name: name, detail: detail});
  if(nameInput) nameInput.value = '';
  if(detailInput) detailInput.value = '';
  renderCustomWarmup();
}
function removeWarmupItem(id){
  S.customWarmup = S.customWarmup.filter(function(w){ return w.id !== id; });
  renderCustomWarmup();
}
function renderCustomWarmup(){
  var list = document.getElementById('customWarmupList');
  if(!list) return;
  if(!S.customWarmup.length){
    list.innerHTML = '<div class="empty">No warm-up items yet — optional, e.g. "5 min bike" or "Band external rotation — 2×15".</div>';
    return;
  }
  list.innerHTML = S.customWarmup.map(function(w){
    return '<div class="warmup-item" data-warmup-id="'+esc(w.id)+'">' +
      '<span>'+esc(w.name)+(w.detail ? ' <span class="exmeta">— '+esc(w.detail)+'</span>' : '')+'</span>' +
      '<button type="button" data-warmup-remove="'+esc(w.id)+'" title="Remove">×</button>' +
    '</div>';
  }).join('');
  list.querySelectorAll('[data-warmup-remove]').forEach(function(btn){
    btn.addEventListener('click', function(){ removeWarmupItem(btn.getAttribute('data-warmup-remove')); });
  });
}
var warmupAddBtnEl = document.getElementById('warmupAddBtn');
if(warmupAddBtnEl) warmupAddBtnEl.addEventListener('click', addWarmupItem);

// ------------------------------------------------------------
// WORKOUT NAME
// ------------------------------------------------------------
function customWorkoutDisplayName(){
  return (S.customWorkoutName && S.customWorkoutName.trim()) || 'Custom Workout';
}
var customNameInputEl = document.getElementById('customWorkoutNameInput');
if(customNameInputEl){
  customNameInputEl.addEventListener('input', function(){
    S.customWorkoutName = customNameInputEl.value.slice(0, 80);
  });
}

// ------------------------------------------------------------
// PERSISTENCE — saved custom workouts. localStorage is always the
// source of truth for rendering (works offline, no login required), and
// syncs to the backend (/api/v1/custom-workouts) in the background
// whenever the person is logged in — same "local write always happens,
// server sync is fire-and-forget on top of it" pattern as history.js's
// syncSessionToBackend/fetchHistory. Logged-out use is unchanged from
// before: purely local, per-device, exactly like it always was.
// ------------------------------------------------------------
var CUSTOM_WORKOUTS_KEY = 'forge_custom_workouts';
function loadSavedCustomWorkouts(){
  try{ return JSON.parse(localStorage.getItem(CUSTOM_WORKOUTS_KEY)) || []; }
  catch(e){ return []; }
}
function persistSavedCustomWorkouts(arr){
  try{ localStorage.setItem(CUSTOM_WORKOUTS_KEY, JSON.stringify(arr)); }
  catch(e){ /* storage unavailable — ignore, same fallback as history.js */ }
}
function serializeCurrentCustomWorkout(){
  return {
    id: S.customEditingWorkoutId || ('cw' + Date.now()),
    name: customWorkoutDisplayName(),
    savedAt: new Date().toISOString(),
    sport: S.sport,
    experience: S.experience,
    exercises: Array.from(S.selectedExercises.entries()),
    groups: S.customGroups,
    groupOrder: S.customGroupOrder,
    warmup: S.customWarmup,
  };
}
// Fire-and-forget POST to /api/v1/custom-workouts, keyed by the same `id`
// the local record already uses as its client-generated identity — so
// saving again from this or another device updates the same synced row
// instead of creating a duplicate (see CustomWorkoutDB's upsert-on-
// client_id docstring). Never blocks or errors the local save above.
function syncCustomWorkoutToBackend(record){
  if(!S.currentUser) return; // logged-out: local-only, same as before this feature
  fetch(API_BASE + '/api/v1/custom-workouts', {
    method: 'POST',
    headers: jsonAuthHeaders(),
    body: JSON.stringify({
      client_id: record.id,
      name: record.name,
      sport: record.sport || null,
      experience: record.experience || null,
      exercises: record.exercises || [],
      groups: record.groups || {},
      group_order: record.groupOrder || [],
      warmup: record.warmup || []
    })
  }).catch(function(){ /* local copy already saved — will sync next time */ });
}
function syncCustomWorkoutDeleteToBackend(id){
  if(!S.currentUser) return;
  fetch(API_BASE + '/api/v1/custom-workouts/' + encodeURIComponent(id), {
    method: 'DELETE',
    headers: authHeaders()
  }).catch(function(){});
}
function saveCurrentCustomWorkout(){
  if(!S.selectedExercises.size){ showToast('Add at least one exercise before saving.', 'error'); return; }
  var record = serializeCurrentCustomWorkout();
  var all = loadSavedCustomWorkouts();
  var idx = all.findIndex(function(w){ return w.id === record.id; });
  if(idx === -1) all.push(record); else all[idx] = record;
  persistSavedCustomWorkouts(all);
  S.customEditingWorkoutId = record.id;
  syncCustomWorkoutToBackend(record);
  renderSavedCustomWorkoutsList();
  showToast(S.currentUser
    ? 'Saved "' + record.name + '" — synced to your account.'
    : 'Saved "' + record.name + '" on this device. Log in to sync it across devices.');
}
function loadCustomWorkoutById(id){
  var all = loadSavedCustomWorkouts();
  var record = all.filter(function(w){ return w.id === id; })[0];
  if(!record) return;
  S.selectedExercises = new Map(record.exercises);
  S.customGroups = record.groups || {};
  S.customGroupOrder = record.groupOrder || [];
  S.customWarmup = record.warmup || [];
  S.customWorkoutName = record.name || '';
  S.customEditingWorkoutId = record.id;
  if(customNameInputEl) customNameInputEl.value = S.customWorkoutName;
  renderExercisePicker();
  renderExPickerSelected();
  renderCustomWarmup();
  renderSavedCustomWorkoutsList();
  updateWizardNav();
  showToast('Loaded "' + record.name + '".');
}
function duplicateCustomWorkoutById(id){
  var all = loadSavedCustomWorkouts();
  var record = all.filter(function(w){ return w.id === id; })[0];
  if(!record) return;
  var copy = JSON.parse(JSON.stringify(record));
  copy.id = 'cw' + Date.now();
  copy.name = record.name + ' (copy)';
  copy.savedAt = new Date().toISOString();
  all.push(copy);
  persistSavedCustomWorkouts(all);
  syncCustomWorkoutToBackend(copy);
  renderSavedCustomWorkoutsList();
  showToast('Duplicated as "' + copy.name + '".');
}
function deleteCustomWorkoutById(id){
  var all = loadSavedCustomWorkouts().filter(function(w){ return w.id !== id; });
  persistSavedCustomWorkouts(all);
  syncCustomWorkoutDeleteToBackend(id);
  if(S.customEditingWorkoutId === id) S.customEditingWorkoutId = null;
  renderSavedCustomWorkoutsList();
}
// Pulls synced workouts from the backend (when logged in) and merges them
// into the local list by id — a synced record wins over a same-id local
// one (the backend is the cross-device source of truth once logged in),
// but any purely-local record from before login/on another device is kept
// too rather than dropped. Called once when Custom Mode's saved-workouts
// panel is opened; falls back to the local list alone if unreachable.
function syncCustomWorkoutsFromBackend(cb){
  if(!S.currentUser){ if(cb) cb(); return; }
  fetch(API_BASE + '/api/v1/custom-workouts', {headers: authHeaders()})
    .then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); })
    .then(function(rows){
      var local = loadSavedCustomWorkouts();
      var byId = {};
      local.forEach(function(w){ byId[w.id] = w; });
      rows.forEach(function(r){
        byId[r.client_id] = {
          id: r.client_id, name: r.name, savedAt: r.updated_at,
          sport: r.sport, experience: r.experience, exercises: r.exercises,
          groups: r.groups, groupOrder: r.group_order, warmup: r.warmup
        };
      });
      persistSavedCustomWorkouts(Object.values(byId));
      if(cb) cb();
    })
    .catch(function(){ if(cb) cb(); });
}
function renderSavedCustomWorkoutsList(){
  var el = document.getElementById('savedCustomWorkoutsList');
  if(!el) return;
  var all = loadSavedCustomWorkouts();
  if(!all.length){
    el.innerHTML = '<div class="empty">No saved custom workouts yet.</div>';
    return;
  }
  el.innerHTML = all.slice().reverse().map(function(w){
    return '<div class="saved-workout-row" data-saved-id="'+esc(w.id)+'">' +
      '<div class="saved-workout-info"><b>'+esc(w.name)+'</b>' +
        '<span class="exmeta">'+w.exercises.length+' exercise'+(w.exercises.length===1?'':'s')+' · '+esc(w.sport||'')+'</span></div>' +
      '<div class="saved-workout-actions">' +
        '<button type="button" class="btn secondary small" data-saved-load="'+esc(w.id)+'">Load</button>' +
        '<button type="button" class="btn secondary small" data-saved-dup="'+esc(w.id)+'">Duplicate</button>' +
        '<button type="button" class="btn secondary small danger" data-saved-del="'+esc(w.id)+'">Delete</button>' +
      '</div>' +
    '</div>';
  }).join('');
  el.querySelectorAll('[data-saved-load]').forEach(function(btn){
    btn.addEventListener('click', function(){ loadCustomWorkoutById(btn.getAttribute('data-saved-load')); });
  });
  el.querySelectorAll('[data-saved-dup]').forEach(function(btn){
    btn.addEventListener('click', function(){ duplicateCustomWorkoutById(btn.getAttribute('data-saved-dup')); });
  });
  el.querySelectorAll('[data-saved-del]').forEach(function(btn){
    btn.addEventListener('click', function(){
      showConfirm('Delete this saved custom workout? This can\'t be undone.', {title:'Delete workout?'}).then(function(ok){
        if(ok) deleteCustomWorkoutById(btn.getAttribute('data-saved-del'));
      });
    });
  });
}
var saveCustomBtnEl = document.getElementById('btnSaveCustomWorkout');
if(saveCustomBtnEl) saveCustomBtnEl.addEventListener('click', saveCurrentCustomWorkout);

// ------------------------------------------------------------
// PROGRESSION — "last time" lookup from logged history (see history.js /
// pr-suggestion.js's log shape: {exId, name, sets:[{weight,reps,isPR}]}).
// Read-only and display-only: never changes today's prescription, exactly
// per the Custom Mode rule that only the person's own typed numbers ship.
// ------------------------------------------------------------
function ensureCustomHistoryLoaded(cb){
  if(S.customHistoryCache !== null){ cb(); return; }
  fetchHistory(function(hist){
    S.customHistoryCache = hist || [];
    cb();
  });
}
function lastPerformanceNote(exId){
  if(!S.customHistoryCache) return '';
  var best = null, bestDate = null;
  S.customHistoryCache.forEach(function(rec){
    (rec.log || []).forEach(function(entry){
      if(entry.exId !== exId || !entry.sets || !entry.sets.length) return;
      var d = new Date(rec.date);
      if(!bestDate || d > bestDate){ bestDate = d; best = entry; }
    });
  });
  if(!best) return '';
  var lastSet = best.sets[best.sets.length - 1];
  if(!lastSet) return '';
  return 'Last time: ' + fmtWeight(lastSet.weight||0) + ' × ' + (lastSet.reps||0);
}

// ------------------------------------------------------------
// PRE-GENERATE SAFETY PRECHECK — Custom Mode's engine safety checks
// (equipment/injury/strength/level, see progression_engine.py) only run
// once the request actually hits /api/v1/generate-workout. This calls that
// same endpoint a beat early, purely to surface any `safety_warning` on the
// review step BEFORE the person commits, with an explicit Keep/Remove per
// flagged exercise (Removing re-runs this precheck; Keeping just dismisses
// the prompt — the final Generate Prescription call happens exactly the
// same either way, per generate.js).
// ------------------------------------------------------------
function runCustomSafetyPrecheck(){
  var box = document.getElementById('customSafetyPrecheck');
  if(!box) return;
  if(!S.selectedExercises.size){ box.innerHTML = ''; return; }
  box.innerHTML = '<div class="empty">Checking your picks against equipment/injury/strength/level constraints…</div>';
  var payload = collectPayload();
  fetch(API_BASE + '/api/v1/generate-workout', {
    method:'POST', headers: jsonAuthHeaders(), body: JSON.stringify(payload)
  }).then(function(r){ return r.json().then(function(body){ return {ok:r.ok, body:body}; }); })
    .then(function(res){
      if(!res.ok){ box.innerHTML = ''; return; }
      var warnings = {};
      (res.body.prescribed_workout || []).forEach(function(ex){
        if(ex.safety_warning) warnings[ex.id] = ex.safety_warning;
      });
      S.customSafetyWarnings = warnings;
      renderCustomSafetyPrecheck();
    })
    .catch(function(){ box.innerHTML = ''; });
}
function renderCustomSafetyPrecheck(){
  var box = document.getElementById('customSafetyPrecheck');
  if(!box) return;
  var warnings = S.customSafetyWarnings || {};
  var ids = Object.keys(warnings);
  if(!ids.length){ box.innerHTML = '<div class="callout blue">No safety conflicts found against your equipment/injury/strength/level settings.</div>'; return; }
  box.innerHTML = '<div class="callout danger"><b>'+ids.length+' pick(s) flagged — review before you generate.</b></div>' +
    ids.map(function(id){
      var pick = S.selectedExercises.get(id);
      if(!pick) return '';
      var w = warnings[id];
      return '<div class="caution safety-precheck-item" data-precheck-id="'+esc(id)+'">' +
        '<b>'+esc(pick.name)+'</b> — '+esc(w.note||'')+
        (w.reasons && w.reasons.length ? '<div class="reason">'+esc(w.reasons.join(' · '))+'</div>' : '') +
        '<div class="precheck-actions">' +
          '<button type="button" class="btn secondary small" data-precheck-keep="'+esc(id)+'">Keep Exercise</button>' +
          '<button type="button" class="btn secondary small danger" data-precheck-remove="'+esc(id)+'">Remove Exercise</button>' +
        '</div>' +
      '</div>';
    }).join('');
  box.querySelectorAll('[data-precheck-keep]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var item = btn.closest('.safety-precheck-item');
      if(item) item.classList.add('kept');
      btn.disabled = true;
      btn.textContent = 'Kept ✓';
    });
  });
  box.querySelectorAll('[data-precheck-remove]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var id = btn.getAttribute('data-precheck-remove');
      S.selectedExercises.delete(id);
      delete (S.customSafetyWarnings || {})[id];
      renderReview();
      runCustomSafetyPrecheck();
    });
  });
}

// ------------------------------------------------------------
// REVIEW-STEP SUMMARY EXTRAS — appended into #reviewCard by renderReview()
// (injury-browser.js) when S.mode === 'custom'. Computed entirely from
// what's already in S (no network round trip needed for the summary
// itself — the safety precheck above is the only part that calls out).
// ------------------------------------------------------------
function renderCustomReviewSummary(){
  var picks = Array.from(S.selectedExercises.values());
  if(!picks.length) return '';
  var totalWorkingSets = picks.reduce(function(sum, p){ return sum + (p.sets||0); }, 0);
  var totalWarmupSets = picks.reduce(function(sum, p){ return sum + (p.warmup_sets||0); }, 0) + S.customWarmup.length;
  // Rough duration estimate: ~45s of work per set, plus each set's own rest,
  // plus a flat couple of minutes for a warm-up block if one exists —
  // deliberately approximate (a display estimate, never fed back into any
  // prescription), same spirit as the wizard's own "~60 min" session-length picker.
  var estSeconds = picks.reduce(function(sum, p){
    return sum + (p.sets||0) * (45 + (p.rest_seconds!=null?p.rest_seconds:60));
  }, 0) + (S.customWarmup.length ? 300 : 0);
  var estMinutes = Math.max(5, Math.round(estSeconds / 60));
  var muscleGroups = Array.from(new Set(picks.map(function(p){ return p.category; }).filter(Boolean)));
  var equipmentUsed = Array.from(new Set(picks.map(function(p){ return p.equipment; }).filter(Boolean)));
  var groupedCount = picks.filter(function(p){ return p.group; }).length;

  var html = '<div class="section-title" style="margin-top:22px;">Custom Workout Summary</div>';
  html += row('Workout name', esc(customWorkoutDisplayName()));
  html += row('Exercises', String(picks.length) + (groupedCount ? ' ('+groupedCount+' in supersets)' : ''));
  html += row('Total working sets', String(totalWorkingSets) + (totalWarmupSets ? ' + ' + totalWarmupSets + ' warm-up' : ''));
  html += row('Estimated duration', '~' + estMinutes + ' min');
  if(muscleGroups.length) html += row('Muscle groups / categories', muscleGroups.map(esc).join(', '));
  if(equipmentUsed.length) html += row('Equipment', equipmentUsed.map(esc).join(', '));
  if(S.customWarmup.length){
    html += row('Warm-up', S.customWarmup.map(function(w){ return esc(w.name) + (w.detail ? ' ('+esc(w.detail)+')' : ''); }).join(' · '));
  }
  html += '<div class="section-title" style="margin-top:18px;">Exercise-by-Exercise</div>';
  var groupCounts = {};
  html += picks.map(function(p, i){
    var groupTag = '';
    if(p.group && S.customGroups[p.group]){
      groupCounts[p.group] = (groupCounts[p.group]||0) + 1;
      groupTag = '<span class="pill group-pill">'+esc(p.group)+groupCounts[p.group]+'</span> ';
    }
    var wDisplay = fmtWeight(p.weight_kg||0);
    var advBits = [];
    if(p.set_type && p.set_type !== 'working') advBits.push(setTypeLabel(p.set_type));
    if(p.rpe != null) advBits.push('RPE ' + p.rpe);
    if(p.rir != null) advBits.push('RIR ' + p.rir);
    if(p.tempo) advBits.push('Tempo ' + esc(p.tempo));
    if(p.warmup_sets) advBits.push(p.warmup_sets + ' warm-up sets');
    return '<div class="review-row"><span>'+groupTag+(i+1)+'. '+esc(p.name)+'</span>' +
      '<span>'+p.sets+'×'+p.reps+(p.weight_kg?' @ '+wDisplay:'')+' · Rest '+(p.rest_seconds||0)+'s' +
      (advBits.length ? '<div class="exmeta">'+advBits.join(' · ')+'</div>' : '') +
      '</span></div>';
  }).join('');
  html += '<div id="customSafetyPrecheck" style="margin-top:14px;"></div>';
  return html;
}
