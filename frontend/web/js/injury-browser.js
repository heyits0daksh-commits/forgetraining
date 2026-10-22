'use strict';

// ============================================================
// INJURY BROWSER — sections (joint) > subsections (condition) > grade chips
// ============================================================

// S.injOpenSections / S.injSearchQuery / S.injJointFilter (wizard instance) and
// S.pgInjOpenSections / S.pgInjSearchQuery / S.pgInjJointFilter (Program
// Builder instance) are initialized alongside the rest of S above.

// ------------------------------------------------------------------
// Two independent instances of this browser exist: 'wiz' (Train wizard,
// bound to S.injuries) and 'pg' (Program Builder, bound to S.pgInjuries).
// INJ_IDS maps each instance to its DOM ids; injState() resolves an
// instance name to its live target Set + open/search/filter state so the
// render functions below never hardcode which screen they're serving.
var INJ_IDS = {
  wiz: {jointFilters:'injJointFilters', search:'injSearchInput', clear:'injClearBtn', sections:'injurySections', noResults:'injNoResults', selectedCount:'injSelectedCount'},
  pg:  {jointFilters:'pgInjJointFilters', search:'pgInjSearchInput', clear:'pgInjClearBtn', sections:'pgInjurySections', noResults:'pgInjNoResults', selectedCount:'pgInjSelectedCount'}
};
function injState(which){
  return which === 'pg'
    ? {target:S.pgInjuries, stages:S.pgInjuryStages, sides:S.pgInjurySides, get open(){return S.pgInjOpenSections;}, get query(){return S.pgInjSearchQuery;}, set query(v){S.pgInjSearchQuery = v;}, get jointFilter(){return S.pgInjJointFilter;}, set jointFilter(v){S.pgInjJointFilter = v;}, get groupMode(){return S.pgInjGroupMode;}, set groupMode(v){S.pgInjGroupMode = v;}}
    : {target:S.injuries, stages:S.injuryStages, sides:S.injurySides, get open(){return S.injOpenSections;}, get query(){return S.injSearchQuery;}, set query(v){S.injSearchQuery = v;}, get jointFilter(){return S.injJointFilter;}, set jointFilter(v){S.injJointFilter = v;}, get groupMode(){return S.injGroupMode;}, set groupMode(v){S.injGroupMode = v;}};
}

// Resolves which of the two server-provided groupings (see backend's
// grouped_injury_taxonomy vs. grouped_injury_taxonomy_by_muscle_group) to
// browse right now. 'joint' is the engine's own 8-tag vocabulary (Shoulder,
// Knee, ...); 'muscle' regroups muscle-strain entries into anatomical
// categories (Chest, Back, Legs, ...) and labels ligament/tendon/joint-
// disorder entries as their own "<Joint> (Joints, Ligaments & Tendons)"
// categories instead. Same underlying injuries either way - this only
// changes how they're organized for browsing.
function injGroupedData(which){
  var meta = S.metadata || {};
  var st = injState(which);
  return (st.groupMode === 'muscle' ? meta.injuries_by_muscle_group : meta.injuries_grouped) || {};
}

// Builds the {injury_name: rehab_stage} map to actually send on the wire -
// only entries whose injury is still checked in `target` (an unchecked chip
// leaves a stale entry sitting in st.stages until the person re-checks it,
// same "don't rewrite what they haven't touched" reasoning as the rest of
// this file, but a stale entry must never reach the request payload).
// Returns null (not {}) when there's nothing to send, matching
// WorkoutRequest/ProgramRequest.injury_stages' Optional[...] = None default -
// an empty object and "field omitted" are the same thing to the backend,
// but null keeps the request body honest about that instead of always
// sending a key.
function buildInjuryStagesPayload(which){
  var st = injState(which);
  var out = {};
  var any = false;
  st.target.forEach(function(name){
    if(st.stages[name]){ out[name] = st.stages[name]; any = true; }
  });
  return any ? out : null;
}

