'use strict';

// ============================================================
// PROGRAM WIZARD — step navigation (mirrors goToStep/updateWizardNav for
// the Train wizard, but scoped to #screen-program's own .pg-step elements
// and its own back/next buttons, so the two wizards can't interfere with
// each other's step state).
// ============================================================

// Pulls saved biometrics in from the Train wizard's Profile step (see
// profile.js) so the Program wizard doesn't ask the same height/weight/1RM
// questions a second time. If real, confirmed numbers are found, the
// "biometrics" step is skipped entirely (see getProgramWizardStepIds) —
// the fields are still filled in behind the scenes and remain editable via
// the Review step's "Biometrics" row.
//
// Two sources, checked in order:
//   1. A saved profile (localStorage) - written after a successful
//      generate(), see profile.js.
//   2. The live Train wizard "Your Profile" fields, but ONLY if the person
//      has actually confirmed that step this session (clicked Next past
//      it, or had a profile restored onto it - see bioStepConfirmedThisSession,
//      weight-unit.js). Without that guard this used to copy the fields'
//      static HTML defaults (175cm/75kg/10 pull-ups/80kg bench/etc, see
//      index.html) as if they were real answers the moment the Program
//      screen was ever touched (even at boot, before the person had looked
//      at anything) - which both skipped a step nobody had actually
//      answered AND fed made-up numbers into the strength-gated program
//      engine. That's what produced an "Operator Biometrics" step that
//      looked pre-filled with real-looking numbers no one had entered, and
//      wouldn't skip either.
function prefillProgramBiometricsFromProfile(){
  var p = loadAthleteProfile();
  var b = p && p.biometrics;
  var hasRealNumbers = b && (b.height_cm || b.weight_kg || b.bench_press_1rm_kg || b.squat_1rm_kg || b.deadlift_1rm_kg || b.pullups_max_reps || b.pushups_max_reps);
  if(hasRealNumbers){
    setNumField('pgBioHeight', b.height_cm);
    setNumField('pgBioWeight', kgToDisplay(b.weight_kg));
    setNumField('pgBioBench', kgToDisplay(b.bench_press_1rm_kg));
    setNumField('pgBioSquat', kgToDisplay(b.squat_1rm_kg));
    setNumField('pgBioDeadlift', kgToDisplay(b.deadlift_1rm_kg));
    setNumField('pgBioPullups', b.pullups_max_reps);
    setNumField('pgBioPushups', b.pushups_max_reps);
    if(b.sex){ var sexEl = document.getElementById('pgBioSex'); if(sexEl) sexEl.value = b.sex; }
    S.pgBiometricsPrefilled = true;
    return;
  }
  if(S.bioStepConfirmedThisSession){
    ['bioHeight','bioWeight','bioPullups','bioBench','bioSquat','bioDeadlift','bioPushups','bioSex'].forEach(function(id){
      var src = document.getElementById(id);
      var dst = document.getElementById('pg' + id.charAt(0).toUpperCase() + id.slice(1));
      if(src && dst) dst.value = src.value;
    });
    S.pgBiometricsPrefilled = true;
    return;
  }
  S.pgBiometricsPrefilled = false;
}

function goToProgramStep(n){
  var actionsBar = document.getElementById('pgWizActionsBar');
  if(actionsBar) actionsBar.style.display = ''; // back in wizard mode - undo any hiding generateProgram() did
  S.pgWizStep = n;
  var ids = getProgramWizardStepIds();
  var id = ids[n-1];
  document.querySelectorAll('#screen-program .pg-step').forEach(function(s){
    s.classList.toggle('active', s.getAttribute('data-pg-step') === id);
  });
  var meta = PG_WIZARD_STEPS[id];
  document.getElementById('pgWizStepLabel').textContent = 'Step '+n+' of '+ids.length;
  document.getElementById('pgWizTitle').innerHTML = meta.title;
  document.getElementById('pgWizSubtitle').innerHTML = meta.sub;

  var dots = document.getElementById('pgProgressDots');
  dots.innerHTML = ids.map(function(sid, i){
    var cls = (i+1) < n ? 'done' : ((i+1) === n ? 'on' : '');
    return '<span class="'+cls+'"></span>';
  }).join('');

  if(id === 'review') renderProgramReview();
  if(id === 'schedule'){
    var pgSport = document.getElementById('pgSport').value;
    fetchSuggestedReadiness(pgSport, 'pgReadiness', 'pgReadinessReadout', 'pgReadinessSuggestionNote', null);
  }
  if(id === 'customDays') renderPgCustomDaysStep();
  if(id === 'sportFocus') renderPgSportFocusStep();
  updateProgramWizardNav();
  window.scrollTo({top:0,behavior:smoothBehavior()});
}
function updateProgramWizardNav(){
  var ids = getProgramWizardStepIds();
  document.getElementById('btnPgWizBack').style.visibility = S.pgWizStep === 1 ? 'hidden' : 'visible';
  var nextBtn = document.getElementById('btnPgWizNext');
  var atLastStep = S.pgWizStep === ids.length;
  nextBtn.textContent = atLastStep ? 'Generate Program →' : 'Next →';
  // Custom Program mode: every day in the rotation needs at least one
  // exercise before the person can move on - an empty day would just
  // build an empty session server-side, same reasoning as the Train
  // wizard's own Custom Mode "at least one exercise" gate.
  var currentId = ids[S.pgWizStep - 1];
  if(currentId === 'customDays' && S.pgMode === 'custom'){
    var emptyDay = S.pgCustomDays.some(function(d){ return !d.exerciseIds.length; });
    nextBtn.disabled = emptyDay || !S.pgCustomDays.length;
  } else {
    nextBtn.disabled = false;
  }
}
// ------------------------------------------------------------
// SPORT FOCUS STEP — the extra sport-specific question(s) (Rugby's
// Positional Emphasis, MMA's Fight-Style Emphasis, Powerlifting's
// Periodization Style, ...) plus a browsable, filtered list of matching
// FORGE S&C templates (see sc_template_library.py). Picking a template
// here switches Generate (below) from the normal engine-generated
// program over to a template-fidelity build - the coach-authored
// template run as written, with only the individual slots that fail this
// athlete's own equipment/injury checks swapped out (see
// program_builder.build_template_fidelity_program's docstring). Not
// picking one (the default) changes nothing about the normal flow.
// ------------------------------------------------------------

function renderPgSportFocusStep(){
  var sport = currentPgSport();
  var questions = (S.scTemplateSportQuestions || {})[sport] || [];
  S.pgSportFocusAnswers = S.pgSportFocusAnswers || {};

  var qCard = document.getElementById('pgSportFocusQuestionsCard');
  var qWrap = document.getElementById('pgSportFocusQuestions');
  if(questions.length){
    qCard.style.display = '';
    document.getElementById('pgSportFocusHeading').textContent = sport + ' — Discipline Questions';
    qWrap.innerHTML = questions.map(function(q){
      var fieldId = 'pgSportFocus_' + q.field;
      var options = (q.optional ? ['(Not specified)'] : []).concat(q.options);
      return '<div class="field"><label>'+esc(q.label)+'</label><select id="'+fieldId+'" data-field="'+esc(q.field)+'">' +
        options.map(function(o){
          var val = o === '(Not specified)' ? '' : o;
          return '<option value="'+esc(val)+'">'+esc(o)+'</option>';
        }).join('') +
        '</select></div>';
    }).join('');
    questions.forEach(function(q){
      var sel = document.getElementById('pgSportFocus_' + q.field);
      if(!sel) return;
      if(S.pgSportFocusAnswers[q.field]) sel.value = S.pgSportFocusAnswers[q.field];
      else S.pgSportFocusAnswers[q.field] = sel.value; // seed from the select's own default
      sel.addEventListener('change', function(){
        S.pgSportFocusAnswers[q.field] = sel.value;
        S.pgSelectedTemplate = null; // answers changed - last pick may no longer be in the new list
        fetchPgSportFocusTemplates(sport, questions);
      });
    });
  } else {
    qCard.style.display = 'none';
    qWrap.innerHTML = '';
  }

  fetchPgSportFocusTemplates(sport, questions);
}

