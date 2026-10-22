'use strict';

// ============================================================
// PROGRAM BUILDER — CUSTOM DAYS (Custom Program mode)
// Lets a person build their own day-by-day exercise lists instead of
// picking a SPLIT_TEMPLATES preset - the Program Builder equivalent of
// custom-mode-picker.js, but per-day and without per-exercise
// prescription fields. Sets/reps/weight aren't picked here on purpose:
// the engine still owns week-to-week progression/deload/emphasis for a
// program (see ProgramRequest.custom_days / program_builder.py's
// mode="custom" branch, which still runs _apply_prescription_bias /
// _apply_week_progression / _apply_phase_volume_scaling on every custom
// day exactly like a preset one) - picking the exercises is the
// person's job, prescribing them week to week stays the program
// builder's.
// ============================================================

function nextPgCustomDayId(){ return 'pgday' + Date.now() + Math.floor(Math.random()*1000); }

function nextPgCustomDayLabel(){
  var letters = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  for(var i=0;i<letters.length;i++){
    var candidate = 'Day ' + letters[i];
    if(!S.pgCustomDays.some(function(d){ return d.label === candidate; })) return candidate;
  }
  return 'Day ' + (S.pgCustomDays.length + 1);
}

function ensurePgCustomDaysInit(){
  if(!S.pgCustomDays.length){
    var day = {id: nextPgCustomDayId(), label: 'Day A', exerciseIds: [], exerciseNames: {}};
    S.pgCustomDays.push(day);
    S.pgCustomActiveDayId = day.id;
  } else if(!S.pgCustomDays.some(function(d){ return d.id === S.pgCustomActiveDayId; })){
    S.pgCustomActiveDayId = S.pgCustomDays[0].id;
  }
}

function getPgActiveDay(){
  return S.pgCustomDays.find(function(d){ return d.id === S.pgCustomActiveDayId; }) || null;
}

function renderPgCustomDaysStep(){
  ensurePgCustomDaysInit();
  var repeatNote = document.getElementById('pgCustomDayRepeatNote');
  if(repeatNote) repeatNote.textContent = String(parseInt(document.getElementById('pgDays').value, 10) || 4);
  renderPgCustomDayTabs();
  syncPgCustomDayLabelInput();
  renderPgExercisePicker();
  renderPgExPickerSelected();
}

function syncPgCustomDayLabelInput(){
  var day = getPgActiveDay();
  var input = document.getElementById('pgCustomDayLabelInput');
  if(input) input.value = day ? day.label : '';
}

function renderPgCustomDayTabs(){
  var el = document.getElementById('pgCustomDayTabs');
  if(!el) return;
  el.innerHTML = S.pgCustomDays.map(function(d){
    var active = d.id === S.pgCustomActiveDayId;
    return '<div class="pg-day-tab'+(active?' active':'')+'" data-pg-day-tab="'+esc(d.id)+'">'+
      '<span>'+esc(d.label || 'Untitled')+'</span>'+
      '<span class="count-pill">'+d.exerciseIds.length+'</span>'+
      (S.pgCustomDays.length > 1 ? '<button type="button" data-pg-day-remove="'+esc(d.id)+'" title="Remove this day">×</button>' : '')+
    '</div>';
  }).join('');
  el.querySelectorAll('[data-pg-day-tab]').forEach(function(tab){
    tab.addEventListener('click', function(e){
      if(e.target.closest('[data-pg-day-remove]')) return;
      S.pgCustomActiveDayId = tab.getAttribute('data-pg-day-tab');
      renderPgCustomDayTabs();
      syncPgCustomDayLabelInput();
      renderPgExercisePicker();
      renderPgExPickerSelected();
    });
  });
  el.querySelectorAll('[data-pg-day-remove]').forEach(function(btn){
    btn.addEventListener('click', function(e){
      e.stopPropagation();
      removePgCustomDay(btn.getAttribute('data-pg-day-remove'));
    });
  });
}

function removePgCustomDay(id){
  if(S.pgCustomDays.length <= 1) return; // always keep at least one day
  S.pgCustomDays = S.pgCustomDays.filter(function(d){ return d.id !== id; });
  if(S.pgCustomActiveDayId === id) S.pgCustomActiveDayId = S.pgCustomDays[0].id;
  renderPgCustomDaysStep();
  updateProgramWizardNav();
}

document.getElementById('btnPgAddCustomDay').addEventListener('click', function(){
  var day = {id: nextPgCustomDayId(), label: nextPgCustomDayLabel(), exerciseIds: [], exerciseNames: {}};
  S.pgCustomDays.push(day);
  S.pgCustomActiveDayId = day.id;
  renderPgCustomDaysStep();
  updateProgramWizardNav();
});

document.getElementById('pgCustomDayLabelInput').addEventListener('input', function(e){
  var day = getPgActiveDay();
  if(!day) return;
  day.label = e.target.value.slice(0, 60);
  renderPgCustomDayTabs();
});

document.getElementById('pgExPickerSearch').addEventListener('input', function(e){
  S.pgExPickerQuery = e.target.value;
  renderPgExercisePicker();
});

