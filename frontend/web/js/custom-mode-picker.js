'use strict';

// ============================================================
// CUSTOM MODE — exercise picker (search /api/v1/exercises, build
// selected_exercise_ids for the generate-workout request)
// ============================================================

function renderExercisePicker(){
  var results = document.getElementById('exPickerResults');
  if(!results) return;
  results.innerHTML = '<div class="empty">Searching…</div>';
  var url = API_BASE + '/api/v1/exercises?limit=60' + (S.exPickerQuery ? '&search=' + encodeURIComponent(S.exPickerQuery) : '');
  fetch(url).then(function(r){ return r.json(); }).then(function(body){
    var list = body.exercises || [];
    if(!list.length){ results.innerHTML = '<div class="empty">No exercises match that search.</div>'; return; }
    results.innerHTML = list.map(function(ex){
      var added = S.selectedExercises.has(ex.id);
      return '<div class="ex-pick-item'+(added?' added':'')+'" data-pick-id="'+esc(ex.id)+'" data-pick-name="'+esc(ex.name)+'" data-pick-category="'+esc(ex.category||'')+'" data-pick-equipment="'+esc(ex.equipment||'')+'">'+
        '<span>'+esc(ex.name)+'<span class="exmeta">'+esc(ex.equipment||'')+' · '+esc(ex.category||'')+'</span></span>'+
        '<button type="button" class="btn secondary small" data-pick-toggle="'+esc(ex.id)+'">'+(added?'Added ✓':'Add')+'</button>'+
      '</div>';
    }).join('');
    results.querySelectorAll('[data-pick-toggle]').forEach(function(btn){
      btn.addEventListener('click', function(){
        var item = btn.closest('.ex-pick-item');
        var id = item.getAttribute('data-pick-id');
        var name = item.getAttribute('data-pick-name');
        if(S.selectedExercises.has(id)){ S.selectedExercises.delete(id); }
        else {
          S.selectedExercises.set(id, {
            name:name, sets:3, reps:10, weight_kg:0, rest_seconds:60, notes:'',
            category: item.getAttribute('data-pick-category') || '',
            equipment: item.getAttribute('data-pick-equipment') || '',
            // Advanced fields — optional, Custom-Mode-only, tucked behind
            // each chip's "Advanced" toggle (see renderExPickerSelected).
            rpe:null, rir:null, tempo:'', set_type:'working', warmup_sets:0, group:null,
          });
        }
        renderExercisePicker();
        renderExPickerSelected();
        updateWizardNav();
      });
    });
  }).catch(function(){
    results.innerHTML = '<div class="empty">Couldn\'t reach the engine to search exercises.</div>';
  });
  renderExPickerSelected();
}
// Reorders S.selectedExercises (a Map, so iteration order === insertion
// order) by deleting and re-setting every entry in the wanted sequence.
// Map has no native "move" op, so this is the whole-map rebuild that does
// it - cheap enough for a picker list that's realistically a handful of
// exercises. The rebuilt order is exactly what Array.from(...keys()) sends
// as selected_exercise_ids, and the engine preserves that order verbatim
// for custom-mode sessions (no role/transfer re-sort), so reordering here
// is reordering the final session, not just the picker's own list.
function reorderSelectedExercises(idsInOrder){
  var snapshot = idsInOrder.map(function(id){ return [id, S.selectedExercises.get(id)]; });
  S.selectedExercises.clear();
  snapshot.forEach(function(pair){ S.selectedExercises.set(pair[0], pair[1]); });
}
// Set types a person can tag a chip with - purely descriptive (see
// SET_TYPE_LABELS in custom-workout-builder.js for the badge text shown in
// the review/results screens). Never changes validation: a bodyweight AMRAP
// or failure set is exactly as valid as a straight working set.
var SET_TYPES = ['working','warmup','backoff','top_set','amrap','drop_set','failure','rest_pause','cluster'];