// Same shape/purpose as buildInjuryStagesPayload above, for the
// {injury_name: side} map (WorkoutRequest/ProgramRequest.injury_sides).
// Only entries whose injury is still checked in `target` are sent, and
// only when a side was actually picked - an injury left at "no side set"
// is simply omitted, which the engine treats as bilateral (unchanged
// behavior). Returns null (not {}) when there's nothing to send.
function buildInjurySidesPayload(which){
  var st = injState(which);
  var out = {};
  var any = false;
  st.target.forEach(function(name){
    if(st.sides[name]){ out[name] = st.sides[name]; any = true; }
  });
  return any ? out : null;
}

// "ACL Tear - Grade 2 (name, Controlled Loading)" for the review screens -
// looks up the human label for a stored stage id via S.metadata.rehab_stages
// rather than title-casing the raw id, so it matches whatever wording the
// backend actually uses. `sidesMap` is optional (v5.15) - when given and the
// injury has a side set, it's appended alongside the stage, e.g.
// "ACL Tear - Grade 2 (Controlled Loading, Left side)".
function formatInjuryWithStage(name, stagesMap, sidesMap){
  var stageId = stagesMap[name];
  var sideId = sidesMap ? sidesMap[name] : null;
  var parts = [];
  if(stageId){
    var stages = (S.metadata && S.metadata.rehab_stages) || [];
    var match = stages.filter(function(s){ return s.stage === stageId; })[0];
    parts.push(match ? match.label : stageId);
  }
  if(sideId){
    parts.push(INJ_SIDE_LABEL[sideId] || sideId);
  }
  return parts.length ? esc(name) + ' (' + esc(parts.join(', ')) + ')' : esc(name);
}

function escRe(s){ return String(s).replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); }

// Wraps matches of `query` in the (already-escaped) text with <mark>, for
// the search box. Operates on the escaped string so it can't reopen a tag.
function highlight(escapedText, query){
  if(!query) return escapedText;
  var re = new RegExp('(' + escRe(esc(query)) + ')', 'ig');
  return escapedText.replace(re, '<mark class="inj-hl">$1</mark>');
}

function renderInjStageSelect(injuryName, checked, currentStage){
  var stages = (S.metadata && S.metadata.rehab_stages) || [];
  if(!stages.length) return ''; // older backend without rehab_stages - degrade to severity-only, same as before this existed
  var options = '<option value="">Stage: severity only</option>' + stages.map(function(s){
    return '<option value="'+esc(s.stage)+'"'+(currentStage===s.stage?' selected':'')+'>'+esc(s.label)+'</option>';
  }).join('');
  return '<select class="inj-stage-select" data-inj-stage-for="'+esc(injuryName)+'" '+
    'style="display:'+(checked?'inline-block':'none')+'" ' +
    'title="Optional rehab stage — narrows what this injury still allows as recovery progresses">' +
    options + '</select>';
}

var INJ_SIDE_LABEL = {left:'Left side', right:'Right side', bilateral:'Both sides'};

// (v5.17) Only shown once the injury itself is checked, same gating
// renderInjStageSelect/renderInjSideSelect already use - this data exists
// on every taxonomy entry (injury_taxonomy.py's clinical_red_flags field)
// but wasn't reaching the person selecting the injury at all before this.
// Not a diagnosis or a gate on anything the engine does - purely "here's
// when this specific condition needs a clinician's eyes before you train
// through it", same disclaimer injury_taxonomy.py's module docstring makes.
function renderInjRedFlags(checked, redFlags){
  if(!checked || !redFlags || !redFlags.length) return '';
  return '<div class="inj-red-flags"><span class="icon">⚠</span><div>' +
    '<div><b>Seek medical evaluation if:</b></div>' +
    '<ul>' + redFlags.map(function(f){ return '<li>'+esc(f)+'</li>'; }).join('') + '</ul>' +
    '</div></div>';
}

function renderInjSideSelect(injuryName, checked, currentSide, lateralityApplicable){
  var sides = (S.metadata && S.metadata.injury_sides) || [];
  if(!sides.length) return ''; // older backend without injury_sides - degrade to today's always-bilateral behavior
  // v5.19 - only paired limb structures (muscle group/ligament/tendon) can
  // be "left" or "right" in the first place; the spine is a single midline
  // column, so an injury whose taxonomy entry doesn't qualify (see backend
  // injury_taxonomy.laterality_applicable, carried here as this grade's
  // laterality_applicable field) never gets a side picker at all - not
  // just left unset.
  if(!lateralityApplicable) return '';
  var options = '<option value="">Side: not set (both)</option>' + sides.map(function(s){
    return '<option value="'+esc(s)+'"'+(currentSide===s?' selected':'')+'>'+esc(INJ_SIDE_LABEL[s] || s)+'</option>';
  }).join('');
  return '<select class="inj-side-select" data-inj-side-for="'+esc(injuryName)+'" '+
    'style="display:'+(checked?'inline-block':'none')+'" ' +
    'title="Which side is injured — a one-sided injury still lets single-leg/single-arm exercises run on the unaffected side">' +
    options + '</select>';
}