function fetchPgSportFocusTemplates(sport, questions){
  var listEl = document.getElementById('pgSportFocusTemplates');
  var emptyEl = document.getElementById('pgSportFocusNoTemplates');
  var level = document.getElementById('pgExperience').value;
  var preferredDays = parseInt(document.getElementById('pgDays').value, 10) || 0;

  // days_per_week is NOT sent as a filter here, deliberately - unlike the
  // engine's own seed match (which needs one exact template), these
  // libraries often ship only a single fixed days_per_week per level/
  // category (e.g. Rugby's Positional Emphasis set is 2 days/wk for
  // Beginner/Novice, 3 for Intermediate+) - filtering strictly on
  // whatever the Schedule step's day count happens to be turned up empty
  // for nearly every combination. Fetch every level/emphasis match
  // instead and sort the person's preferred day count to the top, so nothing
  // that actually exists is hidden - each card already shows its own
  // days/wk so the mismatch (if any) is visible, not silent.
  var params = new URLSearchParams();
  params.set('sport', sport);
  if(level) params.set('level', level);
  (questions || []).forEach(function(q){
    var val = S.pgSportFocusAnswers[q.field];
    if(!val) return;
    params.set(q.field === 'position' ? 'position' : 'emphasis', val);
  });

  listEl.innerHTML = '<div class="micro">Loading matching templates…</div>';
  emptyEl.style.display = 'none';

  fetch(API_BASE + '/api/v1/sc-templates?' + params.toString())
    .then(function(r){ return r.ok ? r.json() : {templates:[]}; })
    .then(function(data){
      var templates = (data.templates || []).slice();
      if(preferredDays){
        templates.sort(function(a, b){
          var aMatch = a.days_per_week === preferredDays ? 0 : 1;
          var bMatch = b.days_per_week === preferredDays ? 0 : 1;
          return aMatch - bMatch;
        });
      }
      templates = templates.slice(0, 6);
      if(!templates.length){
        listEl.innerHTML = '';
        emptyEl.style.display = '';
        // Nothing to run exactly - only option left is the engine build,
        // so make sure a stale pick from a previous answer combo doesn't
        // silently survive into Generate.
        S.pgSelectedTemplate = null;
        S.pgSelectedTemplateName = null;
        return;
      }
      // Best match (top of the sort above) is auto-selected by default -
      // Generate builds this exact template as written, not an
      // engine-generated program, unless the person explicitly picks
      // "Build with the engine instead" below. Keeps whatever's already
      // selected if it's still in this list (e.g. just navigating back to
      // this step); otherwise defaults to the top match.
      var stillValid = templates.some(function(t){ return t.global_id === S.pgSelectedTemplate; });
      if(!stillValid && S.pgSelectedTemplate !== 'ENGINE'){
        S.pgSelectedTemplate = templates[0].global_id;
        S.pgSelectedTemplateName = templates[0].name;
      }
      // Same background-image treatment as the discipline tiles
      // (SPORT_THEME/themeFor/firstImg, wizard-setup.js) - these cards were
      // rendering with no image at all before, which is why they looked
      // empty next to every other tile in the app. Each card now gets its
      // own shot out of the sport's gallery (nthImg, weight-unit.js) instead
      // of every card in the list being stamped with the same one photo -
      // sports with only a single photo on file still repeat it, same as
      // before, but anything with 2+ just cycles through them.
      var sportTheme = themeFor(sport);
      listEl.innerHTML = templates.map(function(t, idx){
        var selected = S.pgSelectedTemplate === t.global_id;
        var cardImg = nthImg(sportTheme, idx);
        var cardBg = cardImg ? "background-image:url('"+cardImg+"');" : '';
        return '<div class="choice sc-template-choice'+(selected?' selected':'')+'" data-global-id="'+esc(t.global_id)+'" style="margin-bottom:10px;--accent:'+sportTheme.accent+';'+cardBg+'">' +
          '<span class="checkmark">✓</span>' +
          '<div class="tile-body"><span class="icon">'+esc(sportTheme.mono)+'</span><h4>'+esc(t.name)+'</h4>' +
          '<span class="micro">'+esc(t.goal || '')+' · '+esc(String(t.days_per_week||'?'))+' days/wk · '+esc(String(t.duration_weeks||'?'))+' weeks</span></div>' +
          '</div>';
      }).join('') +
      '<div class="choice sc-template-choice'+(S.pgSelectedTemplate === 'ENGINE' ? ' selected' : '')+'" data-global-id="ENGINE" style="margin-bottom:10px;opacity:.85;">' +
        '<span class="checkmark">✓</span>' +
        '<div class="tile-body"><h4>Build with the engine instead</h4>' +
        '<span class="micro">Skip the fixed template — let the engine generate a program from your full setup (goal, biometrics, injuries, etc.)</span></div>' +
      '</div>';
      listEl.querySelectorAll('.sc-template-choice').forEach(function(card){
        card.addEventListener('click', function(){
          var gid = card.getAttribute('data-global-id');
          listEl.querySelectorAll('.sc-template-choice').forEach(function(c){ c.classList.remove('selected'); });
          card.classList.add('selected');
          S.pgSelectedTemplate = gid === 'ENGINE' ? null : gid;
          S.pgSelectedTemplateName = gid === 'ENGINE' ? null : card.querySelector('h4').textContent;
          if(gid === 'ENGINE') S.pgSelectedTemplate = 'ENGINE'; // sentinel distinct from "no answer yet" null, so a later re-fetch (answers unchanged) doesn't silently re-auto-pick a template out from under an explicit opt-out
        });
      });
    })
    .catch(function(){
      listEl.innerHTML = '';
      emptyEl.style.display = '';
    });
}

function renderProgramReview(){
  var splitSel = document.getElementById('pgSplit');
  var chosenSplit = S.splits.find(function(sp){ return sp.id === splitSel.value; });
  var phaseId = document.getElementById('pgTrainingPhase').value;
  var eqEl = document.getElementById('pgEquipmentChecks');
  var equipment = eqEl._equipmentSet ? Array.from(eqEl._equipmentSet) : ['Bodyweight'];
  var card = document.getElementById('pgReviewCard');
  var splitRow = S.pgMode === 'custom'
    ? row('Days', S.pgCustomDays.map(function(d){ return esc(d.label || 'Untitled') + ' (' + d.exerciseIds.length + ')'; }).join(', '))
    : row('Split', chosenSplit ? esc(chosenSplit.name) : 'Auto (recommended for you)');
  card.innerHTML =
    row('Discipline', esc(document.getElementById('pgSport').value)) +
    (S.pgSelectedTemplate && S.pgSelectedTemplate !== 'ENGINE' ? row('Template', esc(S.pgSelectedTemplateName || S.pgSelectedTemplate) + ' <span class="micro">(run as written — see Sport Focus step to change or clear)</span>') : '') +
    row('Experience', esc(document.getElementById('pgExperience').value)) +
    row('Program type', S.pgMode === 'custom' ? 'Custom (your own days)' : 'Preset split') +
    splitRow +
    row('Training phase', phaseId ? esc(phaseId) : 'Auto (no phase)') +
    row('Schedule', numVal('pgDays')+' days/week · '+numVal('pgWeeks')+' weeks · '+numVal('pgDuration')+' min/session') +
    row('Readiness', numVal('pgReadiness')+'%') +
    row('Conditioning focus', esc((CONDITIONING_LABELS[S.pgConditioningEmphasis] || {}).label || S.pgConditioningEmphasis)) +
    row('Equipment', equipment.length ? equipment.map(esc).join(', ') : 'Bodyweight only') +
    row('Injuries flagged', S.pgInjuries.size ? Array.from(S.pgInjuries).map(function(n){ return formatInjuryWithStage(n, S.pgInjuryStages, S.pgInjurySides); }).join(', ') : 'None') +
    row('Biometrics', fmtRawUnit(numVal('pgBioWeight'))+' BW · Bench '+fmtRawUnit(numVal('pgBioBench'))+' · Squat '+fmtRawUnit(numVal('pgBioSquat'))+' · Deadlift '+fmtRawUnit(numVal('pgBioDeadlift'))
      + (S.pgBiometricsPrefilled ? ' <span class="micro">(from your profile — </span><a href="#" class="exercise-link-btn" id="pgEditBiometricsLink" style="padding:3px 9px;font-size:10.5px;">Edit</a><span class="micro">)</span>' : ''));
  var editLink = document.getElementById('pgEditBiometricsLink');
  if(editLink){
    editLink.addEventListener('click', function(e){
      e.preventDefault();
      S.pgBiometricsPrefilled = false; // reveal the step again for editing
      var ids = getProgramWizardStepIds();
      goToProgramStep(ids.indexOf('biometrics') + 1);
    });
  }
}

document.getElementById('btnPgWizNext').addEventListener('click', function(){
  var ids = getProgramWizardStepIds();
  if(S.pgWizStep === ids.length){ generateProgram(); return; }
  goToProgramStep(S.pgWizStep + 1);
});
document.getElementById('btnPgWizBack').addEventListener('click', function(){
  if(S.pgWizStep === 1){ show('screen-hero'); return; }
  goToProgramStep(S.pgWizStep - 1);
});

