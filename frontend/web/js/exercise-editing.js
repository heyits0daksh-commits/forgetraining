'use strict';

// ============================================================
// EXERCISE EDITING (remove from session / change sequence)
// Mutates a session-shaped object in place (either the whole
// generate-workout response, or a single `day` inside a generated
// program — both carry `session_structure` + `prescribed_workout`,
// which is all these need). Re-render after calling either of these.
// ============================================================

function removeExerciseFrom(container, exId){
  (container.session_structure || []).forEach(function(phase){
    var idx = phase.exercises.indexOf(exId);
    if(idx !== -1){ phase.exercises.splice(idx, 1); }
  });
  container.prescribed_workout = (container.prescribed_workout || []).filter(function(ex){ return ex.id !== exId; });
  if(container.session_summary){ container.session_summary.total_prescribed = container.prescribed_workout.length; }
  if(typeof container.exercise_count === 'number'){ container.exercise_count = container.prescribed_workout.length; }
  if(!container._removedNames) container._removedNames = [];
}
function moveExerciseIn(container, exId, direction){
  var structure = container.session_structure;
  if(!structure || !structure.length) return false;
  var flat = [];
  structure.forEach(function(phase){ phase.exercises.forEach(function(id){ flat.push(id); }); });
  var pos = flat.indexOf(exId);
  if(pos === -1) return false;
  var newPos = pos + direction;
  if(newPos < 0 || newPos >= flat.length) return false;
  var tmp = flat[pos]; flat[pos] = flat[newPos]; flat[newPos] = tmp;
  var cursor = 0;
  structure.forEach(function(phase){
    for(var i=0; i<phase.exercises.length; i++){ phase.exercises[i] = flat[cursor]; cursor++; }
  });
  return true;
}
function exEditButtons(exId, flatPos, flatLen, weekNum, dayIndex){
  // weekNum/dayIndex are only passed from the program view, so the click
  // handler knows which day inside S.lastProgram to mutate; omitted (single
  // generated session) means "act on S.lastResult" instead.
  var scope = (weekNum != null && dayIndex != null)
    ? ' data-ex-week="'+weekNum+'" data-ex-dayindex="'+dayIndex+'"' : '';
  return '<div class="ex-editbar">'+
    '<button type="button" class="ex-editbtn" data-ex-move="up" data-ex-id="'+esc(exId)+'"'+scope+' title="Move earlier in the session"'+(flatPos<=0?' disabled':'')+'>↑</button>'+
    '<button type="button" class="ex-editbtn" data-ex-move="down" data-ex-id="'+esc(exId)+'"'+scope+' title="Move later in the session"'+(flatPos>=flatLen-1?' disabled':'')+'>↓</button>'+
    '<button type="button" class="ex-editbtn remove" data-ex-remove="'+esc(exId)+'"'+scope+' title="Remove from session">✕</button>'+
  '</div>';
}
function flatExIds(container){
  var flat = [];
  (container.session_structure || []).forEach(function(phase){ phase.exercises.forEach(function(id){ flat.push(id); }); });
  return flat;
}

// ============================================================
// ADD-YOUR-OWN-EXERCISE (post-generation) + editable sets/reps
// Works on the same session-shaped container as remove/move above -
// either S.lastResult (single session) or one `day` inside S.lastProgram.
// ============================================================