function renderExPickerSelected(){
  var el = document.getElementById('exPickerSelected');
  var countEl = document.getElementById('exPickerCount');
  if(!el) return;
  countEl.textContent = S.selectedExercises.size;
  renderCustomGroupBar();
  if(!S.selectedExercises.size){
    el.innerHTML = '<div class="empty">Nothing picked yet — search above and add exercises.</div>';
    return;
  }
  // Each picked exercise gets its own sets/reps/weight/rest/notes (plus,
  // behind "Advanced", RPE/RIR/tempo/set-type/warm-up-sets/group) right
  // here - Custom Mode means the person decides all of it, not the engine,
  // so there's nothing to "generate" for any of these fields; what's typed
  // here is exactly what carries through to the built session (see
  // applyCustomPrescriptions in generate.js), in exactly this order. The
  // order of `ids` (S.selectedExercises' Map insertion order) IS the final
  // session order - reordering only ever happens via the ↑/↓ buttons or
  // drag-and-drop below, never automatically.
  var ids = Array.from(S.selectedExercises.keys());
  var groupCounts = {}; // groupId -> running A1/A2/... counter while rendering
  el.innerHTML = ids.map(function(id, i){
    var pick = S.selectedExercises.get(id);
    var wDisplay = S.unit === 'lb' ? Math.round(kgToLb(pick.weight_kg||0)) : (pick.weight_kg||0);
    var advOpen = !!S.customPickerAdvancedOpen[id];
    var groupBadge = '';
    if(pick.group && S.customGroups[pick.group]){
      groupCounts[pick.group] = (groupCounts[pick.group]||0) + 1;
      groupBadge = '<span class="pill group-pill" title="'+esc(S.customGroups[pick.group].name)+'">'+
        esc(pick.group)+groupCounts[pick.group]+'</span>';
    }
    var lastPerf = lastPerformanceNote(id);
    return '<div class="ex-chip-custom'+(pick.group?' grouped':'')+'" data-pick-chip="'+esc(id)+'">'+
      '<div class="ex-chip-name"><span class="drag-handle" title="Drag to reorder">⠿</span>'+groupBadge+' '+esc(pick.name)+
        (lastPerf ? '<span class="last-perf" title="From your logged history">'+esc(lastPerf)+'</span>' : '')+
        '<button type="button" data-remove-pick="'+esc(id)+'" title="Remove exercise">×</button></div>'+
      '<div class="ex-chip-fields">'+
        '<label>Sets <input type="number" class="presc-input" min="1" value="'+(pick.sets||1)+'" data-pick-field="sets" data-pick-id="'+esc(id)+'"></label>'+
        '<label>Reps <input type="number" class="presc-input" min="1" value="'+(pick.reps||1)+'" data-pick-field="reps" data-pick-id="'+esc(id)+'"></label>'+
        '<label>Weight <input type="number" class="presc-input" min="0" step="'+(S.unit==='lb'?'5':'2.5')+'" value="'+wDisplay+'" data-pick-field="weight_kg" data-pick-id="'+esc(id)+'"> '+(S.unit==='lb'?'lb':'kg')+'</label>'+
        '<label>Rest <input type="number" class="presc-input" min="0" step="5" value="'+(pick.rest_seconds!=null?pick.rest_seconds:60)+'" data-pick-field="rest_seconds" data-pick-id="'+esc(id)+'"> s</label>'+
        '<div class="ex-chip-reorder">'+
          '<button type="button" data-pick-move="up" data-pick-id="'+esc(id)+'" title="Move earlier"'+(i===0?' disabled':'')+'>↑</button>'+
          '<button type="button" data-pick-move="down" data-pick-id="'+esc(id)+'" title="Move later"'+(i===ids.length-1?' disabled':'')+'>↓</button>'+
        '</div>'+
      '</div>'+
      '<textarea class="ex-chip-notes" rows="1" placeholder="Notes for this exercise (cues, tempo, why you picked it)…" data-pick-field="notes" data-pick-id="'+esc(id)+'">'+esc(pick.notes||'')+'</textarea>'+
      '<button type="button" class="why-toggle adv-toggle" data-adv-toggle="'+esc(id)+'">'+(advOpen?'Hide advanced ▲':'Advanced (RPE, RIR, tempo, set type…) ▾')+'</button>'+
      '<div class="ex-chip-advanced'+(advOpen?' open':'')+'">'+
        '<label>Set type <select class="presc-input" data-pick-field="set_type" data-pick-id="'+esc(id)+'">'+
          SET_TYPES.map(function(t){ return '<option value="'+t+'"'+(pick.set_type===t?' selected':'')+'>'+esc(setTypeLabel(t))+'</option>'; }).join('')+
        '</select></label>'+
        '<label>Warm-up sets <input type="number" class="presc-input" min="0" value="'+(pick.warmup_sets||0)+'" data-pick-field="warmup_sets" data-pick-id="'+esc(id)+'"></label>'+
        '<label>RPE <input type="number" class="presc-input" min="0" max="10" step="0.5" placeholder="—" value="'+(pick.rpe!=null?pick.rpe:'')+'" data-pick-field="rpe" data-pick-id="'+esc(id)+'"></label>'+
        '<label>RIR <input type="number" class="presc-input" min="0" max="10" placeholder="—" value="'+(pick.rir!=null?pick.rir:'')+'" data-pick-field="rir" data-pick-id="'+esc(id)+'"></label>'+
        '<label>Tempo <input type="text" class="presc-input" maxlength="12" placeholder="e.g. 2-1-X-1" value="'+esc(pick.tempo||'')+'" data-pick-field="tempo" data-pick-id="'+esc(id)+'"></label>'+
        '<label>Group <select class="presc-input" data-pick-group="'+esc(id)+'">'+
          '<option value="">— standalone —</option>'+
          S.customGroupOrder.map(function(gid){ return '<option value="'+esc(gid)+'"'+(pick.group===gid?' selected':'')+'>'+esc(gid)+' — '+esc(S.customGroups[gid].name)+'</option>'; }).join('')+
        '</select></label>'+
      '</div>'+
    '</div>';
  }).join('');
  el.querySelectorAll('[data-remove-pick]').forEach(function(btn){
    btn.addEventListener('click', function(){
      S.selectedExercises.delete(btn.getAttribute('data-remove-pick'));
      renderExPickerSelected();
      renderExercisePicker();
      updateWizardNav();
    });
  });
  el.querySelectorAll('[data-adv-toggle]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var id = btn.getAttribute('data-adv-toggle');
      S.customPickerAdvancedOpen[id] = !S.customPickerAdvancedOpen[id];
      renderExPickerSelected();
    });
  });
  el.querySelectorAll('[data-pick-move]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var id = btn.getAttribute('data-pick-id');
      var dir = btn.getAttribute('data-pick-move') === 'up' ? -1 : 1;
      var order = Array.from(S.selectedExercises.keys());
      var pos = order.indexOf(id);
      var newPos = pos + dir;
      if(newPos < 0 || newPos >= order.length) return;
      var tmp = order[pos]; order[pos] = order[newPos]; order[newPos] = tmp;
      reorderSelectedExercises(order);
      renderExPickerSelected();
    });
  });
  el.querySelectorAll('[data-pick-field]').forEach(function(input){
    input.addEventListener('input', function(){
      var pick = S.selectedExercises.get(input.getAttribute('data-pick-id'));
      if(!pick) return;
      var field = input.getAttribute('data-pick-field');
      if(field === 'weight_kg'){
        var w = parseFloat(input.value);
        pick.weight_kg = isNaN(w) || w < 0 ? 0 : inputToKg(w);
      } else if(field === 'notes'){
        pick.notes = String(input.value == null ? '' : input.value).slice(0, 500);
      } else if(field === 'tempo'){
        pick.tempo = String(input.value == null ? '' : input.value).slice(0, 12);
      } else if(field === 'set_type'){
        pick.set_type = input.value || 'working';
      } else if(field === 'rpe' || field === 'rir'){
        if(input.value === ''){ pick[field] = null; return; }
        var v = parseFloat(input.value);
        var max = field === 'rpe' ? 10 : 10;
        pick[field] = isNaN(v) ? null : Math.max(0, Math.min(max, v));
      } else {
        var floor = (field === 'rest_seconds' || field === 'warmup_sets') ? 0 : 1;
        var n = parseInt(input.value, 10);
        pick[field] = isNaN(n) || n < floor ? floor : n;
      }
    });
  });
  el.querySelectorAll('[data-pick-group]').forEach(function(select){
    select.addEventListener('change', function(){
      var pick = S.selectedExercises.get(select.getAttribute('data-pick-group'));
      if(!pick) return;
      pick.group = select.value || null;
      renderExPickerSelected();
    });
  });
  // Touch-first drag reorder (see drag-reorder.js) - the ↑/↓ buttons above
  // stay as the fallback for anyone who prefers tapping over dragging.
  // Dropping never changes group membership, only position - same "the
  // order you set is the order that ships" rule as reorderSelectedExercises.
  enableDragReorder(el, {
    itemSelector: '.ex-chip-custom',
    getId: function(chip){ return chip.getAttribute('data-pick-chip'); },
    onReorder: function(idsInOrder){
      reorderSelectedExercises(idsInOrder);
      renderExPickerSelected();
    }
  });
}