function renderPgExercisePicker(){
  var results = document.getElementById('pgExPickerResults');
  var day = getPgActiveDay();
  if(!results || !day) return;
  results.innerHTML = '<div class="empty">Searching…</div>';
  var url = API_BASE + '/api/v1/exercises?limit=60' + (S.pgExPickerQuery ? '&search=' + encodeURIComponent(S.pgExPickerQuery) : '');
  fetch(url).then(function(r){ return r.json(); }).then(function(body){
    // The active day may have changed while this request was in flight -
    // re-resolve it rather than trusting the closed-over `day`.
    var activeDay = getPgActiveDay();
    if(!activeDay) return;
    var list = body.exercises || [];
    if(!list.length){ results.innerHTML = '<div class="empty">No exercises match that search.</div>'; return; }
    results.innerHTML = list.map(function(ex){
      var added = activeDay.exerciseIds.indexOf(ex.id) !== -1;
      return '<div class="ex-pick-item'+(added?' added':'')+'" data-pg-pick-id="'+esc(ex.id)+'" data-pg-pick-name="'+esc(ex.name)+'">'+
        '<span>'+esc(ex.name)+'<span class="exmeta">'+esc(ex.equipment||'')+' · '+esc(ex.category||'')+'</span></span>'+
        '<button type="button" class="btn secondary small" data-pg-pick-toggle="'+esc(ex.id)+'">'+(added?'Added ✓':'Add')+'</button>'+
      '</div>';
    }).join('');
    results.querySelectorAll('[data-pg-pick-toggle]').forEach(function(btn){
      btn.addEventListener('click', function(){
        var item = btn.closest('.ex-pick-item');
        var id = item.getAttribute('data-pg-pick-id');
        var name = item.getAttribute('data-pg-pick-name');
        var d = getPgActiveDay();
        if(!d) return;
        var idx = d.exerciseIds.indexOf(id);
        if(idx !== -1){ d.exerciseIds.splice(idx, 1); }
        else { d.exerciseIds.push(id); d.exerciseNames[id] = name; }
        renderPgExercisePicker();
        renderPgExPickerSelected();
        renderPgCustomDayTabs();
        updateProgramWizardNav();
      });
    });
  }).catch(function(){
    results.innerHTML = '<div class="empty">Couldn\'t reach the engine to search exercises.</div>';
  });
}

function renderPgExPickerSelected(){
  var el = document.getElementById('pgExPickerSelected');
  var countEl = document.getElementById('pgExPickerCount');
  var day = getPgActiveDay();
  if(!el || !day) return;
  countEl.textContent = day.exerciseIds.length;
  if(!day.exerciseIds.length){
    el.innerHTML = '<div class="empty">Nothing picked yet for this day — search above and add exercises.</div>';
    return;
  }
  el.innerHTML = day.exerciseIds.map(function(id, i){
    var name = day.exerciseNames[id] || id;
    return '<div class="ex-chip-custom" data-pg-chip="'+esc(id)+'">'+
      '<div class="ex-chip-name"><span class="drag-handle" title="Drag to reorder">⠿</span> '+esc(name)+
        '<button type="button" data-pg-remove-pick="'+esc(id)+'" title="Remove exercise">×</button></div>'+
      '<div class="ex-chip-reorder">'+
        '<button type="button" data-pg-pick-move="up" data-pg-pick-id="'+esc(id)+'" title="Move earlier"'+(i===0?' disabled':'')+'>↑</button>'+
        '<button type="button" data-pg-pick-move="down" data-pg-pick-id="'+esc(id)+'" title="Move later"'+(i===day.exerciseIds.length-1?' disabled':'')+'>↓</button>'+
      '</div>'+
    '</div>';
  }).join('');
  el.querySelectorAll('[data-pg-remove-pick]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var id = btn.getAttribute('data-pg-remove-pick');
      var idx = day.exerciseIds.indexOf(id);
      if(idx !== -1) day.exerciseIds.splice(idx, 1);
      renderPgExPickerSelected();
      renderPgExercisePicker();
      renderPgCustomDayTabs();
      updateProgramWizardNav();
    });
  });
  el.querySelectorAll('[data-pg-pick-move]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var id = btn.getAttribute('data-pg-pick-id');
      var dir = btn.getAttribute('data-pg-pick-move') === 'up' ? -1 : 1;
      var pos = day.exerciseIds.indexOf(id);
      var newPos = pos + dir;
      if(newPos < 0 || newPos >= day.exerciseIds.length) return;
      var tmp = day.exerciseIds[pos]; day.exerciseIds[pos] = day.exerciseIds[newPos]; day.exerciseIds[newPos] = tmp;
      renderPgExPickerSelected();
    });
  });
  // Touch-first drag reorder (see drag-reorder.js) - the ↑/↓ buttons above
  // stay as the fallback for anyone who prefers tapping over dragging.
  enableDragReorder(el, {
    itemSelector: '.ex-chip-custom',
    getId: function(chip){ return chip.getAttribute('data-pg-chip'); },
    onReorder: function(idsInOrder){
      day.exerciseIds = idsInOrder;
      renderPgExPickerSelected();
    }
  });
}

// The Custom Program toggle in the "basics" step (mirrors #customModeToggle
// on the Train wizard) - flips S.pgMode, hides the split dropdown, and lets
// getProgramWizardStepIds() insert the "customDays" step.
(function(){
  var toggle = document.getElementById('pgCustomModeToggle');
  var splitField = document.getElementById('pgSplitField');
  toggle.checked = S.pgMode === 'custom';
  if(splitField) splitField.style.display = S.pgMode === 'custom' ? 'none' : '';
  toggle.addEventListener('change', function(e){
    S.pgMode = e.target.checked ? 'custom' : 'preset';
    if(splitField) splitField.style.display = S.pgMode === 'custom' ? 'none' : '';
    if(S.pgMode === 'custom') ensurePgCustomDaysInit();
    updateProgramWizardNav();
  });
})();