// A person adding an exercise themselves has no engine-computed
// prescription to fall back on, so this is a plain, always-editable
// sets × reps shape (renderPrescription/renderPrescriptionEditable both
// know how to read and write it) rather than trying to guess which of the
// engine's strength/conditioning/carry/isometric shapes would apply.
function defaultCustomPrescription(){
  return {type:'custom', sets:3, reps:10, rest_seconds:60, working_weight_kg:0, notes:''};
}
function addExerciseTo(container, ex){
  if(!container || !ex || !ex.id) return;
  container.prescribed_workout = container.prescribed_workout || [];
  if(container.prescribed_workout.some(function(e){ return e.id === ex.id; })) return; // already in the session
  var entry = {
    id: ex.id, name: ex.name, category: ex.category, equipment: ex.equipment,
    experience_level: ex.experience_level, difficulty: ex.difficulty,
    prescription: defaultCustomPrescription(),
    _addedByUser: true,
  };
  container.prescribed_workout.push(entry);
  container.session_structure = container.session_structure || [];
  var ownPhase = container.session_structure.filter(function(p){ return p.phase === 'Added by You'; })[0];
  if(!ownPhase){
    ownPhase = {phase:'Added by You', exercises:[]};
    container.session_structure.push(ownPhase);
  }
  ownPhase.exercises.push(ex.id);
  if(container.session_summary){ container.session_summary.total_prescribed = container.prescribed_workout.length; }
  if(typeof container.exercise_count === 'number'){ container.exercise_count = container.prescribed_workout.length; }
}
// Mutates one prescription field on one exercise in-place (sets, the
// type-appropriate rep/duration field, rest_seconds, or the working weight)
// from an inline input. Weight is float, shown/typed in whichever unit is
// currently active (see weight-unit.js) and converted to kg for storage;
// every other field is a plain integer, clamped to >=1 so a cleared/
// invalid field can't zero out or negative-out a prescription.
function setPrescriptionField(container, exId, field, rawValue){
  var ex = (container.prescribed_workout || []).filter(function(e){ return e.id === exId; })[0];
  if(!ex || !ex.prescription) return;
  if(field === 'working_weight_kg'){
    var w = parseFloat(rawValue);
    if(isNaN(w) || w < 0) w = 0;
    ex.prescription.working_weight_kg = inputToKg(w);
    ex.prescription.weight_confidence = 'user_entered';
    return;
  }
  // Free-text coaching note the person writes for themselves (form cues, a
  // reminder about tempo, why they swapped a grip, etc.) - a plain string,
  // not a number, so it skips the parseInt path below entirely. Capped the
  // same way ProgressionOverride.custom_name is server-side, so a very long
  // paste can't bloat the saved session log.
  if(field === 'notes'){
    ex.prescription.notes = String(rawValue == null ? '' : rawValue).slice(0, 500);
    return;
  }
  // rest_seconds is allowed to be 0 (no rest / straight into the next set) -
  // every other numeric field (sets/reps/etc.) still floors at 1.
  var n = parseInt(rawValue, 10);
  var floor = field === 'rest_seconds' ? 0 : 1;
  if(isNaN(n) || n < floor) n = floor;
  ex.prescription[field] = n;
}
// Which prescription field holds the "reps"-equivalent count, per type -
// same type switch renderPrescription uses to decide what to print.
function primaryFieldFor(p){
  if(p.type === 'conditioning') return {key:'work_seconds', label:'sec work'};
  if(p.type === 'carry') return {key:'distance_meters', label:'m'};
  if(p.type === 'isometric') return {key:'hold_seconds', label:'sec hold'};
  return {key:'reps', label:'reps'}; // strength, strength_bodyweight, technical, custom
}
// conditioning_engine.py's prescribe_conditioning() (Category A protocols -
// ruck/race-load carries, sled/sprint work, wall-ball/erg intervals,
// running zones, swim, hangboard/climbing, combat rounds, complexes - see
// forge_category_audit.md) returns a DIFFERENT prescription shape than a
// real exercises.json lift: no `type` field (has `load_type` instead), and
// its own field names (rest_s not rest_seconds, distance_m not
// distance_meters, plus load_type-specific fields like load_pct_race,
// hang_duration_s, round_count that primaryFieldFor/renderPrescriptionEditable
// don't know about at all). Feeding one through the generic editor renders
// nonsense - primaryFieldFor falls through to its {key:'reps'} default,
// none of the fields it reads (p.sets, p.rest_seconds, p[field.key]) exist
// on this shape, so every input silently shows a wrong floor value (1 × 1
// reps · rest 0s) instead of the actual distance/duration/load prescribed.
// A conditioning protocol's numeric fields also don't share a lift's
// editable-set semantics (you don't free-edit a ruck march's load % the
// way you'd bump a working weight), so this renders read-only text built
// from prescribe_conditioning's own field names instead of routing through
// the sets/reps/rest inputs at all.
var _CONDITIONING_LOAD_TYPE_LABEL = {
  race_load_carry: 'Race-load carry', sled_sprint: 'Sled / sprint', shuttle_ladder: 'Shuttle / ladder',
  erg_interval: 'Erg / interval', zone_run: 'Zone run', swim: 'Swim', hang_climb: 'Hang / climb',
  rounds: 'Rounds', complex: 'Complex'
};
function renderConditioningPrescription(ex){
  var p = ex.prescription;
  if(!p) return '';
  var parts = [];
  if(p.distance_m != null) parts.push(p.distance_m + 'm');
  if(p.steps_m && p.steps_m.length) parts.push(p.steps_m.join('-') + 'm');
  if(p.duration_s != null) parts.push(p.duration_s + 's');
  if(p.duration_min != null) parts.push(p.duration_min + ' min');
  if(p.hang_duration_s != null) parts.push(p.hang_duration_s + 's hang' + (p.edge_mm != null ? ' (' + p.edge_mm + 'mm edge)' : ''));
  if(p.load_pct_race != null) parts.push(p.load_pct_race + '% race load');
  if(p.load_pct_bw != null) parts.push(p.load_pct_bw + '% BW');
  if(p.target_pct_race_pace != null) parts.push(p.target_pct_race_pace + '% race pace');
  if(p.hr_zone != null) parts.push('Zone ' + p.hr_zone);
  if(p.reps != null) parts.push(p.reps + ' reps');
  if(p.round_count != null) parts.push(p.round_count + ' rounds × ' + (p.round_length_s || 0) + 's');
  if(p.work_s != null) parts.push(p.work_s + 's work');
  var setsOrRounds = p.sets != null ? p.sets + ' sets' : (p.rounds != null ? p.rounds + ' rounds' : '');
  if(setsOrRounds) parts.push(setsOrRounds);
  if(p.rest_s != null) parts.push('rest ' + p.rest_s + 's');
  var label = _CONDITIONING_LOAD_TYPE_LABEL[p.load_type] || '';
  var supervision = '';
  if(ex.requires_supervision){
    supervision = '<div class="caution"><b>Supervision required —</b> ' + esc(ex.safety_note || '') + '</div>';
  }
  return '<div class="load">' + (label ? '<span class="pill">' + esc(label) + '</span> ' : '') + esc(parts.join(' · ')) + '</div>' + supervision;
}
function renderPrescriptionEditable(ex, scope){
  var p = ex.prescription;
  if(!p) return '';
  if(ex.conditioning_protocol) return renderConditioningPrescription(ex);
  var field = primaryFieldFor(p);
  var weightNote = '';
  // A working weight only makes sense for loaded/free-choice work (strength
  // or a fully custom pick) - conditioning/carry/isometric/bodyweight
  // prescriptions don't carry a working_weight_kg field at all, so leave
  // those as-is instead of inventing a weight box for them.
  var showWeight = p.type === 'strength' || p.type === 'custom';
  if(showWeight){
    var wDisplay = S.unit === 'lb' ? Math.round(kgToLb(p.working_weight_kg||0)) : (p.working_weight_kg||0);
    weightNote = ' @ <input type="number" class="presc-input" min="0" step="'+(S.unit==='lb'?'5':'2.5')+'" value="'+wDisplay+'" '+
      'data-presc-field="working_weight_kg" data-presc-exid="'+esc(ex.id)+'"'+scope+'> '+(S.unit==='lb'?'lb':'kg')+
      (p.type === 'strength' ? ' <span class="pill" title="'+esc('Engine suggested '+p.load_pct_1rm+'% 1RM')+'">'+p.load_pct_1rm+'% 1RM ref</span>' : ' <span class="pill">your own pick</span>');
  }
  var advNote = '';
  if(p.type === 'custom'){
    var bits = [];
    if(p.set_type && p.set_type !== 'working' && typeof setTypeLabel === 'function') bits.push(setTypeLabel(p.set_type));
    if(p.rpe != null) bits.push('RPE '+p.rpe);
    if(p.rir != null) bits.push('RIR '+p.rir);
    if(p.tempo) bits.push('Tempo '+esc(p.tempo));
    if(p.warmup_sets) bits.push(p.warmup_sets+' warm-up sets');
    if(bits.length) advNote = '<div class="exmeta" style="margin-top:6px;">'+bits.join(' · ')+'</div>';
  }
  return '<div class="load editable">'+
    '<input type="number" class="presc-input" min="1" value="'+(p.sets||1)+'" '+
      'data-presc-field="sets" data-presc-exid="'+esc(ex.id)+'"'+scope+'> ×'+
    '<input type="number" class="presc-input" min="1" value="'+(p[field.key]||1)+'" '+
      'data-presc-field="'+field.key+'" data-presc-exid="'+esc(ex.id)+'"'+scope+'> '+esc(field.label)+
    weightNote+' &nbsp;·&nbsp; rest '+
    '<input type="number" class="presc-input" min="0" step="5" value="'+(p.rest_seconds||0)+'" '+
      'data-presc-field="rest_seconds" data-presc-exid="'+esc(ex.id)+'"'+scope+'>s'+
  '</div>'+advNote+
  '<textarea class="presc-notes" rows="1" placeholder="Your own notes for this exercise (cues, tempo, why you swapped it in)…" '+
    'data-presc-field="notes" data-presc-exid="'+esc(ex.id)+'"'+scope+'>'+esc(p.notes||'')+'</textarea>';
}
// Search box + results + "Add" buttons for picking an extra exercise into
// an already-generated session/day. idPrefix keeps element ids unique when
// both the session view and a program day could theoretically render one
// (only one is ever on-screen at a time in practice, but this keeps it
// future-safe rather than relying on that).
function addExercisePanelHtml(idPrefix){
  return '<div class="add-ex-panel" id="'+idPrefix+'AddExPanel" style="display:'+(S.addExPanelOpen?'block':'none')+';">'+
    '<input type="text" class="add-ex-search" id="'+idPrefix+'AddExSearch" value="'+esc(S.addExQuery)+'" placeholder="Search exercises to add — e.g. &quot;row&quot;, &quot;lunge&quot;" autocomplete="off">'+
    '<div class="ex-picker-results" id="'+idPrefix+'AddExResults"></div>'+
  '</div>';
}
function renderAddExResults(idPrefix, query, scope){
  var results = document.getElementById(idPrefix+'AddExResults');
  if(!results) return;
  results.innerHTML = '<div class="empty">Searching…</div>';
  var url = API_BASE + '/api/v1/exercises?limit=40' + (query ? '&search=' + encodeURIComponent(query) : '');
  fetch(url).then(function(r){ return r.json(); }).then(function(body){
    var list = body.exercises || [];
    if(!list.length){ results.innerHTML = '<div class="empty">No exercises match that search.</div>'; return; }
    results.innerHTML = list.map(function(ex){
      return '<div class="ex-pick-item" data-add-ex-id="'+esc(ex.id)+'">'+
        '<span>'+esc(ex.name)+'<span class="exmeta">'+esc(ex.equipment||'')+' · '+esc(ex.category||'')+'</span></span>'+
        '<button type="button" class="btn secondary small" data-add-ex-pick="'+esc(ex.id)+'" data-add-ex-name="'+esc(ex.name)+'" data-add-ex-cat="'+esc(ex.category||'')+'" data-add-ex-equip="'+esc(ex.equipment||'')+'" data-add-ex-lvl="'+esc(ex.experience_level||'')+'" data-add-ex-diff="'+(ex.difficulty||1)+'"'+scope+'>+ Add</button>'+
      '</div>';
    }).join('');
  }).catch(function(){
    results.innerHTML = '<div class="empty">Couldn\'t reach the engine to search exercises.</div>';
  });
}