// "No injuries — Skip" — clears any in-progress injury picks and moves
// straight on, for the common case of nothing to flag.
var btnPgInjurySkip = document.getElementById('btnPgInjurySkip');
if(btnPgInjurySkip){
  btnPgInjurySkip.addEventListener('click', function(){
    S.pgInjuries.clear();
    if(S.pgInjuryStages) for(var k in S.pgInjuryStages) delete S.pgInjuryStages[k];
    if(S.pgInjurySides) for(var k2 in S.pgInjurySides) delete S.pgInjurySides[k2];
    if(typeof renderInjuryBrowser === 'function') renderInjuryBrowser('pg');
    goToProgramStep(S.pgWizStep + 1);
  });
}

// Program Builder shares one screen (#screen-program) between the setup
// wizard and the built program. Before this existed, "finishing" the
// wizard only hid the Back/Generate button row - the step header
// ("Step 5 of 5" / "Review"), the progress dots, and the full Review
// step card stayed on screen with the generated program stacked
// underneath them, so every build looked like a second page bolted onto
// the leftover wizard chrome. This is the single switch between the two
// states: wizard chrome (#pgWizardChrome - dots, step header, all
// .pg-step cards, Back/Next row) XOR the result (#programResult) is
// visible, mirroring the clean single-purpose feel of screen-results.
function setProgramResultMode(active){
  var chrome = document.getElementById('pgWizardChrome');
  if(chrome) chrome.style.display = active ? 'none' : '';
  var result = document.getElementById('programResult');
  if(result) result.style.display = active ? '' : 'none';
}

function generateProgram(){
  var btn = document.getElementById('btnPgWizNext');
  var eqEl = document.getElementById('pgEquipmentChecks');
  var equipment = eqEl._equipmentSet ? Array.from(eqEl._equipmentSet) : ['Bodyweight'];

  // A template picked (or auto-recommended) on the Sport Focus step runs
  // template-fidelity (POST /sc-templates/{id}/build) instead of the
  // normal engine-generated program by default - same exercises/order/
  // prescription the coach wrote, only swapping the individual slots that
  // fail this athlete's equipment/injury checks right now (see
  // build_template_fidelity_program's docstring). 'ENGINE' is the
  // explicit "Build with the engine instead" opt-out from that same step -
  // only equipment/injuries carry over either way; goal/schedule/
  // biometrics don't apply to a fixed template.
  if(S.pgSelectedTemplate && S.pgSelectedTemplate !== 'ENGINE'){
    generateProgramFromTemplate(btn, equipment);
    return;
  }

  var payload = {
    mode: S.pgMode,
    primary_goal: document.getElementById('pgGoal').value,
    sport: document.getElementById('pgSport').value,
    experience_level: document.getElementById('pgExperience').value,
    equipment_available: equipment.length ? equipment : ['Bodyweight'],
    readiness: parseInt(document.getElementById('pgReadiness').value, 10),
    conditioning_emphasis: S.pgConditioningEmphasis,
    injuries: Array.from(S.pgInjuries),
    injury_stages: buildInjuryStagesPayload('pg'),
    injury_sides: buildInjurySidesPayload('pg'),
    days_per_week: parseInt(document.getElementById('pgDays').value, 10) || 3,
    weeks: parseInt(document.getElementById('pgWeeks').value, 10) || 4,
    session_duration_minutes: parseInt(document.getElementById('pgDuration').value, 10) || 60,
    preferred_split: document.getElementById('pgSplit').value,
    training_phase: document.getElementById('pgTrainingPhase').value || null,
    biometrics: {
      height_cm: parseFloat(document.getElementById('pgBioHeight').value) || 175,
      weight_kg: inputToKg(parseFloat(document.getElementById('pgBioWeight').value) || 75),
      bench_press_1rm: inputToKg(parseFloat(document.getElementById('pgBioBench').value) || 0),
      squat_1rm: inputToKg(parseFloat(document.getElementById('pgBioSquat').value) || 0),
      deadlift_1rm: inputToKg(parseFloat(document.getElementById('pgBioDeadlift').value) || 0),
      pullups_max_reps: parseInt(document.getElementById('pgBioPullups').value, 10) || 0,
      pushups_max_reps: parseInt(document.getElementById('pgBioPushups').value, 10) || 0,
      sex: document.getElementById('pgBioSex').value || null
    }
  };
  // Custom Program mode: send each day's own picks instead of relying on
  // preferred_split - see ProgramRequest.custom_days. preferred_split still
  // rides along above (harmless - the backend ignores it entirely once
  // mode="custom", see program_builder.generate_program's custom branch).
  if(S.pgMode === 'custom'){
    payload.custom_days = S.pgCustomDays.map(function(d){
      return {label: d.label || 'Untitled', selected_exercise_ids: d.exerciseIds.slice()};
    });
  }

  btn.disabled = true;
  var originalLabel = btn.textContent;
  btn.textContent = 'Building your program…';
  document.getElementById('programResult').innerHTML = '';

  fetch(API_BASE + '/api/v1/generate-program', {
    method: 'POST',
    headers: jsonAuthHeaders(),
    body: JSON.stringify(payload)
  })
    .then(function(r){
      return r.json().then(function(data){
        if(!r.ok) throw new Error(extractErrorMessage(data, 'Request failed'));
        return data;
      });
    })
    .then(function(data){
      data._usedInjuries = payload.injuries || [];
      data._usedInjuryStages = payload.injury_stages || {};
      data._usedInjurySides = payload.injury_sides || {};
      data._usedEquipment = payload.equipment_available || [];
      // Kept around (same idea as _usedInjuries/_usedEquipment above) so a
      // later in-workout swap on any day of this program can rebuild that
      // one day via generate-workout(mode=custom) with the same context
      // the whole program was generated with, instead of guessing at it.
      data._usedBiometrics = payload.biometrics;
      data._usedReadiness = payload.readiness;
      data._usedDuration = payload.session_duration_minutes;
      data._usedConditioningEmphasis = payload.conditioning_emphasis;
      S.lastProgram = data;
      S.lastProgramOriginal = JSON.parse(JSON.stringify(data));
      S.pgSavedProgramId = null; // freshly generated — not yet saved under any client_id
      S.programWeek = 1;
      S.programDayIndex = 0;
      S.programWhyOpen = {};
      S.programSessionLog = {};
      S.programSavedDays = {};
      setProgramResultMode(true);
      renderProgram(data);
      var resultEl = document.getElementById('programResult');
      resultEl.scrollIntoView({behavior:smoothBehavior(), block:'start'});
    })
    .catch(function(err){
      // A failed Regenerate would otherwise strand the person on the
      // hidden wizard with only an error message and no visible way back
      // to Edit Setup (renderProgram's own Edit/Regenerate buttons are
      // exactly what innerHTML below just wiped out) - bring the wizard
      // chrome back so the Review step (with Back/Generate) is right there.
      setProgramResultMode(false);
      document.getElementById('programResult').innerHTML =
        '<div class="callout danger"><b>Couldn\'t generate program.</b> '+esc(err.message || String(err))+'</div>';
      document.getElementById('screen-program').scrollIntoView({behavior:smoothBehavior(), block:'start'});
    })
    .finally(function(){
      btn.disabled = false;
      btn.textContent = originalLabel;
    });
}