function injuryTextMatches(joint, condition, grade, query){
  if(!query) return true;
  var q = query.toLowerCase();
  return (
    joint.toLowerCase().indexOf(q) !== -1 ||
    condition.toLowerCase().indexOf(q) !== -1 ||
    grade.name.toLowerCase().indexOf(q) !== -1 ||
    (grade.tissue || '').toLowerCase().indexOf(q) !== -1 ||
    (grade.region || '').toLowerCase().indexOf(q) !== -1 ||
    grade.severity_label.toLowerCase().indexOf(q) !== -1
  );
}

// Quick-jump chips — one per joint. Clicking a joint narrows the browser
// below to just that joint's section (and force-opens it); clicking the
// same joint again clears the filter back to the full accordion.
function renderInjJointFilters(which){
  var ids = INJ_IDS[which];
  var st = injState(which);
  var grouped = injGroupedData(which);
  var container = document.getElementById(ids.jointFilters);
  if(!container) return;
  var joints = Object.keys(grouped);
  if(!joints.length){ container.innerHTML = ''; return; }

  container.innerHTML = joints.map(function(joint){
    var conditions = grouped[joint];
    var selectedInJoint = conditions.reduce(function(n, c){
      return n + c.grades.filter(function(g){ return st.target.has(g.name); }).length;
    }, 0);
    var active = st.jointFilter === joint;
    return '<button type="button" class="inj-joint-chip'+(active?' active':'')+(selectedInJoint?' has-selected':'')+'" '+
      'data-joint-filter="'+esc(joint)+'">'+
      esc(joint)+
      (selectedInJoint ? '<span class="count-pill">'+selectedInJoint+'</span>' : '')+
      '</button>';
  }).join('');

  container.querySelectorAll('[data-joint-filter]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var joint = btn.getAttribute('data-joint-filter');
      if(st.jointFilter === joint){
        st.jointFilter = null;
        st.open.delete(joint);
      } else {
        st.jointFilter = joint;
        st.open.add(joint);
      }
      renderInjuryBrowser(which);
    });
  });
}