// Surfaces recommendation_engine.compute_adaptive_load_adjustment's own
// transparency contract (docs/ROADMAP.md Phase 19) - until now
// `adaptive_training_load` rode along in every generate-workout/
// generate-program response completely unused by the frontend: the
// displayed readiness %/deload flag could already be silently nudged by
// RPE trend, a weekly volume spike, a missed-session gap, or a
// plateau read, with zero indication of why. `load.reasons` is exactly
// the plain-English explanation built for this. A no-op response
// (`active: false`, e.g. anonymous caller or too little logged history)
// renders nothing, same as before this existed.
function renderAdaptiveLoadNote(load){
  if(!load || !load.active || !load.reasons || !load.reasons.length) return '';
  var intensityPct = Math.round((load.intensity_multiplier - 1) * 100);
  var volumePct = Math.round((load.volume_multiplier - 1) * 100);
  var deltaParts = [];
  if(intensityPct) deltaParts.push((intensityPct > 0 ? '+' : '') + intensityPct + '% intensity');
  if(volumePct) deltaParts.push((volumePct > 0 ? '+' : '') + volumePct + '% volume');
  var headline = deltaParts.length
    ? 'Adjusted ' + deltaParts.join(', ') + ' from your readiness input, based on recent training history'
    : 'Recent training history reviewed - no net adjustment this time';
  return '<div class="callout'+(load.auto_deload_recommended ? ' danger' : ' blue')+'">'+
    '<b>Adaptive load'+(load.auto_deload_recommended ? ' — deload recommended' : '')+'.</b> '+esc(headline)+
    ' (last '+load.sessions_considered+' logged session(s)):'+
    '<div class="reason">'+load.reasons.map(esc).join(' · ')+'</div>'+
    '</div>';
}