function generateProgramFromTemplate(btn, equipment){
  // Biometrics don't change which exercises the template runs (goal/
  // schedule/exercise-selection still come from the coach-authored
  // template itself), but they DO feed the weight recommender: every
  // slot that carries a coach-written %1RM (see
  // build_template_fidelity_program's docstring) gets a real
  // working_weight_kg computed off these maxes, same as a normal
  // generated program - instead of leaving the athlete to do that math
  // by hand mid-session. Same pgBio* fields generateProgram() above
  // already collects for the engine path.
  var payload = {
    equipment_available: equipment.length ? equipment : ['Bodyweight'],
    injuries: Array.from(S.pgInjuries),
    injury_stages: buildInjuryStagesPayload('pg'),
    injury_sides: buildInjurySidesPayload('pg'),
    biometrics: {
      height_cm: parseFloat(document.getElementById('pgBioHeight').value) || 175,
      weight_kg: inputToKg(parseFloat(document.getElementById('pgBioWeight').value) || 75),
      bench_press_1rm: inputToKg(parseFloat(document.getElementById('pgBioBench').value) || 0),
      squat_1rm: inputToKg(parseFloat(document.getElementById('pgBioSquat').value) || 0),
      deadlift_1rm: inputToKg(parseFloat(document.getElementById('pgBioDeadlift').value) || 0),
      pullups_max_reps: parseInt(document.getElementById('pgBioPullups').value, 10) || 0,
      pushups_max_reps: parseInt(document.getElementById('pgBioPushups').value, 10) || 0,
      sex: document.getElementById('pgBioSex').value || null
    }
  };

  btn.disabled = true;
  var originalLabel = btn.textContent;
  btn.textContent = 'Building your program…';
  document.getElementById('programResult').innerHTML = '';

  fetch(API_BASE + '/api/v1/sc-templates/' + encodeURIComponent(S.pgSelectedTemplate) + '/build', {
    method: 'POST',
    headers: jsonAuthHeaders(),
    body: JSON.stringify(payload)
  })
    .then(function(r){
      return r.json().then(function(data){
        if(!r.ok) throw new Error(extractErrorMessage(data, 'Request failed'));
        return data;
      });
    })
    .then(function(data){
      // Adapt the template-fidelity response into the exact same shape
      // generate-program returns (split/program[week].days[].prescribed_workout)
      // and hand it to the normal renderProgram/renderProgramWeek/renderProgramDay
      // pipeline - see adaptTemplateFidelityToProgramShape's docstring for why:
      // a template-built program used to get its own separate, read-only,
      // visually-different renderer, and had no way to be saved/logged the
      // way an engine-generated one can.
      var adapted = adaptTemplateFidelityToProgramShape(data);
      // Same _used* context generateProgram() stashes on the engine path
      // (see its own .then above) - without this, swapping a single
      // exercise within a template-built day (workout-swap.js) or a PR
      // banner off a logged set (checkOneRMUpdate) had no biometrics/
      // equipment/injury context to work with, so a swapped-in exercise
      // would come back with no weight recommendation even though the
      // rest of the template now has one.
      adapted._usedInjuries = payload.injuries || [];
      adapted._usedInjuryStages = payload.injury_stages || {};
      adapted._usedInjurySides = payload.injury_sides || {};
      adapted._usedEquipment = payload.equipment_available || [];
      adapted._usedBiometrics = payload.biometrics;
      S.lastProgram = adapted;
      S.lastProgramOriginal = JSON.parse(JSON.stringify(adapted));
      S.pgSavedProgramId = null;
      S.programWeek = 1;
      S.programDayIndex = 0;
      S.programWhyOpen = {};
      S.programSessionLog = {};
      S.programSavedDays = {};
      setProgramResultMode(true);
      renderProgram(adapted);
      var resultEl = document.getElementById('programResult');
      resultEl.scrollIntoView({behavior:smoothBehavior(), block:'start'});
    })
    .catch(function(err){
      setProgramResultMode(false);
      document.getElementById('programResult').innerHTML =
        '<div class="callout danger"><b>Couldn\'t build this template.</b> '+esc(err.message || String(err))+'</div>';
      document.getElementById('screen-program').scrollIntoView({behavior:smoothBehavior(), block:'start'});
    })
    .finally(function(){
      btn.disabled = false;
      btn.textContent = originalLabel;
    });
}

// Standalone renderer for a template-fidelity build (flat `days`, no week
// progression - a coach-authored template is run as one fixed week,
// repeated for `duration_weeks`, not an engine mesocycle) - deliberately
// separate from renderProgram/renderProgramWeek, which assume the
// multi-week engine shape (weeks[], autoregulation, workout-swap, saved-
// program sync) this response doesn't have.
// Turns a /sc-templates/{id}/build response (flat `days`, one fixed week)
// into the exact shape /generate-program returns (`split` + `program[]` of
// {week_number, days[].prescribed_workout[]}) so a template-fidelity build
// renders through the SAME renderProgram/renderProgramWeek/renderProgramDay
// pipeline an engine-generated program does - same header, same exercise
// cards/pills, same editable prescription/log-set/swap UI, and (since
// saveCurrentProgram/loadSavedProgram only ever look at S.lastProgram's
// generic shape) the same Save Program / My Saved Programs flow too. A
// template used to render on its own separate, read-only, visually
// different screen with no way to save or log it at all.
//
// The template itself is one fixed week repeated for `duration_weeks`
// (the athlete progresses load themselves, not the engine) - that week is
// deep-cloned into `duration_weeks` week tabs so the week/day-tab UI and
// per-day session logging work exactly like a real mesocycle, rather than
// collapsing everything onto a single Week 1.
function adaptTemplateFidelityToProgramShape(data){
  function slug(s){ return 'tpl-' + (s||'').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/(^-|-$)/g, ''); }

  var baseDays = (data.days || []).map(function(day, i){
    var prescribed = [];
    var excludedList = [];
    (day.exercises || []).forEach(function(ex){
      if(ex.excluded){
        excludedList.push({name: ex.name, reasons: [ex.exclusion_reason].filter(Boolean)});
        return;
      }
      prescribed.push({
        id: ex.id || slug(ex.name),
        name: ex.name,
        category: ex.category || '',
        equipment: ex.equipment || '',
        experience_level: ex.experience_level || '',
        difficulty: ex.difficulty || 1,
        prescription: ex.prescription || null,
        // Template-specific badges (see renderProgramDay's pillrow) - always
        // undefined on a normal engine-generated exercise, so this never
        // shows up outside a template-built program.
        _templateVerified: ex.verified,
        _templateSubstitutedFor: ex.substituted_for,
        _templateSubstitutionReason: ex.substitution_reason,
        // conditioning_engine.resolve_conditioning_exercise's own fields
        // (Category A protocols - see forge_category_audit.md) - only
        // present when this slot resolved to a conditioning protocol
        // rather than a real exercises.json lift. conditioning_protocol
        // tells renderPrescriptionEditable to use renderConditioningPrescription
        // instead of the generic sets/reps/rest editor, since this
        // prescription shape doesn't share that editor's field names.
        conditioning_protocol: ex.conditioning_protocol,
        family_label: ex.family_label,
        energy_system: ex.energy_system,
        requires_supervision: ex.requires_supervision,
        safety_note: ex.safety_note
      });
    });
    return {
      day_label: day.label || day.name || ('Day '+(i+1)),
      exercise_count: prescribed.length,
      prescribed_workout: prescribed,
      excluded_exercises: excludedList,
      session_structure: [{phase: 'Session', exercises: prescribed.map(function(e){ return e.id; })}]
    };
  });

  var weeksCount = Math.max(1, data.duration_weeks || 1);
  var program = [];
  for(var w = 1; w <= weeksCount; w++){
    program.push({week_number: w, is_deload: false, days: JSON.parse(JSON.stringify(baseDays))});
  }

  var subNote = (data.substitutions_made || data.exercises_excluded)
    ? (esc(String(data.substitutions_made||0))+' exercise(s) swapped and '+esc(String(data.exercises_excluded||0))+' excluded to fit your equipment/injuries.')
    : '';

  return {
    template_fidelity: true,
    global_id: data.global_id,
    split: {
      name: data.name || 'FORGE S&C Template',
      description: 'Coach-authored FORGE S&C Template — run exactly as written each week' +
        (subNote ? '. ' + subNote : '.')
    },
    sport: data.sport,
    experience_level: data.level,
    primary_goal: data.goal,
    days_per_week: data.days_per_week,
    weeks: weeksCount,
    program: program,
    personalization_applied: false
  };
}