function renderInjuryBrowser(which){
  which = which || 'wiz';
  var ids = INJ_IDS[which];
  var st = injState(which);
  var grouped = injGroupedData(which);
  var query = st.query.trim();
  var container = document.getElementById(ids.sections);
  var noResults = document.getElementById(ids.noResults);
  var allJoints = Object.keys(grouped);
  var joints = allJoints;

  renderInjJointFilters(which);

  if(st.jointFilter) joints = joints.filter(function(j){ return j === st.jointFilter; });

  if(!allJoints.length){
    // Backward-compat fallback for an older backend without injuries_grouped:
    // fall back to the flat list the /metadata endpoint always carries.
    var flat = (S.metadata && S.metadata.injuries) || [];
    container.innerHTML = '<div class="checks dense">' + flat.map(function(inj){
      return checkboxHtml(inj, st.target.has(inj));
    }).join('') + '</div>';
    wireChecks(container, st.target);
    updateInjSelectedCount(which);
    return;
  }

  var html = '';
  var anyVisible = false;

  joints.forEach(function(joint){
    var conditions = grouped[joint];
    var visibleConditions = [];
    conditions.forEach(function(c){
      var visibleGrades = c.grades.filter(function(g){ return injuryTextMatches(joint, c.condition, g, query); });
      if(visibleGrades.length) visibleConditions.push({condition: c.condition, grades: visibleGrades});
    });
    if(query && !visibleConditions.length) return;  // hide whole section on an active, non-matching search
    anyVisible = true;

    var selectedInSection = conditions.reduce(function(n, c){
      return n + c.grades.filter(function(g){ return st.target.has(g.name); }).length;
    }, 0);
    var isOpen = st.jointFilter === joint || st.open.has(joint) || (query && visibleConditions.length > 0);
    var shownConditions = query ? visibleConditions : conditions;

    html += '<div class="inj-section'+(isOpen?' open':'')+(query&&visibleConditions.length?' has-match':'')+'" data-joint="'+esc(joint)+'">';
    html += '<div class="inj-section-head" data-toggle-section="'+esc(joint)+'">'+
      '<span class="name">'+highlight(esc(joint), query)+'</span>'+
      '<span class="counts">'+
        (selectedInSection ? '<span class="count-pill selected">'+selectedInSection+' selected</span>' : '')+
        '<span class="count-pill">'+conditions.length+' conditions</span>'+
        '<span class="chev">▶</span>'+
      '</span>'+
    '</div>';
    html += '<div class="inj-section-body">';
    shownConditions.forEach(function(c){
      html += '<div class="inj-condition">';
      html += '<div class="inj-condition-name">'+highlight(esc(c.condition), query)+'</div>';
      html += '<div class="inj-grades">';
      c.grades.forEach(function(g){
        var checked = st.target.has(g.name);
        // Single-grade conditions (most named conditions) just show the
        // severity as the chip label; multi-grade ones (most muscle/
        // ligament/tendon entries) show "Grade N" pulled from the full name.
        var gradeMatch = g.name.match(/Grade\s+[IVX0-9]+/i);
        var label = gradeMatch ? gradeMatch[0] : g.severity_label;
        html += '<span class="inj-grade-wrap">';
        html += '<button type="button" class="inj-grade-chip sev-'+g.severity+(checked?' checked':'')+'" '+
          'data-inj-name="'+esc(g.name)+'" title="'+esc(g.name)+'">'+
          esc(label)+' <span class="sev">('+esc(g.severity_label)+')</span>'+
          '</button>';
        // Optional rehab-stage picker, one per checked injury (backend:
        // WorkoutRequest/ProgramRequest.injury_stages, injury_taxonomy.
        // REHAB_STAGES) - only meaningful, so only shown, once the injury
        // itself is checked. Left unset (empty value), the engine keeps
        // its existing severity-only behavior for this joint - a stage
        // only ever narrows that further, never loosens it.
        html += renderInjStageSelect(g.name, checked, st.stages[g.name]);
        html += renderInjSideSelect(g.name, checked, st.sides[g.name], g.laterality_applicable);
        html += '</span>';
        html += renderInjRedFlags(checked, g.clinical_red_flags);
      });
      html += '</div></div>';
    });
    html += '</div></div>';
  });

  container.innerHTML = html;
  noResults.style.display = (query && !anyVisible) ? 'block' : 'none';

  container.querySelectorAll('[data-toggle-section]').forEach(function(head){
    head.addEventListener('click', function(){
      var joint = head.getAttribute('data-toggle-section');
      var section = head.closest('.inj-section');
      if(st.open.has(joint)){ st.open.delete(joint); section.classList.remove('open'); }
      else { st.open.add(joint); section.classList.add('open'); }
    });
  });
  container.querySelectorAll('[data-inj-name]').forEach(function(chip){
    chip.addEventListener('click', function(){
      var name = chip.getAttribute('data-inj-name');
      var wrap = chip.closest('.inj-grade-wrap');
      var stageSelect = wrap ? wrap.querySelector('[data-inj-stage-for]') : null;
      var sideSelect = wrap ? wrap.querySelector('[data-inj-side-for]') : null;
      if(st.target.has(name)){
        st.target.delete(name);
        chip.classList.remove('checked');
        // A stage/side with no checked injury behind it is stale - drop it
        // so it can never leak into buildInjuryStagesPayload/
        // buildInjurySidesPayload for an injury the person no longer has
        // flagged, and reset the (now-hidden) selects back to their
        // defaults for if they re-check it later.
        delete st.stages[name];
        delete st.sides[name];
        if(stageSelect){ stageSelect.style.display = 'none'; stageSelect.value = ''; }
        if(sideSelect){ sideSelect.style.display = 'none'; sideSelect.value = ''; }
      } else {
        st.target.add(name);
        chip.classList.add('checked');
        if(stageSelect){ stageSelect.style.display = 'inline-block'; }
        if(sideSelect){ sideSelect.style.display = 'inline-block'; }
      }
      updateInjSelectedCount(which);
      // Keep the per-section "N selected" pill accurate without a full re-render.
      var section = chip.closest('.inj-section');
      var pill = section.querySelector('.count-pill.selected');
      var count = section.querySelectorAll('.inj-grade-chip.checked').length;
      if(count && !pill){
        pill = document.createElement('span');
        pill.className = 'count-pill selected';
        section.querySelector('.counts').prepend(pill);
      }
      if(pill){
        if(count){ pill.textContent = count + ' selected'; }
        else { pill.remove(); }
      }
    });
  });
  container.querySelectorAll('[data-inj-stage-for]').forEach(function(select){
    select.addEventListener('click', function(e){ e.stopPropagation(); }); // don't let the click bubble into the chip's own toggle
    select.addEventListener('change', function(){
      var name = select.getAttribute('data-inj-stage-for');
      if(select.value){ st.stages[name] = select.value; }
      else { delete st.stages[name]; }
    });
  });
  container.querySelectorAll('[data-inj-side-for]').forEach(function(select){
    select.addEventListener('click', function(e){ e.stopPropagation(); }); // don't let the click bubble into the chip's own toggle
    select.addEventListener('change', function(){
      var name = select.getAttribute('data-inj-side-for');
      if(select.value){ st.sides[name] = select.value; }
      else { delete st.sides[name]; }
    });
  });

  updateInjSelectedCount(which);
}