function renderResults(data){
  document.getElementById('resultTitle').innerHTML = sportBadge(data.sport) + esc(data.sport) +
    (data.mode === 'custom' ? ' <span class="pill">Custom Session</span>' : '') + ' Session';
  document.getElementById('resultSubtitle').textContent =
    data.experience_level + ' · Readiness ' + Math.round(data.readiness_factor*100) + '%';

  var byId = {};
  data.prescribed_workout.forEach(function(ex){ byId[ex.id] = ex; });
  var bio = data.biometric_analysis;
  var summary = data.session_summary;
  var recovery = data.recovery;

  var html = '';

  if(data.deload_mode){
    html += '<div class="deload-banner"><span class="tag">Deload</span>'+
      'Readiness below 40% — volume cut and high-difficulty work locked out until you recover.</div>';
  }

  html += renderAdaptiveLoadNote(data.adaptive_training_load);

  if(recovery && recovery.components){
    html += '<div class="callout'+(recovery.score<40?' danger':(recovery.score<60?' ':' blue'))+'">'+
      '<b>Recovery '+recovery.score+'% — '+esc(recovery.label)+'.</b>'+
      (recovery.poor_sleep ? ' Poor sleep flagged — heavy compound lifts below are trimmed for it.' : '')+
      (recovery.high_soreness ? ' High soreness flagged.' : '')+
      '</div>';
  }

  html += renderCoachNotes(data.coach_notes);

  html += '<div class="section-title">Biometric Analysis</div>';
  html += '<div class="stats">'+
    stat(bio.bmi != null ? bio.bmi : '—','BMI')+
    stat(bio.relative_bench_ratio+'×','Bench / BW')+
    stat(bio.relative_squat_ratio+'×','Squat / BW')+
    stat(bio.relative_deadlift_ratio+'×','Deadlift / BW')+
    stat(Math.round(data.readiness_factor*100)+'%','Readiness')+
    '</div>';
  if(bio.status){ html += '<p class="bio-status">'+esc(bio.status)+'</p>'; }

  if(data.level_check && data.level_check.estimated_level && data.level_check.agrees === false){
    html += '<div class="callout blue"><b>Level check.</b> '+esc(data.level_check.note)+
      ' <span class="pill">'+esc(data.level_check.confidence)+' confidence</span></div>';
  }

  html += '<div class="hud-banner">'+
    '<b>'+summary.total_prescribed+'</b> exercises unlocked &nbsp;·&nbsp; '+
    '<b>'+summary.total_excluded+'</b> locked &nbsp;·&nbsp; target intensity '+
    '<b>'+Math.round(data.readiness_factor*100)+'%</b></div>';
  html += data.personalization_applied ?
    '<div class="callout blue" style="margin-top:0;">Ranked using your logged training history — see "Why this exercise?" on each pick.</div>' :
    '<div class="progression-note" style="margin:-8px 0 18px;">Not personalized yet — log a few sessions and this ranking will start using your own history.</div>';

  if(!data.prescribed_workout.length){
    html += '<div class="callout danger">Nothing qualifies yet — loosen an equipment/injury filter or check your biometrics.</div>';
  }

  html += '<div class="session-editbar">'+
    (data.prescribed_workout.length ? '<button type="button" id="btnResetOrder">↺ Reset removals &amp; order</button>' : '')+
    '<button type="button" id="btnToggleAddEx" data-toggle-add-ex="res">+ Add Exercise</button>'+
  '</div>';
  html += addExercisePanelHtml('res');

  if(data.mode === 'custom' && data._customWarmup && data._customWarmup.length){
    html += '<div class="phase-label"><span class="n">W</span><h3>Warm-Up</h3></div>';
    html += '<div class="warmup-list" style="margin-bottom:22px;">'+
      data._customWarmup.map(function(w){
        return '<div class="warmup-item"><span>'+esc(w.name)+(w.detail ? ' <span class="exmeta">— '+esc(w.detail)+'</span>' : '')+'</span></div>';
      }).join('')+
    '</div>';
  }

  var groupOccurrence = {};

  // PHASE TABS (same visual/behavior pattern as the program view's
  // week-tabs/day-tabs - see program-wizard-steps.js renderProgramWeek).
  // Before this, a single session's Warm-Up/Main/Conditioning phases were
  // just stacked one after another with a plain header - fine for a short
  // session, but there was no quick way to jump straight to e.g. the
  // Conditioning block the way the program view lets you jump straight to
  // a specific day. "All" (default, active) reproduces the exact old
  // behavior - every phase stacked and visible - so nothing changes for
  // someone who never touches the tabs; picking a specific phase tab just
  // hides the others so that section is front and center on a small
  // screen.
  var phases = data.session_structure || [];
  if(phases.length > 1){
    html += '<div class="day-tabs" id="resultPhaseTabs">'+
      '<button type="button" class="day-tab active" data-result-phase="all">All</button>'+
      phases.map(function(phase, pIdx){
        return '<button type="button" class="day-tab" data-result-phase="'+pIdx+'">'+esc(phase.phase)+
          ' <span class="dtcount">'+phase.exercises.length+'</span></button>';
      }).join('')+
    '</div>';
  }

  var flatIds = flatExIds(data);
  var idx = 0;
  phases.forEach(function(phase, pIdx){
    html += '<div class="phase-label" data-result-phase-section="'+pIdx+'"><span class="n">'+(pIdx+1)+'</span><h3>'+esc(phase.phase)+'</h3></div>';
    phase.exercises.forEach(function(exId){
      var ex = byId[exId];
      if(!ex) return;
      idx++;
      var flatPos = flatIds.indexOf(exId);
      var stars = DIFFICULTY_STARS[ex.difficulty] || '★'.repeat(ex.difficulty || 1);
      var groupPill = '';
      if(data.mode === 'custom' && ex.prescription && ex.prescription.group && data._customGroups && data._customGroups[ex.prescription.group]){
        groupOccurrence[ex.prescription.group] = (groupOccurrence[ex.prescription.group]||0) + 1;
        groupPill = '<span class="pill group-pill" title="'+esc(data._customGroups[ex.prescription.group].name)+'">'+
          esc(ex.prescription.group)+groupOccurrence[ex.prescription.group]+'</span> ';
      }
      html += '<div class="exercise" data-exid="'+esc(ex.id)+'" data-result-phase="'+pIdx+'" style="animation-delay:'+(idx*0.04)+'s;">'+
        '<div class="exerciseTop">'+
          '<h4><span class="rank">'+idx+'</span>'+groupPill+'<span class="exname" data-open-modal="'+esc(ex.id)+'">'+esc(ex.name)+'</span></h4>'+
          (!isStrengthMode() ? '<div class="transfer">Transfer <b>'+ex.sport_priority_score+'</b></div>' : '')+
          exEditButtons(ex.id, flatPos, flatIds.length)+
        '</div>'+
        '<div class="pillrow">'+pill(ex.category)+pill(ex.equipment)+pill(ex.experience_level)+pill(stars)+(ex._addedByUser?pill('added by you'):'')+'</div>'+
        renderPrescriptionEditable(ex, '');
      if(ex.prescription && ex.prescription.sleep_adjusted){
        html += '<div class="caution"><b>Sleep-adjusted —</b> '+esc(ex.prescription.note||'Load trimmed for poor sleep.')+'</div>';
      }
      if(ex.injury_caution){
        html += '<div class="caution"><b>Caution —</b> '+esc(ex.injury_caution)+'</div>';
      }
      if(ex.safety_warning){
        html += '<div class="caution"><b>Safety warning —</b> '+esc(ex.safety_warning.note||'')+
          (ex.safety_warning.reasons && ex.safety_warning.reasons.length ? '<div class="reason">'+esc(ex.safety_warning.reasons.join(' · '))+'</div>' : '')+
          '<div class="precheck-actions">'+
            '<button type="button" class="btn secondary small" data-warn-keep="'+esc(ex.id)+'">Keep Exercise</button>'+
            '<button type="button" class="btn secondary small danger" data-ex-remove="'+esc(ex.id)+'" title="Remove from session">Remove Exercise</button>'+
          '</div>'+
        '</div>';
      }
      var resWhyOpen = !!S.resultWhyOpen[ex.id];
      html += '<button type="button" class="why-toggle" data-why-toggle-result="'+esc(ex.id)+'">'+(resWhyOpen ? 'Hide why this exercise ▲' : 'Why this exercise? ▾')+'</button>';
      html += '<div class="why'+(resWhyOpen ? ' open' : '')+'">'+
        (ex.personalization_note ? '<div><b>Your history.</b> '+esc(ex.personalization_note)+'</div>' : '')+
        (!isStrengthMode() ? '<div><b>Sport transfer.</b> '+esc(ex.sport_transfer_rationale||'')+'</div>' : '')+
        '<div><b>Programming role.</b> '+esc(ex.programming_role_rationale||'')+'</div>'+
        (ex.experience_level_fit ? '<div><b>Experience level.</b> '+esc(ex.experience_level_fit)+'</div>' : '')+
        '</div>';
      html += '<button type="button" class="why-toggle" data-swap-open="'+esc(ex.id)+'">'+(ex.injury_caution ? '🔄 Find a safer swap ▾' : '🔄 Swap this exercise ▾')+'</button>';
      html += '<div class="swap-panel" data-swap-panel="'+esc(ex.id)+'"></div>';
      html += '<div class="logged-sets" data-logged-for="'+esc(ex.id)+'"></div>';
      // Dumbbell exercises are always logged per hand, not a combined
      // total (that's how the exercise is actually loaded) - the input
      // placeholder says so up front instead of leaving it ambiguous.
      var isDb = ex.equipment === 'Dumbbell';
      html += '<div class="logrow">'+
        '<input type="number" placeholder="'+(isDb ? 'Weight per hand (' : 'Weight (')+(S.unit==="lb"?"lb":"kg")+')" class="logw" min="0">'+
        '<input type="number" placeholder="Reps" class="logr" min="0">'+
        '<button class="btn small" data-log-set="'+esc(ex.id)+'" data-log-name="'+esc(ex.name)+'">Log Set</button>'+
        '<span></span>'+
      '</div>';
      html += '</div>';
    });
  });

  if(data.progression_roadmap && data.progression_roadmap.length){
    html += '<div class="section-title" style="margin-top:34px;">Progression Roadmap — Closest Unlocks</div>';
    data.progression_roadmap.forEach(function(r){
      var gaps = Object.values(r.progress_needed || {}).map(function(g){
        return '<div>'+esc(g.label)+': have '+esc(String(g.have))+', need '+esc(String(g.need))+'</div>';
      }).join('');
      html += '<div class="roadmap-card"><b>'+esc(r.name)+'</b>'+
        '<div class="gaps">'+gaps+'</div>'+
        (r.next_step ? '<div class="next">Next: '+esc(r.next_step)+'</div>' : '')+
        '</div>';
    });
  }

  if(data.excluded_exercises && data.excluded_exercises.length){
    html += '<details class="locked" style="margin-top:26px;"><summary>All Locked Protocols ('+data.excluded_exercises.length+')</summary>';
    data.excluded_exercises.forEach(function(ex){
      html += renderLockedExercise(ex);
    });
    html += '</details>';
  }

  document.getElementById('resultBody').innerHTML = html;
  if(S.addExPanelOpen) renderAddExResults('res', S.addExQuery, '');

  var phaseTabs = document.getElementById('resultPhaseTabs');
  if(phaseTabs){
    phaseTabs.addEventListener('click', function(e){
      var btn = e.target.closest('[data-result-phase]');
      if(!btn) return;
      var picked = btn.getAttribute('data-result-phase');
      phaseTabs.querySelectorAll('.day-tab').forEach(function(b){
        b.classList.toggle('active', b === btn);
      });
      document.querySelectorAll('#resultBody [data-result-phase-section], #resultBody [data-result-phase]').forEach(function(el){
        var elPhase = el.getAttribute('data-result-phase-section') != null
          ? el.getAttribute('data-result-phase-section') : el.getAttribute('data-result-phase');
        el.style.display = (picked === 'all' || elPhase === picked) ? '' : 'none';
      });
    });
  }
}
function stat(value,label){ return '<div class="stat"><strong>'+esc(String(value))+'</strong><small>'+esc(label)+'</small></div>'; }
function pill(text){ return '<span class="pill">'+esc(text||'')+'</span>'; }