// ------------------------------------------------------------
// SAVED PROGRAMS — localStorage is always the source of truth (works
// offline, no login required, same "local write always happens, server
// sync is fire-and-forget on top of it" pattern as custom-workout-builder.js
// and history.js). A logged-in account additionally syncs saved programs
// across devices — that's the only thing an account adds here.
// ------------------------------------------------------------
var SAVED_PROGRAMS_KEY = 'forge_saved_programs';
function loadSavedProgramsLocal(){
  try{ return JSON.parse(localStorage.getItem(SAVED_PROGRAMS_KEY)) || []; }
  catch(e){ return []; }
}
function persistSavedProgramsLocal(arr){
  try{ localStorage.setItem(SAVED_PROGRAMS_KEY, JSON.stringify(arr)); }
  catch(e){ /* storage unavailable — ignore, same fallback as history.js */ }
}
// Fire-and-forget POST to /api/v1/programs, keyed by the same client_id
// the local record already uses — saving again from this or another
// device updates the same synced row instead of duplicating it. Never
// blocks or errors the local save above.
function syncProgramToBackend(record){
  if(!S.currentUser) return; // logged-out: local-only, same as custom workouts
  fetch(API_BASE + '/api/v1/programs', {
    method: 'POST',
    headers: jsonAuthHeaders(),
    body: JSON.stringify({
      client_id: record.client_id,
      label: record.label,
      sport: record.sport || null,
      experience_level: record.experience_level || null,
      weeks: record.weeks || null,
      days_per_week: record.days_per_week || null,
      program: record.program
    })
  }).catch(function(){ /* local copy already saved — will sync next time */ });
}
function syncProgramDeleteToBackend(clientId){
  if(!S.currentUser) return;
  fetch(API_BASE + '/api/v1/programs/' + encodeURIComponent(clientId), {method:'DELETE', headers: authHeaders()})
    .catch(function(){});
}
function saveCurrentProgram(){
  if(!S.lastProgram){ return; }
  var d = S.lastProgram;
  var clientId = S.pgSavedProgramId || ('pg' + Date.now());
  var label = (d.split && d.split.name ? d.split.name : 'Program') + ' — ' + (d.sport || '');
  var record = {
    client_id: clientId,
    label: label.trim(),
    sport: d.sport || null,
    experience_level: d.experience_level || null,
    weeks: d.weeks || null,
    days_per_week: d.days_per_week || null,
    program: d,
    savedAt: new Date().toISOString()
  };
  var all = loadSavedProgramsLocal();
  var idx = all.findIndex(function(p){ return p.client_id === clientId; });
  if(idx === -1) all.push(record); else all[idx] = record;
  persistSavedProgramsLocal(all);
  S.pgSavedProgramId = clientId;
  syncProgramToBackend(record);
  var btn = document.getElementById('btnSaveProgram');
  if(btn){ btn.textContent = '💾 Update Saved'; }
  showToast(S.currentUser
    ? 'Program saved — synced to your account.'
    : 'Program saved on this device. Log in to also sync it across devices.');
}
// Pulls synced programs from the backend (when logged in) and merges them
// into the local list by client_id — same "backend wins for a shared id,
// purely-local records from before login are kept too" pattern as
// syncCustomWorkoutsFromBackend. Falls back to the local list alone if
// logged out or unreachable.
function syncSavedProgramsFromBackend(cb){
  if(!S.currentUser){ if(cb) cb(loadSavedProgramsLocal()); return; }
  fetch(API_BASE + '/api/v1/programs', {headers: authHeaders()})
    .then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); })
    .then(function(rows){
      var local = loadSavedProgramsLocal();
      var byId = {};
      local.forEach(function(p){ byId[p.client_id] = p; });
      rows.forEach(function(r){ byId[r.client_id] = r; });
      var merged = Object.values(byId);
      persistSavedProgramsLocal(merged);
      if(cb) cb(merged);
    })
    .catch(function(){ if(cb) cb(loadSavedProgramsLocal()); });
}
function openSavedProgramsModal(){
  var overlay = document.getElementById('modalOverlay');
  var content = document.getElementById('modalContent');
  content.innerHTML =
    '<button class="close-btn" id="modalClose">&times;</button>'+
    '<h3>My Saved Programs</h3>'+
    '<div class="modal-section" id="savedProgramsListBox"><div class="modal-loading">Loading…</div></div>';
  overlay.classList.add('active');
  document.getElementById('modalClose').addEventListener('click', closeModal);
  renderSavedProgramsList(loadSavedProgramsLocal());
  syncSavedProgramsFromBackend(function(rows){ renderSavedProgramsList(rows); });
}
function renderSavedProgramsList(rows){
  var box = document.getElementById('savedProgramsListBox');
  if(!box) return;
  if(!rows.length){ box.innerHTML = '<div class="empty">No saved programs yet — generate one and hit "Save Program".</div>'; return; }
  box.innerHTML = rows.map(function(r){
    return '<div class="saved-workout-row" data-saved-program="'+esc(r.client_id)+'">' +
      '<div class="saved-workout-info"><b>'+esc(r.label || 'Program')+'</b>' +
        '<span class="exmeta">'+esc(r.sport||'')+' · '+(r.weeks||'?')+' wk · '+(r.days_per_week||'?')+'x/wk</span></div>' +
      '<div class="saved-workout-actions">' +
        '<button type="button" class="btn secondary small" data-load-program="'+esc(r.client_id)+'">Load</button>' +
        '<button type="button" class="btn secondary small danger" data-delete-program="'+esc(r.client_id)+'">Delete</button>' +
      '</div>' +
    '</div>';
  }).join('');
  box.querySelectorAll('[data-load-program]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var id = btn.getAttribute('data-load-program');
      var row = rows.filter(function(r){ return r.client_id === id; })[0];
      if(!row) return;
      // loadSavedProgram sets S.lastProgram before show('screen-program')
      // runs, so its first-visit check (nav-control.js) doesn't mistake
      // this for a fresh visit and reset to wizard step 1. This modal can
      // now be opened from Home as well as from screen-program itself
      // (see btnViewProgram, home.js), so make the screen switch explicit
      // instead of assuming the caller is already there.
      loadSavedProgram(row);
      show('screen-program');
      closeModal();
    });
  });
  box.querySelectorAll('[data-delete-program]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var id = btn.getAttribute('data-delete-program');
      showConfirm('Delete this saved program? This can\'t be undone.', {title:'Delete program?'}).then(function(ok){
      if(!ok) return;
      var all = loadSavedProgramsLocal().filter(function(p){ return p.client_id !== id; });
      persistSavedProgramsLocal(all);
      syncProgramDeleteToBackend(id);
      if(S.pgSavedProgramId === id) S.pgSavedProgramId = null;
      renderSavedProgramsList(all);
      });
    });
  });
}
function loadSavedProgram(row){
  var data = row.program;
  S.lastProgram = data;
  S.lastProgramOriginal = JSON.parse(JSON.stringify(data));
  S.pgSavedProgramId = row.client_id;
  S.programWeek = 1;
  S.programDayIndex = 0;
  S.programWhyOpen = {};
  S.programSessionLog = {};
  S.programSavedDays = {};
  setProgramResultMode(true);
  renderProgram(data);
  document.getElementById('programResult').scrollIntoView({behavior:smoothBehavior(), block:'start'});
  showToast('Loaded "' + esc(row.label || 'Program') + '".');
}
var openSavedProgramsBtnEl = document.getElementById('btnOpenSavedPrograms');
if(openSavedProgramsBtnEl) openSavedProgramsBtnEl.addEventListener('click', openSavedProgramsModal);

function renderProgram(data){
  var el = document.getElementById('programResult');
  var html = '';

  // Header matches screen-results' own .topline exactly (step label / h2 /
  // subtitle / right-aligned actions) so a built program reads as the same
  // kind of screen as a built session, not a different page glued below
  // the wizard - see setProgramResultMode for the chrome-swap this pairs with.
  html += '<div class="topline">'+
    '<div>'+
      '<div class="step">'+(S.pgSavedProgramId ? 'Program Loaded' : 'Program Ready')+'</div>'+
      '<h2>'+esc(data.split.name)+'</h2>'+
      '<p>'+esc(data.sport)+' &nbsp;·&nbsp; '+esc(data.experience_level)+' &nbsp;·&nbsp; '+esc(data.primary_goal)+
        ' &nbsp;·&nbsp; '+data.days_per_week+' days/wk &nbsp;·&nbsp; '+data.weeks+' weeks'+
        (data.periodization_model ? ' &nbsp;·&nbsp; '+esc(data.periodization_model) : '')+
      '</p>'+
    '</div>'+
    '<div class="actions" style="margin:0;flex-wrap:wrap;gap:10px;align-items:center;">'+
      '<button type="button" class="btn secondary small" id="btnEditProgramSetup">✎ Edit Setup</button>'+
      '<button type="button" class="btn secondary small" id="btnRegenerateProgram">↻ Regenerate</button>'+
      '<button type="button" class="btn green" id="btnSaveProgram">'+(S.pgSavedProgramId ? '💾 Update Saved' : '💾 Save Program')+'</button>'+
    '</div>'+
  '</div>';
  html += '<p class="micro" style="margin-top:-6px;margin-bottom:18px;">'+esc(data.split.description)+'</p>';
  html += data.personalization_applied ?
    '<div class="callout blue">Ranked using your logged training history — see "Why this exercise?" on each pick.</div>' :
    '<div class="progression-note" style="margin-bottom:14px;">Not personalized yet — log a few sessions and this ranking will start using your own history.</div>';
  html += renderCoachNotes(data.coach_notes);
  if(data.periodization_rationale){
    html += '<div class="callout">'+esc(data.periodization_rationale)+'</div>';
  }
  if(data.split.recommended_for_sport && data.split.sport_rationale){
    html += '<div class="callout">'+esc(data.split.sport_rationale)+'</div>';
  }
  if(data.split.experience_capped && data.split.experience_rationale){
    html += '<div class="callout">'+esc(data.split.experience_rationale)+'</div>';
  }
  if(data.level_check && data.level_check.estimated_level && data.level_check.agrees === false){
    html += '<div class="callout blue"><b>Level check.</b> '+esc(data.level_check.note)+
      ' <span class="pill">'+esc(data.level_check.confidence)+' confidence</span></div>';
  }
  if(data.deload_week){
    html += '<div class="callout">Week <b>'+data.deload_week+'</b> is an automatic deload — lighter and shorter to let you recover before repeating or progressing the cycle.</div>';
  }

  if(data.training_phase){
    var tp = data.training_phase;
    html += '<div class="callout blue"><b>'+esc(tp.phase)+'</b>'+
      (tp.typical_duration ? ' <span class="pill">'+esc(tp.typical_duration)+'</span>' : '')+
      '<br>'+esc(tp.lifting_focus || '')+' '+esc(tp.conditioning_focus || '')+'</div>';
  }

  if(data.conditioning_guidance){
    var cg = data.conditioning_guidance;
    html += '<div class="callout"><b>Conditioning — '+esc(cg.sport)+'.</b> '+
      'Aim for roughly <b>'+cg.aerobic_pct+'% aerobic / '+cg.lactic_pct+'% lactic</b> conditioning work. '+
      esc(cg.conditioning_notes)+'<br><span class="micro">Time-saver: '+esc(cg.time_saver)+'</span></div>';
  }

  html += '<div class="week-tabs" id="weekTabs">' + data.program.map(function(w){
    var cls = 'week-tab' + (w.week_number === S.programWeek ? ' active' : '') + (w.is_deload ? ' deload' : '');
    return '<button class="'+cls+'" data-week="'+w.week_number+'">Week '+w.week_number+(w.is_deload ? ' · Deload' : '')+'</button>';
  }).join('') + '</div>';

  html += '<div id="weekBody"></div>';

  el.innerHTML = html;

  document.getElementById('weekTabs').addEventListener('click', function(e){
    var btn = e.target.closest('button[data-week]');
    if(!btn) return;
    S.programWeek = parseInt(btn.getAttribute('data-week'), 10);
    S.programDayIndex = 0; // land on day 1 of the newly-picked week rather than carrying over an index that may not exist there
    document.querySelectorAll('#weekTabs .week-tab').forEach(function(b){
      b.classList.toggle('active', parseInt(b.getAttribute('data-week'),10) === S.programWeek);
    });
    renderProgramWeek(data);
  });

  renderProgramWeek(data);
  el.scrollIntoView({behavior:smoothBehavior(), block:'start'});
}