function updateInjSelectedCount(which){
  which = which || 'wiz';
  var el = document.getElementById(INJ_IDS[which].selectedCount);
  if(el) el.textContent = injState(which).target.size + ' selected';
}

// Segmented "By Joint" / "By Muscle Group" toggle above the quick-jump
// chips. Switching clears the active section filter (the two groupings use
// different category names, so a joint-mode filter like "Knee" wouldn't
// mean anything once switched to muscle-group categories) but never touches
// the actual injury selection (st.target) - it's purely a browsing lens.
function wireInjGroupModeToggle(which, jointBtnId, muscleBtnId){
  var jointBtn = document.getElementById(jointBtnId);
  var muscleBtn = document.getElementById(muscleBtnId);
  if(!jointBtn || !muscleBtn) return;
  function setMode(mode){
    var st = injState(which);
    if(st.groupMode === mode) return;
    st.groupMode = mode;
    st.jointFilter = null;
    jointBtn.classList.toggle('active', mode === 'joint');
    muscleBtn.classList.toggle('active', mode === 'muscle');
    renderInjuryBrowser(which);
  }
  jointBtn.addEventListener('click', function(){ setMode('joint'); });
  muscleBtn.addEventListener('click', function(){ setMode('muscle'); });
}
wireInjGroupModeToggle('wiz', 'injModeJointBtn', 'injModeMuscleBtn');
wireInjGroupModeToggle('pg', 'pgInjModeJointBtn', 'pgInjModeMuscleBtn');

document.getElementById('injSearchInput').addEventListener('input', function(e){
  S.injSearchQuery = e.target.value;
  renderInjuryBrowser('wiz');
});
document.getElementById('injClearBtn').addEventListener('click', function(){
  S.injuries.clear();
  S.injuryStages = {};
  renderInjuryBrowser('wiz');
});
document.getElementById('pgInjSearchInput').addEventListener('input', function(e){
  S.pgInjSearchQuery = e.target.value;
  renderInjuryBrowser('pg');
});
document.getElementById('pgInjClearBtn').addEventListener('click', function(){
  S.pgInjuries.clear();
  S.pgInjuryStages = {};
  renderInjuryBrowser('pg');
});

function updateReadinessUI(){
  var out = document.getElementById('readinessReadout');
  out.textContent = S.readiness + '%';
  out.classList.toggle('low', S.readiness < 40);
  document.getElementById('deloadWarning').style.display = S.readiness < 40 ? 'block' : 'none';
}