function checkboxHtml(value, checked){
  return '<label class="check'+(checked?' checked':'')+'" data-value="'+esc(value)+'">'+
    '<input type="checkbox" '+(checked?'checked':'')+'>'+'<span>'+esc(value)+'</span></label>';
}
// Equipment-browser version: same checkbox, plus an exercise-count badge
// (e.g. "112") so a person can see, before picking it, roughly how much of
// the database an item unlocks - a flat alphabetical list couldn't show
// this at all.
function checkboxHtmlEquipment(row, checked){
  return '<label class="check'+(checked?' checked':'')+'" data-value="'+esc(row.equipment)+'" title="'+
    esc(row.movement_categories.join(', '))+'">'+
    '<input type="checkbox" '+(checked?'checked':'')+'>'+'<span>'+esc(row.equipment)+'</span>'+
    '<span class="eq-count">'+row.exercise_count+'</span></label>';
}
// Which open-group Set + selected-count element belongs to which instance of
// the equipment browser - 'wiz' (Train wizard, S.equipment) and 'pg'
// (Program Builder, S.pgEquipmentSet, resolved by the caller and passed in
// as targetSet already, same pattern as the injury browser's INJ_IDS/injState).
function eqOpenSetFor(targetSet){
  return targetSet === S.equipment ? S.eqOpenGroups : S.pgEqOpenGroups;
}
// Same instance-resolution idea as eqOpenSetFor above, for the search box.
function eqSearchStateFor(targetSet){
  return targetSet === S.equipment
    ? {get query(){return S.eqSearchQuery;}, set query(v){S.eqSearchQuery = v;}, noResultsId:'eqNoResults'}
    : {get query(){return S.pgEqSearchQuery;}, set query(v){S.pgEqSearchQuery = v;}, noResultsId:'pgEqNoResults'};
}
function updateEqSelectedCount(container, targetSet){
  var el = container.id === 'pgEquipmentChecks'
    ? document.getElementById('pgEqSelectedCount')
    : document.getElementById('eqSelectedCount');
  if(el) el.textContent = targetSet.size + ' selected';
}
// Groups the flat equipment list into browsable, collapsible sections (Free
// Weights, Machines, Strongman, ...) - same accordion pattern as the injury
// joint browser below, so a 67-item checkbox list doesn't dump onto the
// screen all at once. Each header shows item/exercise counts and, once
// picked, a "N selected" pill; hovering an item still shows which movement
// patterns it covers (e.g. Kettlebell spans Horizontal Push/Pull/Hinge/
// Squat/Carry/Core, not just "Swing"). A group auto-opens if it already has
// a selection in it, so existing picks are never hidden behind a collapsed
// header. A search query (same box/behavior as the injury browser) narrows
// every group down to matching equipment names and force-opens any group
// with a match, hiding groups left with nothing. Falls back to a flat list
// if the catalog endpoint didn't load (keeps the UI working even against an
// older backend without /api/v1/equipment).
function renderEquipmentGroups(container, targetSet, catalog){
  var searchState = eqSearchStateFor(targetSet);
  var query = searchState.query.trim().toLowerCase();
  var noResultsEl = document.getElementById(searchState.noResultsId);
  if(!catalog || !catalog.length){
    var flatItems = (S.metadata.equipment || []).filter(function(eq){
      return !query || eq.toLowerCase().indexOf(query) !== -1;
    });
    container.innerHTML = '<div class="checks">' + flatItems.map(function(eq){
      return checkboxHtml(eq, targetSet.has(eq));
    }).join('') + '</div>';
    if(noResultsEl) noResultsEl.style.display = (query && !flatItems.length) ? 'block' : 'none';
    wireChecks(container, targetSet);
    updateEqSelectedCount(container, targetSet);
    return;
  }
  var openSet = eqOpenSetFor(targetSet);
  var groups = {};
  var order = [];
  catalog.forEach(function(row){
    if(!groups[row.group]){ groups[row.group] = []; order.push(row.group); }
    groups[row.group].push(row);
  });
  var anyVisible = false;
  container.innerHTML = order.map(function(groupName){
    var rows = groups[groupName];
    var visibleRows = query
      ? rows.filter(function(r){
          return r.equipment.toLowerCase().indexOf(query) !== -1 ||
            r.movement_categories.some(function(m){ return m.toLowerCase().indexOf(query) !== -1; });
        })
      : rows;
    if(query && !visibleRows.length) return '';  // hide whole group on an active, non-matching search
    anyVisible = true;
    var totalExercises = rows.reduce(function(sum, r){ return sum + r.exercise_count; }, 0);
    var selectedInGroup = rows.filter(function(r){ return targetSet.has(r.equipment); }).length;
    // Only a search match or an explicit tap on the group header opens it -
    // having items selected inside (e.g. from a one-tap preset like "Full
    // Commercial Gym") no longer force-opens the group. Otherwise picking a
    // preset would blow every group open at once into a wall of checkboxes,
    // defeating the point of having a preset in the first place. Browsing
    // is still one click away: tap the group name (e.g. "Free Weights") and
    // it opens, exactly like every other group.
    var isOpen = openSet.has(groupName) || (query && visibleRows.length > 0);
    return '<div class="eq-group'+(isOpen?' open':'')+(selectedInGroup?' has-selected':'')+'" data-group="'+esc(groupName)+'">'+
      '<div class="eq-group-head" data-toggle-group="'+esc(groupName)+'">'+
        '<h5>'+esc(groupName)+'</h5>'+
        '<span class="eq-group-note">'+
          (selectedInGroup ? '<span class="count-pill selected">'+selectedInGroup+' selected</span>' : '')+
          '<span class="count-pill">'+rows.length+' items · '+totalExercises+' exercises</span>'+
          '<span class="chev">▶</span>'+
        '</span>'+
      '</div>'+
      '<div class="eq-group-body"><div class="checks dense">'+
        visibleRows.map(function(row){ return checkboxHtmlEquipment(row, targetSet.has(row.equipment)); }).join('')+
      '</div></div></div>';
  }).join('');
  if(noResultsEl) noResultsEl.style.display = (query && !anyVisible) ? 'block' : 'none';

  container.querySelectorAll('[data-toggle-group]').forEach(function(head){
    head.addEventListener('click', function(){
      var groupName = head.getAttribute('data-toggle-group');
      var group = head.closest('.eq-group');
      if(openSet.has(groupName)){ openSet.delete(groupName); group.classList.remove('open'); }
      else { openSet.add(groupName); group.classList.add('open'); }
    });
  });
  wireChecks(container, targetSet);
  updateEqSelectedCount(container, targetSet);

  // Keep each group's "N selected" pill and the overall count accurate
  // without a full re-render, same approach the injury browser uses.
  container.querySelectorAll('.check').forEach(function(label){
    label.addEventListener('click', function(){
      updateEqSelectedCount(container, targetSet);
      var group = label.closest('.eq-group');
      var groupName = group.getAttribute('data-group');
      var count = group.querySelectorAll('.check.checked').length;
      var pill = group.querySelector('.count-pill.selected');
      var note = group.querySelector('.eq-group-note');
      if(count && !pill){
        pill = document.createElement('span');
        pill.className = 'count-pill selected';
        note.prepend(pill);
        group.classList.add('has-selected');
      }
      if(pill){
        if(count){ pill.textContent = count + ' selected'; }
        else { pill.remove(); group.classList.remove('has-selected'); }
      }
    });
  });
}
function wireChecks(container, targetSet){
  container.querySelectorAll('.check').forEach(function(label){
    label.addEventListener('click', function(e){
      e.preventDefault();
      var value = label.getAttribute('data-value');
      var input = label.querySelector('input');
      if(targetSet.has(value)){ targetSet.delete(value); input.checked = false; label.classList.remove('checked'); }
      else { targetSet.add(value); input.checked = true; label.classList.add('checked'); }
    });
  });
}