// Renders ONE day of the active week at a time (picked via the day-tabs),
// instead of every day in the week stacked and fully expanded together —
// that flat wall of days/exercises was the confusing part of the program
// output. Move/remove/save/log logic is unchanged; only what's painted
// into the DOM at once is scoped down to the selected day.
function renderProgramWeek(data){
  var week = data.program.find(function(w){ return w.week_number === S.programWeek; });
  var body = document.getElementById('weekBody');
  if(!week){ body.innerHTML = ''; return; }

  if(S.programDayIndex >= week.days.length) S.programDayIndex = 0;

  var html = '';

  if(week.is_deload && week.deload_reason === 'signal'){
    html += '<div class="callout">⚡ <b>Auto-deload.</b> ' + esc(week.deload_explanation || 'Your recent soreness/fatigue trend suggested lighter training this week.') + '</div>';
  }

  html += '<div class="day-tabs" id="dayTabs">' + week.days.map(function(day, dayIndex){
    var dayKey = S.programWeek + '|' + dayIndex;
    var cls = 'day-tab' + (dayIndex === S.programDayIndex ? ' active' : '');
    return '<button class="'+cls+'" data-day="'+dayIndex+'">'+
      (S.programSavedDays[dayKey] ? '<span class="dtsaved" title="Saved to history"></span>' : '')+
      esc(day.day_label)+' <span class="dtcount">'+day.exercise_count+' ex</span>'+
      '</button>';
  }).join('') + '</div>';
  html += '<div class="day-progress">Day '+(S.programDayIndex+1)+' of '+week.days.length+'</div>';

  html += '<div id="dayBody"></div>';

  body.innerHTML = html;

  document.getElementById('dayTabs').addEventListener('click', function(e){
    var btn = e.target.closest('button[data-day]');
    if(!btn) return;
    S.programDayIndex = parseInt(btn.getAttribute('data-day'), 10);
    renderProgramWeek(data);
  });

  renderProgramDay(week, S.programDayIndex);
}