// Renders the deterministic "pro coach" summary (backend/services/coach_notes.py).
// Present on every generate-workout / generate-program response - no API
// key or feature flag required (unlike ai_insight, which is optional and
// LLM-backed) - so this always has something to show when coach_notes is
// on the payload at all.
function renderCoachNotes(coachNotes){
  if(!coachNotes) return '';
  var html = '<div class="coach-notes">';
  html += '<div class="coach-notes-head"><span class="coach-notes-badge">Coach\u2019s Take</span>'+
    '<h3>'+esc(coachNotes.headline||'')+'</h3></div>';
  if(coachNotes.key_lifts && coachNotes.key_lifts.length){
    html += '<div class="coach-notes-lifts">'+
      coachNotes.key_lifts.map(function(l){
        return '<div class="coach-notes-lift"><b>'+esc(l.name||'')+'</b>'+
          (l.role ? ' <span class="pill">'+esc(l.role)+'</span>' : '')+
          (l.why ? '<div class="coach-notes-why">'+esc(l.why)+'</div>' : '')+
        '</div>';
      }).join('')+
    '</div>';
  }
  if(coachNotes.watch_for && coachNotes.watch_for.length){
    html += '<ul class="coach-notes-watch">'+
      coachNotes.watch_for.map(function(w){ return '<li>'+esc(w)+'</li>'; }).join('')+
    '</ul>';
  }
  if(coachNotes.coach_tip){
    html += '<div class="coach-notes-tip">'+esc(coachNotes.coach_tip)+'</div>';
  }
  html += '</div>';
  return html;
}