// Fetches a suggested starting readiness from the backend's logged session
// history (see backend/services/readiness_service.py) and pre-fills the
// given slider + readout with it, showing the reasoning in `noteElId`.
// Never overrides silently forever — this only runs once when the step is
// opened; if the person then drags the slider themselves, that stands.
function fetchSuggestedReadiness(sport, sliderElId, readoutElId, noteElId, stateSetter){
  var note = document.getElementById(noteElId);
  fetch(API_BASE + '/api/v1/readiness/suggested?athlete_id=' + encodeURIComponent(ATHLETE_ID) +
    (sport ? '&sport=' + encodeURIComponent(sport) : ''), {headers: authHeaders()})
    .then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); })
    .then(function(data){
      if(data.basis === 'no_history'){
        if(note){ note.style.display = 'none'; }
        return;
      }
      var slider = document.getElementById(sliderElId);
      var readout = document.getElementById(readoutElId);
      if(slider){ slider.value = data.suggested_readiness; }
      if(readout){ readout.textContent = data.suggested_readiness + '%'; }
      if(stateSetter){ stateSetter(data.suggested_readiness); }
      if(note){
        note.style.display = 'block';
        note.innerHTML = '<b>Starting point from your training history:</b> ' + esc(data.explanation) +
          ' <span style="opacity:.75">(edit how you\'re feeling below to recalculate)</span>';
      }
      if(sliderElId === 'readinessInput'){ updateReadinessUI(); }
    })
    .catch(function(){ if(note){ note.style.display = 'none'; } });
}