function renderProgramDay(week, dayIndex){
  var day = week.days[dayIndex];
  var dayBody = document.getElementById('dayBody');
  if(!day){ dayBody.innerHTML = ''; return; }

  var byId = {};
  day.prescribed_workout.forEach(function(ex){ byId[ex.id] = ex; });
  var dayKey = S.programWeek + '|' + dayIndex;
  var alreadySaved = !!S.programSavedDays[dayKey];

  var html = '<div class="day-block">';
  html += '<div class="day-block-head"><h4>'+esc(day.day_label)+'</h4>'+
    (day.emphasis ? '<span class="pill">'+esc(day.emphasis)+' emphasis</span>' : '') +
    '<span class="pill">'+day.exercise_count+' exercises</span>' +
    (day.deload_mode ? '<span class="pill">deload</span>' : '') +
    '</div>';
  html += renderAdaptiveLoadNote(day.adaptive_training_load);
  if(!day.prescribed_workout.length){
    html += '<div class="callout danger" style="margin-top:0;">Nothing qualified for this day — loosen an equipment or injury filter.</div>';
  }

  var dayScope = ' data-ex-week="'+S.programWeek+'" data-ex-dayindex="'+dayIndex+'"';
  html += '<div class="session-editbar">'+
    (day.prescribed_workout.length ? '<button type="button" class="btnResetDayOrder" data-reset-week="'+S.programWeek+'" data-reset-dayindex="'+dayIndex+'">↺ Reset removals &amp; order</button>' : '')+
    '<button type="button" data-toggle-add-ex="day"'+dayScope+'>+ Add Exercise</button>'+
  '</div>';
  html += addExercisePanelHtml('day');

  // day.session_structure isn't reassigned back onto `day` below when it's
  // freshly built from prescribed_workout (only when the API already
  // provided one) — normalize it onto `day` itself so remove/reorder edits
  // (which mutate day.session_structure in place) have something to mutate
  // even on a day that came back with no explicit structure from the API.
  if(!day.session_structure || !day.session_structure.length){
    day.session_structure = [{phase: 'Session', exercises: day.prescribed_workout.map(function(ex){ return ex.id; })}];
  }
  var structure = day.session_structure;
  var flatIds = flatExIds(day);
  var idx = 0;

  structure.forEach(function(phase, pIdx){
    html += '<div class="phase-label"><span class="n">'+(pIdx+1)+'</span><h3>'+esc(phase.phase)+'</h3></div>';
    phase.exercises.forEach(function(exId){
      var ex = byId[exId];
      if(!ex) return;
      idx++;
      var flatPos = flatIds.indexOf(exId);
      var stars = DIFFICULTY_STARS[ex.difficulty] || '★'.repeat(ex.difficulty || 1);
      var whyKey = dayKey + '::' + ex.id;
      var whyOpen = !!S.programWhyOpen[whyKey];
      html += '<div class="exercise" data-exid="'+esc(ex.id)+'" style="animation-delay:'+(idx*0.04)+'s;">'+
        '<div class="exerciseTop">'+
          '<h4><span class="rank">'+idx+'</span><span class="exname" data-open-modal="'+esc(ex.id)+'">'+esc(ex.name)+'</span></h4>'+
          (!isStrengthMode() && ex.sport_priority_score != null ? '<div class="transfer">Transfer <b>'+ex.sport_priority_score+'</b></div>' : '')+
          exEditButtons(ex.id, flatPos, flatIds.length, S.programWeek, dayIndex)+
        '</div>'+
        '<div class="pillrow">'+(ex.conditioning_protocol ? pill(ex.family_label) : pill(ex.category))+pill(ex.equipment)+(ex.conditioning_protocol ? '' : pill(ex.experience_level))+pill(stars)+(ex._addedByUser?pill('added by you'):'')+
          (ex._templateSubstitutedFor ? '<span class="pill" title="'+esc(ex._templateSubstitutionReason||'')+'">Swapped in for '+esc(ex._templateSubstitutedFor)+'</span>' : '')+
          (ex._templateVerified === false ? '<span class="pill">Unverified — not in exercise database, check manually</span>' : '')+
        '</div>'+
        renderPrescriptionEditable(ex, ' data-ex-week="'+S.programWeek+'" data-ex-dayindex="'+dayIndex+'"');
      if(ex.prescription && ex.prescription.progression_note){
        html += '<div class="progression-note'+(ex.prescription.autoregulated ? ' autoreg' : '')+'">'+
          (ex.prescription.autoregulated ? '⚡ ' : '')+esc(ex.prescription.progression_note)+'</div>';
      }
      if(ex.prescription && ex.prescription.sleep_adjusted){
        html += '<div class="caution"><b>Sleep-adjusted —</b> '+esc(ex.prescription.note||'Load trimmed for poor sleep.')+'</div>';
      }
      if(ex.injury_caution){
        html += '<div class="caution"><b>Caution —</b> '+esc(ex.injury_caution)+'</div>';
      }
      html += '<button type="button" class="why-toggle" data-why-toggle="'+esc(whyKey)+'">'+(whyOpen ? 'Hide why this exercise ▲' : 'Why this exercise? ▾')+'</button>';
      html += '<div class="why'+(whyOpen ? ' open' : '')+'">'+
        (ex.personalization_note ? '<div><b>Your history.</b> '+esc(ex.personalization_note)+'</div>' : '')+
        (!isStrengthMode() ? '<div><b>Sport transfer.</b> '+esc(ex.sport_transfer_rationale||'')+'</div>' : '')+
        '<div><b>Programming role.</b> '+esc(ex.programming_role_rationale||'')+'</div>'+
        (ex.experience_level_fit ? '<div><b>Experience level.</b> '+esc(ex.experience_level_fit)+'</div>' : '')+
        '</div>';
      html += '<button type="button" class="why-toggle" data-pg-swap-open="'+esc(ex.id)+'">'+(ex.injury_caution ? '🔄 Find a safer swap ▾' : '🔄 Swap this exercise ▾')+'</button>';
      html += '<div class="swap-panel" data-pg-swap-panel="'+esc(ex.id)+'"></div>';
      html += '<div class="logged-sets" data-logged-for="'+esc(dayKey)+'::'+esc(ex.id)+'"></div>';
      // Same per-hand framing as the single-session log row (exercise-editing.js) - a
      // Dumbbell exercise's logged weight is always one hand's load.
      var isDbDay = ex.equipment === 'Dumbbell';
      html += '<div class="logrow">'+
        '<input type="number" placeholder="'+(isDbDay ? 'Weight per hand (' : 'Weight (')+(S.unit==="lb"?"lb":"kg")+')" class="logw" min="0">'+
        '<input type="number" placeholder="Reps" class="logr" min="0">'+
        '<button class="btn small" data-log-set="'+esc(ex.id)+'" data-log-name="'+esc(ex.name)+'" data-log-daykey="'+esc(dayKey)+'">Log Set</button>'+
        '<span></span>'+
      '</div>';
      html += '</div>';
    });
  });
  if(day.prescribed_workout.length){
    html += '<div class="actions" style="margin-top:14px;flex-wrap:wrap;gap:10px;align-items:center;">'+
      '<label style="font-size:12px;">Soreness after '+
        '<select class="pf-soreness"><option value="">–</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option></select>'+
      '</label>'+
      '<label style="font-size:12px;">Fatigue '+
        '<select class="pf-fatigue"><option value="">–</option><option value="1">1</option><option value="2">2</option><option value="3">3</option><option value="4">4</option><option value="5">5</option></select>'+
      '</label>'+
      '<button class="btn'+(alreadySaved ? ' secondary' : '')+'" data-save-day="'+esc(dayKey)+'" '+
        'data-save-week="'+S.programWeek+'" data-save-daylabel="'+esc(day.day_label)+'" data-save-dayindex="'+dayIndex+'">'+
        (alreadySaved ? '✓ Saved to History — update' : 'Finish & Save This Session') +
      '</button></div>';
  }
  if(day.excluded_exercises && day.excluded_exercises.length){
    html += '<details class="locked" style="margin-top:18px;"><summary>All Locked Protocols ('+day.excluded_exercises.length+')</summary>';
    day.excluded_exercises.forEach(function(ex){
      html += renderLockedExercise(ex);
    });
    html += '</details>';
  }
  html += '</div>';

  dayBody.innerHTML = html;

  if(S.addExPanelOpen) renderAddExResults('day', S.addExQuery, ' data-ex-week="'+S.programWeek+'" data-ex-dayindex="'+dayIndex+'"');

  // repaint any sets already logged for this day (e.g. after switching day/week tabs and back)
  var log = S.programSessionLog[dayKey];
  if(!log) return;
  Object.keys(log).forEach(function(exId){
    var container = document.querySelector('.logged-sets[data-logged-for="'+cssEsc(dayKey+'::'+exId)+'"]');
    if(!container) return;
    var exForRepaint = (day.prescribed_workout || []).find(function(e){ return e.id === exId; });
    var isDbRepaint = exForRepaint && exForRepaint.equipment === 'Dumbbell';
    log[exId].sets.forEach(function(s){
      var row = document.createElement('div');
      row.className = 'logged-set';
      row.innerHTML = '<span>'+fmtWeight(s.weight)+(isDbRepaint ? ' each hand' : '')+' × '+s.reps+'</span>' + (s.isPR ? '<span class="pr">PR</span>' : '');
      container.appendChild(row);
    });
  });
}