// Shared by exercise-editing.js's single-session "Locked Protocols" list and
// program-wizard-steps.js's per-day equivalent (both render the same
// excluded_exercises[] shape off the same backend response fields:
// alternatives, manual_guidance, alternatives_note - see
// progression_engine.py's excluded{} assembly). Kept here since this file
// already owns the single-session locked-list rendering it was written for.
function renderLockedExercise(ex){
  var html = '<div class="locked-item"><b>'+esc(ex.name)+'</b>'+
    '<div class="reason">'+esc((ex.reasons||[]).join(' · '))+'</div>';

  if(ex.alternatives && ex.alternatives.length){
    html += '<div class="alt-list">';
    ex.alternatives.forEach(function(a){
      html += '<div class="alt-swap"><span class="alt-name">🔁 '+esc(a.name)+'</span>'+
        (a.rehab_pick ? '<span class="alt-pill rehab">Rehab pick</span>' : '')+
        (a.equipment_available ? '<span class="alt-pill have-eq">You have this equipment</span>' : '')+
        (a.safety_classification && a.safety_classification.color ? '<span class="alt-pill">'+esc(a.safety_classification.color)+'</span>' : '')+
        '</div>';
    });
    html += '</div>';
  } else if(ex.alternatives_note){
    html += '<div class="alt-note">⚠️ '+esc(ex.alternatives_note)+'</div>';
  }

  if(ex.manual_guidance && ex.manual_guidance.length){
    ex.manual_guidance.forEach(function(m){
      html += '<div class="manual-swap"><b>Coach\'s note ('+esc(m.issue)+'):</b> '+
        esc((m.substitutes||[]).map(function(s){ return s.name || s; }).join(', '))+
        (m.note ? ' — '+esc(m.note) : '')+
        '</div>';
    });
  }

  html += '</div>';
  return html;
}