document.getElementById('eqSearchInput').addEventListener('input', function(e){
  S.eqSearchQuery = e.target.value;
  renderEquipmentGroups(document.getElementById('equipmentChecks'), S.equipment, S.equipmentCatalog);
});
document.getElementById('eqClearBtn').addEventListener('click', function(){
  S.equipment.clear();
  S.equipment.add('Bodyweight');
  renderEquipmentGroups(document.getElementById('equipmentChecks'), S.equipment, S.equipmentCatalog);
  var row = document.getElementById('eqPresetRow');
  if(row) row.querySelectorAll('.chip-btn').forEach(function(b){ b.classList.remove('active'); });
});
document.getElementById('pgEqSearchInput').addEventListener('input', function(e){
  S.pgEqSearchQuery = e.target.value;
  var pgEqEl = document.getElementById('pgEquipmentChecks');
  renderEquipmentGroups(pgEqEl, pgEqEl._equipmentSet, S.equipmentCatalog);
});
document.getElementById('pgEqClearBtn').addEventListener('click', function(){
  var pgEqEl = document.getElementById('pgEquipmentChecks');
  var pgSet = pgEqEl._equipmentSet;
  pgSet.clear();
  pgSet.add('Bodyweight');
  renderEquipmentGroups(pgEqEl, pgSet, S.equipmentCatalog);
  var row = document.getElementById('pgEqPresetRow');
  if(row) row.querySelectorAll('.chip-btn').forEach(function(b){ b.classList.remove('active'); });
});