document.getElementById('programResult').addEventListener('click', function(e){
  var saveProgramBtn = e.target.closest('#btnSaveProgram');
  if(saveProgramBtn){ saveCurrentProgram(); return; }
  var editSetupBtn = e.target.closest('#btnEditProgramSetup');
  if(editSetupBtn){
    setProgramResultMode(false);
    document.getElementById('programResult').innerHTML = '';
    goToProgramStep(1);
    document.getElementById('screen-program').scrollIntoView({behavior:smoothBehavior(), block:'start'});
    return;
  }
  var regenBtn = e.target.closest('#btnRegenerateProgram');
  if(regenBtn){ generateProgram(); return; }

  var whyToggle = e.target.closest('[data-why-toggle]');
  if(whyToggle){
    var whyKey = whyToggle.getAttribute('data-why-toggle');
    var whyBox = whyToggle.nextElementSibling;
    var nowOpen = !S.programWhyOpen[whyKey];
    S.programWhyOpen[whyKey] = nowOpen;
    if(whyBox && whyBox.classList.contains('why')){ whyBox.classList.toggle('open', nowOpen); }
    whyToggle.textContent = nowOpen ? 'Hide why this exercise ▲' : 'Why this exercise? ▾';
    return;
  }

  var pgSwapOpenBtn = e.target.closest('[data-pg-swap-open]');
  if(pgSwapOpenBtn){ toggleProgramSwapPanel(pgSwapOpenBtn.getAttribute('data-pg-swap-open')); return; }
  var pgSwapPickBtn = e.target.closest('[data-pg-swap-pick]');
  if(pgSwapPickBtn && !pgSwapPickBtn.disabled){
    applyProgramSwap(pgSwapPickBtn.getAttribute('data-pg-swap-old'), pgSwapPickBtn.getAttribute('data-pg-swap-pick'), pgSwapPickBtn.getAttribute('data-pg-swap-name'));
    return;
  }

  var nameEl = e.target.closest('[data-open-modal]');
  if(nameEl){ openExerciseModal(nameEl.getAttribute('data-open-modal')); return; }

  var moveBtn = e.target.closest('[data-ex-move]');
  if(moveBtn && !moveBtn.disabled){
    var mvId = moveBtn.getAttribute('data-ex-id');
    var mvWeek = parseInt(moveBtn.getAttribute('data-ex-week'), 10);
    var mvDayIdx = parseInt(moveBtn.getAttribute('data-ex-dayindex'), 10);
    var dir = moveBtn.getAttribute('data-ex-move') === 'up' ? -1 : 1;
    var mvWeekObj = S.lastProgram && S.lastProgram.program.find(function(w){ return w.week_number === mvWeek; });
    var mvDay = mvWeekObj && mvWeekObj.days[mvDayIdx];
    if(mvDay && moveExerciseIn(mvDay, mvId, dir)){ renderProgramWeek(S.lastProgram); }
    return;
  }
  var removeBtn = e.target.closest('[data-ex-remove]');
  if(removeBtn){
    var rmId = removeBtn.getAttribute('data-ex-remove');
    var rmWeek = parseInt(removeBtn.getAttribute('data-ex-week'), 10);
    var rmDayIdx = parseInt(removeBtn.getAttribute('data-ex-dayindex'), 10);
    var rmWeekObj = S.lastProgram && S.lastProgram.program.find(function(w){ return w.week_number === rmWeek; });
    var rmDay = rmWeekObj && rmWeekObj.days[rmDayIdx];
    if(rmDay){ removeExerciseFrom(rmDay, rmId); renderProgramWeek(S.lastProgram); }
    return;
  }
  var toggleAddBtn = e.target.closest('[data-toggle-add-ex]');
  if(toggleAddBtn){
    S.addExPanelOpen = !S.addExPanelOpen;
    S.addExQuery = '';
    var dayPanel = document.getElementById('dayAddExPanel');
    if(dayPanel){
      dayPanel.style.display = S.addExPanelOpen ? 'block' : 'none';
      if(S.addExPanelOpen) renderAddExResults('day', '', ' data-ex-week="'+S.programWeek+'" data-ex-dayindex="'+S.programDayIndex+'"');
    }
    return;
  }
  var addPickBtn = e.target.closest('[data-add-ex-pick]');
  if(addPickBtn){
    var apWeek = parseInt(addPickBtn.getAttribute('data-ex-week'), 10);
    var apDayIdx = parseInt(addPickBtn.getAttribute('data-ex-dayindex'), 10);
    var apWeekObj = S.lastProgram && S.lastProgram.program.find(function(w){ return w.week_number === apWeek; });
    var apDay = apWeekObj && apWeekObj.days[apDayIdx];
    if(apDay){
      addExerciseTo(apDay, {
        id: addPickBtn.getAttribute('data-add-ex-pick'),
        name: addPickBtn.getAttribute('data-add-ex-name'),
        category: addPickBtn.getAttribute('data-add-ex-cat'),
        equipment: addPickBtn.getAttribute('data-add-ex-equip'),
        experience_level: addPickBtn.getAttribute('data-add-ex-lvl'),
        difficulty: parseInt(addPickBtn.getAttribute('data-add-ex-diff'), 10) || 1,
      });
      renderProgramWeek(S.lastProgram);
    }
    return;
  }
  var resetBtn = e.target.closest('.btnResetDayOrder');
  if(resetBtn && S.lastProgramOriginal){
    var rsWeek = parseInt(resetBtn.getAttribute('data-reset-week'), 10);
    var rsDayIdx = parseInt(resetBtn.getAttribute('data-reset-dayindex'), 10);
    var liveWeek = S.lastProgram.program.find(function(w){ return w.week_number === rsWeek; });
    var origWeek = S.lastProgramOriginal.program.find(function(w){ return w.week_number === rsWeek; });
    if(liveWeek && origWeek && origWeek.days[rsDayIdx]){
      liveWeek.days[rsDayIdx] = JSON.parse(JSON.stringify(origWeek.days[rsDayIdx]));
      renderProgramWeek(S.lastProgram);
    }
    return;
  }

  var logBtn = e.target.closest('[data-log-set]');
  if(logBtn){
    var exId = logBtn.getAttribute('data-log-set');
    var exName = logBtn.getAttribute('data-log-name');
    var dayKey = logBtn.getAttribute('data-log-daykey');
    var card = logBtn.closest('.exercise');
    var weight = inputToKg(parseFloat(card.querySelector('.logw').value));
    var reps = parseFloat(card.querySelector('.logr').value);
    if(isNaN(weight) || isNaN(reps) || reps <= 0){ return; }
    logProgramSet(dayKey, exId, exName, weight, reps);
    card.querySelector('.logw').value = '';
    card.querySelector('.logr').value = '';
    return;
  }

  var saveBtn = e.target.closest('[data-save-day]');
  if(saveBtn){
    var dk = saveBtn.getAttribute('data-save-day');
    var weekNum = parseInt(saveBtn.getAttribute('data-save-week'), 10);
    var dayIdx = parseInt(saveBtn.getAttribute('data-save-dayindex'), 10);
    var dayLabel = saveBtn.getAttribute('data-save-daylabel');
    var actionsRow = saveBtn.closest('.actions');
    var sorenessSel = actionsRow ? actionsRow.querySelector('.pf-soreness') : null;
    var fatigueSel = actionsRow ? actionsRow.querySelector('.pf-fatigue') : null;
    var postSoreness = sorenessSel && sorenessSel.value ? parseInt(sorenessSel.value, 10) : null;
    var postFatigue = fatigueSel && fatigueSel.value ? parseInt(fatigueSel.value, 10) : null;
    saveProgramDay(dk, weekNum, dayIdx, dayLabel, postSoreness, postFatigue);
  }
});

// Same "input isn't click" split as workout-swap.js's resultBody listener -
// covers the editable sets/reps fields and the add-exercise search box for
// whichever program day is currently on screen.
var dayAddExSearchTimer = null;
document.getElementById('programResult').addEventListener('input', function(e){
  var pFieldEl = e.target.closest('[data-presc-field]');
  if(pFieldEl){
    var pfWeek = parseInt(pFieldEl.getAttribute('data-ex-week'), 10);
    var pfDayIdx = parseInt(pFieldEl.getAttribute('data-ex-dayindex'), 10);
    var pfWeekObj = S.lastProgram && S.lastProgram.program.find(function(w){ return w.week_number === pfWeek; });
    var pfDay = pfWeekObj && pfWeekObj.days[pfDayIdx];
    if(pfDay) setPrescriptionField(pfDay, pFieldEl.getAttribute('data-presc-exid'), pFieldEl.getAttribute('data-presc-field'), pFieldEl.value);
    return;
  }
  if(e.target.id === 'dayAddExSearch'){
    S.addExQuery = e.target.value;
    clearTimeout(dayAddExSearchTimer);
    var q = S.addExQuery;
    dayAddExSearchTimer = setTimeout(function(){
      renderAddExResults('day', q, ' data-ex-week="'+S.programWeek+'" data-ex-dayindex="'+S.programDayIndex+'"');
    }, 250);
  }
});

function logProgramSet(dayKey, exId, exName, weight, reps){
  var score = computeScore(weight, reps);
  var isPR = score > bestPriorScore(exId) && score > 0;
  if(!S.programSessionLog[dayKey]) S.programSessionLog[dayKey] = {};
  if(!S.programSessionLog[dayKey][exId]) S.programSessionLog[dayKey][exId] = {name: exName, sets:[]};
  S.programSessionLog[dayKey][exId].sets.push({weight:weight, reps:reps, isPR:isPR});
  var week = S.lastProgram && S.lastProgram.program.find(function(w){ return w.week_number === S.programWeek; });
  var day = week && week.days[S.programDayIndex];
  var ex = day && (day.prescribed_workout || []).find(function(e){ return e.id === exId; });
  var isDb = ex && ex.equipment === 'Dumbbell';
  var container = document.querySelector('.logged-sets[data-logged-for="'+cssEsc(dayKey+'::'+exId)+'"]');
  if(container){
    var row = document.createElement('div');
    row.className = 'logged-set';
    row.innerHTML = '<span>'+fmtWeight(weight)+(isDb ? ' each hand' : '')+' × '+reps+'</span>' + (isPR ? '<span class="pr">PR</span>' : '');
    container.appendChild(row);
  }
  if(isPR){
    checkOneRMUpdate(ex, weight, reps, S.lastProgram && S.lastProgram._usedBiometrics);
  }
}

function saveProgramDay(dayKey, weekNumber, dayIndex, dayLabel, postSoreness, postFatigue){
  if(!S.lastProgram) return;
  var week = S.lastProgram.program.find(function(w){ return w.week_number === weekNumber; });
  if(!week) return;
  var day = week.days[dayIndex];
  if(!day) return;

  var dayLog = S.programSessionLog[dayKey] || {};
  var log = Object.keys(dayLog).map(function(exId){
    return {exId:exId, name:dayLog[exId].name, sets:dayLog[exId].sets};
  });

  var record = {
    id: S.programSavedDays[dayKey] || Date.now(),
    date: new Date().toISOString(),
    sport: S.lastProgram.sport,
    experience_level: S.lastProgram.experience_level,
    deload_mode: !!day.deload_mode,
    prescribed_count: day.exercise_count,
    readiness_used: parseInt((document.getElementById('pgReadiness')||{}).value, 10) || null,
    program_label: S.lastProgram.split.name + ' — Week ' + weekNumber + ' · ' + dayLabel,
    exercises: day.prescribed_workout.map(function(ex){
      return {id:ex.id, name:ex.name, category:ex.category, prescription: renderPrescription(ex.prescription)};
    }),
    log: log
  };

  var hist = loadHistory();
  var existingIdx = hist.findIndex(function(s){ return s.id === record.id; });
  if(existingIdx >= 0){ hist[existingIdx] = record; } else { hist.push(record); }
  saveHistory(hist);
  S.programSavedDays[dayKey] = record.id;
  syncSessionToBackend(record, postSoreness, postFatigue);

  autoregulateNextWeek(day, weekNumber, dayIndex, dayLabel, dayLog, postSoreness, postFatigue);
  checkSignalDeload(weekNumber);

  renderProgramWeek(S.lastProgram); // repaint the save button as "Saved"
  updateHeroForReturningUser();
  show('screen-history');
}