function goToStep(n){
  S.wizStep = n;
  var ids = getWizardStepIds();
  var id = ids[n-1];
  document.querySelectorAll('.wizard-step').forEach(function(s){
    s.classList.toggle('active', s.getAttribute('data-step') === id);
  });
  var meta = WIZARD_STEPS[id];
  var dots = document.getElementById('progressDots');
  if(S.quickStart && id === 'readiness'){
    // Quick session: this is the only screen the person sees, so it isn't
    // really "step 3 of 6" to them - drop the step counter/progress dots
    // that would otherwise imply 5 more screens are coming.
    document.getElementById('wizStepLabel').textContent = "Today's Check-In";
    document.getElementById('wizTitle').innerHTML = 'How are you feeling today?';
    document.getElementById('wizSubtitle').innerHTML = 'Everything else is already saved on your profile — just today\'s readiness.';
    dots.innerHTML = '';
  } else {
    document.getElementById('wizStepLabel').textContent = 'Step '+n+' of '+ids.length;
    document.getElementById('wizTitle').innerHTML = meta.title;
    document.getElementById('wizSubtitle').innerHTML = meta.sub;
    dots.innerHTML = ids.map(function(sid, i){
      var cls = (i+1) < n ? 'done' : ((i+1) === n ? 'on' : '');
      // Editing an existing profile (S.wizardEditMode - set by
      // editAthleteProfile/btnMakeNewProgram, home.js/profile.js): every
      // field is already filled in from the saved profile, so "editing"
      // means jumping straight to whichever screen has the thing you want
      // to change, not clicking Next through five unrelated screens first.
      // A first-run wizard (nothing saved yet) leaves dots inert so someone
      // can't skip past a step - discipline, equipment, etc. - before
      // they've actually filled it in.
      return S.wizardEditMode
        ? '<span class="'+cls+' clickable" data-goto-step="'+(i+1)+'"></span>'
        : '<span class="'+cls+'"></span>';
    }).join('');
    if(S.wizardEditMode){
      dots.querySelectorAll('[data-goto-step]').forEach(function(dot){
        dot.addEventListener('click', function(){
          goToStep(parseInt(dot.getAttribute('data-goto-step'), 10));
        });
      });
    }
  }

  if(id === 'exercises'){
    renderExercisePicker();
    renderCustomWarmup();
    renderSavedCustomWorkoutsList();
    // Pull any workouts synced from another device in the background, then
    // re-render once merged — the local list above renders immediately so
    // this never blocks opening the panel.
    syncCustomWorkoutsFromBackend(renderSavedCustomWorkoutsList);
    if(document.getElementById('customWorkoutNameInput')) document.getElementById('customWorkoutNameInput').value = S.customWorkoutName;
    // "Last time" notes on each chip depend on logged history - fetched once
    // per session (customHistoryCache) and re-rendered in without blocking
    // the picker, which is already usable before this resolves.
    ensureCustomHistoryLoaded(function(){ renderExPickerSelected(); });
  }
  if(id === 'review'){
    renderReview();
    if(S.mode === 'custom' && S.selectedExercises.size) runCustomSafetyPrecheck();
  }
  if(id === 'readiness'){
    fetchSuggestedReadiness(S.sport, 'readinessInput', 'readinessReadout', 'readinessSuggestionNote', function(v){ S.readiness = v; });
  }
  updateWizardNav();
}
function updateWizardNav(){
  var ids = getWizardStepIds();
  var curId = ids[S.wizStep-1];
  var nextBtn = document.getElementById('btnWizNext');
  if(S.quickStart && curId === 'readiness'){
    // Quick session has no steps before or after this one - Back leaves
    // the wizard entirely (see btnWizBack below) and Next generates
    // directly instead of walking into biometrics/equipment/review.
    document.getElementById('btnWizBack').style.visibility = 'visible';
    nextBtn.textContent = 'Start Session →';
    nextBtn.disabled = false;
    return;
  }
  document.getElementById('btnWizBack').style.visibility = S.wizStep === 1 ? 'hidden' : 'visible';
  var atLastStep = S.wizStep === ids.length;
  nextBtn.textContent = atLastStep ? 'Generate Prescription →' : 'Next →';
  var onExercisesStep = curId === 'exercises';
  var nameEl = document.getElementById('bioName');
  var onBiometricsStep = curId === 'biometrics';
  nextBtn.disabled = (curId === 'discipline' && !S.sport) ||
    (onExercisesStep && S.selectedExercises.size === 0) ||
    (onBiometricsStep && nameEl && !nameEl.value.trim());
}
function renderReview(){
  var card = document.getElementById('reviewCard');
  var recoveryRow = '';
  if(S.recoveryEnabled){
    recoveryRow = row('Recovery inputs', 'Sleep '+numVal('riSleep')+'h · Soreness '+numVal('riSoreness')+'/5 · Stress '+numVal('riStress')+'/5 · Energy '+numVal('riEnergy')+'/5 · Motivation '+numVal('riMotivation')+'/5');
  }
  var modeRow = S.mode === 'custom'
    ? row('Mode', 'Custom — you chose every exercise, order, and prescription. FORGE only organizes, validates, and tracks it.')
    : row('Mode', 'Engine-recommended session');
  card.innerHTML =
    (S.athleteName ? row('Name', esc(S.athleteName)) : '') +
    row('Discipline', sportBadge(S.sport)+esc(S.sport)) +
    row('Focus', S.emphasis === 'hypertrophy' ? 'Look Jacked (higher reps, more sets)' :
      S.emphasis === 'strength_hypertrophy' ? 'Strength + Hypertrophy (5-8 reps, 70-82% 1RM)' :
      'Strength (balanced)') +
    modeRow +
    row('Experience', esc(S.experience)) +
    row('Readiness', S.readiness+'%' + (S.readiness<40 ? ' — Deload Mode' : '')) +
    row('Conditioning Focus', esc((CONDITIONING_LABELS[S.conditioningEmphasis] || {}).label || S.conditioningEmphasis)) +
    (S.mode === 'custom' ? '' : row('Session Length', '~'+S.sessionDuration+' min')) +
    recoveryRow +
    row('Equipment', S.equipment.size ? Array.from(S.equipment).map(esc).join(', ') : 'Bodyweight only') +
    row('Injuries flagged', S.injuries.size ? Array.from(S.injuries).map(function(n){ return formatInjuryWithStage(n, S.injuryStages, S.injurySides); }).join(', ') : 'None') +
    row('Biometrics', fmtRawUnit(numVal('bioWeight'))+' BW · Bench '+fmtRawUnit(numVal('bioBench'))+' · Squat '+fmtRawUnit(numVal('bioSquat'))+' · Deadlift '+fmtRawUnit(numVal('bioDeadlift')));
  if(S.mode === 'custom'){ card.innerHTML += renderCustomReviewSummary(); }
}
function row(label,val){
  return '<div class="review-row"><span>'+label+'</span><span>'+val+'</span></div>';
}