// ---------- one-tap equipment presets ----------
// Groups drive the presets (not a hardcoded equipment list) so this stays
// correct automatically if the backend's EQUIPMENT_CATEGORIES ever changes.
//   bodyweight -> just the Bodyweight group
//   home       -> Bodyweight + Free Weights + Racks & Benches (what a
//                 well-equipped home/garage gym realistically has)
//   full       -> everything you'd find in a normal commercial gym
//                 (adds Machines + Conditioning + Grip & Accessory),
//                 leaving out Strongman/Combat Sport/Rehab specialty gear
//                 most commercial gyms don't stock
var EQ_PRESET_GROUPS = {
  bodyweight: ['Bodyweight'],
  home:       ['Bodyweight', 'Free Weights', 'Racks & Benches'],
  full:       ['Bodyweight', 'Free Weights', 'Racks & Benches', 'Machines', 'Conditioning', 'Grip & Accessory']
};
function applyEquipmentPreset(container, targetSet, preset){
  var allowedGroups = EQ_PRESET_GROUPS[preset];
  if(!allowedGroups) return;
  targetSet.clear();
  if(S.equipmentCatalog && S.equipmentCatalog.length){
    S.equipmentCatalog.forEach(function(row){
      if(allowedGroups.indexOf(row.group) !== -1) targetSet.add(row.equipment);
    });
  } else {
    // Catalog endpoint not loaded yet — fall back to just Bodyweight so the
    // set is never left empty (equipment step always needs at least one item).
    targetSet.add('Bodyweight');
  }
  // Collapse every group back down after applying a preset — see the
  // isOpen comment in renderEquipmentGroups for why selection alone should
  // never force a group open.
  eqOpenSetFor(targetSet).clear();
  renderEquipmentGroups(container, targetSet, S.equipmentCatalog);
}
function wireEquipmentPresetRow(rowId, container, getTargetSet){
  var row = document.getElementById(rowId);
  if(!row) return;
  row.addEventListener('click', function(e){
    var btn = e.target.closest('[data-eq-preset]');
    if(!btn) return;
    applyEquipmentPreset(container, getTargetSet(), btn.getAttribute('data-eq-preset'));
    row.querySelectorAll('.chip-btn').forEach(function(b){ b.classList.toggle('active', b === btn); });
  });
}
wireEquipmentPresetRow('eqPresetRow', document.getElementById('equipmentChecks'), function(){ return S.equipment; });
wireEquipmentPresetRow('pgEqPresetRow', document.getElementById('pgEquipmentChecks'), function(){ return document.getElementById('pgEquipmentChecks')._equipmentSet; });