document.getElementById('btnWizNext').addEventListener('click', function(){
  var ids = getWizardStepIds();
  var curId = ids[S.wizStep-1];
  if(curId === 'biometrics'){
    // Confirms these numbers as real/answered - see bioStepConfirmedThisSession
    // above and prefillProgramBiometricsFromProfile in program-wizard-steps.js.
    S.bioStepConfirmedThisSession = true;
    // Persist name/sex/height/weight/1RMs the moment this step is confirmed,
    // instead of waiting for a full wizard run + generate() (saveAthleteProfile
    // is also called there, and will overwrite this with the complete profile
    // once the rest of the wizard is finished). Without this, closing the app
    // - or just clicking the Profile button - before finishing all 7 steps
    // meant hasAthleteProfile() stayed false, so Profile kept reopening Step 1
    // instead of showing the saved-profile summary/edit screen.
    if(typeof saveAthleteProfile === 'function') saveAthleteProfile();
  }
  if(S.quickStart && curId === 'readiness'){
    generate();
    return;
  }
  if(curId === 'discipline'){
    if(!S.sport) return;
    // Sport is picked on this step (after biometrics), so the step-1 save
    // above never had it. Re-save now so a Profile-button summary opened
    // right after this step already shows the chosen sport, not blank.
    if(typeof saveAthleteProfile === 'function') saveAthleteProfile();
    // Custom Mode (pick your own exercises for one session) is the only
    // thing left that still runs through the rest of this wizard
    // (equipment/injuries/readiness/exercises/review, ending in
    // generate()) - the old "Single Session" scope choice that used to
    // send preset picks down this same path is gone, so preset picks go
    // straight into the Program Builder instead.
    if(S.mode === 'custom' && typeof routeCustomToProgram === 'function'){
      // Custom builds a custom PROGRAM (Program Builder, custom-days mode),
      // not a single session - see routeCustomToProgram in sport-switch.js.
      routeCustomToProgram();
      return;
    }
    if(S.mode !== 'custom'){
      S.trainScope = 'program';
      // Carry the chosen discipline into the Program Builder's own form
      // instead of leaving pgSport on whatever populateProgramForm()
      // defaulted to back at boot() time, before any discipline existed.
      populateProgramForm();
      var pgSportSel = document.getElementById('pgSport');
      if(S.sport && pgSportSel){ pgSportSel.value = S.sport; }
      show('screen-program');
      return;
    }
    S.trainScope = 'custom';
  }
  if(curId === 'exercises' && S.selectedExercises.size === 0) return;
  if(S.wizStep === ids.length){
    if(S.mode === 'custom' && S.selectedExercises.size === 0){
      showToast('Your custom workout is empty — go back and add at least one exercise.', 'error');
      return;
    }
    generate();
    return;
  }
  goToStep(S.wizStep + 1);
});
// "No injuries — Skip" — clears any in-progress injury picks and moves
// straight on, for the common case of nothing to flag. Mirrors the
// Program wizard's btnPgInjurySkip (program-wizard-steps.js).
var btnInjurySkipEl = document.getElementById('btnInjurySkip');
if(btnInjurySkipEl){
  btnInjurySkipEl.addEventListener('click', function(){
    S.injuries.clear();
    if(S.injuryStages) for(var k in S.injuryStages) delete S.injuryStages[k];
    if(S.injurySides) for(var k2 in S.injurySides) delete S.injurySides[k2];
    if(typeof renderInjuryBrowser === 'function') renderInjuryBrowser('wiz');
    goToStep(S.wizStep + 1);
  });
}
document.getElementById('btnWizBack').addEventListener('click', function(){
  if(S.quickStart){
    // Quick session has nothing "before" its one screen - Back just
    // leaves the wizard the way step 1's Back always has.
    S.quickStart = false;
    show('screen-hero');
    return;
  }
  if(S.wizStep === 1){ show('screen-hero'); return; }
  goToStep(S.wizStep - 1);
});
document.getElementById('btnBuildStrength').addEventListener('click', function(){
  S.quickStart = false;
  // First-run, nothing saved yet - keep the wizard strictly linear (see
  // S.wizardEditMode in goToStep) so a fresh person can't skip past a step
  // before actually filling it in.
  S.wizardEditMode = false;
  S.emphasis = null;
  S.trainScope = null;
  show('screen-setup');
  goToStep(1);
});
document.getElementById('btnConditioning').addEventListener('click', function(){ show('screen-conditioning'); });

