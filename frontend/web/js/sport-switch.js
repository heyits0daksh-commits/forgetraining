'use strict';

// ============================================================
// SPORT SWITCH - picking a sport throws away whatever workout/program was
// on screen and builds a fresh one for THAT sport, straight away.
//
// Before this, tapping a discipline tile only set S.sport and opened the
// Program screen. If a program for the previous sport already existed in
// memory (S.lastProgram), that old program was shown again - same exercises,
// wrong sport. Nothing was rebuilt.
//
// Picking a sport builds BOTH today's session (generate-workout) and the
// multi-week plan behind it, and lands on the session.
//
// What "pro" means here (see rankSportPlans): the plan is a coach-written
// template for exactly this sport (not the generic cross-sport pool), at the
// athlete's own level, closest to their training days, and the longest
// periodised block available - then run through the same template-fidelity
// build (POST /sc-templates/{id}/build) so every slot is still checked
// against this athlete's equipment and injuries.
// ============================================================

var SPORT_SWITCH_DEFAULT_DAYS = 4;
var SPORT_SWITCH_LEVELS = ['Novice', 'Beginner', 'Intermediate', 'Advanced', 'Elite'];
var _sportSwitchToken = 0;

// ---------- wipe ----------
// Clears the on-screen workout/program and every piece of state derived from
// it. Does NOT touch saved programs, session history, or the athlete's
// profile - those belong to the person, not to the current draft.
function clearCurrentWorkout(){
  S.lastResult = null;
  S.lastResultOriginal = null;
  S.sessionLog = {};
  S.resultWhyOpen = {};

  S.lastProgram = null;
  S.lastProgramOriginal = null;
  S.pgSavedProgramId = null;
  S.pgSelectedTemplate = null;
  S.pgSelectedTemplateName = null;
  S.programWeek = 1;
  S.programDayIndex = 0;
  S.programWhyOpen = {};
  S.programSessionLog = {};
  S.programSavedDays = {};

  // Custom-mode leftovers from the old sport's exercise picks.
  if(S.selectedExercises && S.selectedExercises.clear) S.selectedExercises.clear();
  S.customGroups = {};
  S.customGroupOrder = [];
  S.customWarmup = [];
  S.customEditingWorkoutId = null;
  S.customSafetyWarnings = null;

  var pr = document.getElementById('programResult');
  if(pr) pr.innerHTML = '';
  var rr = document.getElementById('results');
  if(rr && rr.innerHTML) rr.innerHTML = '';
}

// Would clearing lose anything the person hasn't saved?
function currentWorkoutHasUnsavedWork(){
  var logged = Object.keys(S.sessionLog || {}).some(function(id){
    return ((S.sessionLog[id] || {}).sets || []).length > 0;
  }) || Object.keys(S.programSessionLog || {}).length > 0;
  var unsavedProgram = !!S.lastProgram && !S.pgSavedProgramId;
  return logged || unsavedProgram;
}

// ---------- pick the best plan ----------
function sportSwitchProfile(){
  return (typeof loadAthleteProfile === 'function') ? loadAthleteProfile() : null;
}

function sportSwitchLevel(){
  var p = sportSwitchProfile();
  var exp = String((p && p.experience) || S.experience || 'Intermediate');
  for(var i = 0; i < SPORT_SWITCH_LEVELS.length; i++){
    if(exp.toLowerCase().indexOf(SPORT_SWITCH_LEVELS[i].toLowerCase()) === 0) return SPORT_SWITCH_LEVELS[i];
  }
  return 'Intermediate';
}

function sportSwitchDays(){
  if(typeof QS_state !== 'undefined' && QS_state && QS_state.days) return QS_state.days;
  return SPORT_SWITCH_DEFAULT_DAYS;
}

// Higher score = better. Order of importance: exact sport (not generic pool),
// exact level, closest days/week, longest block.
function rankSportPlans(list, sport, level, days){
  var li = SPORT_SWITCH_LEVELS.indexOf(level);
  return list.map(function(t){
    var score = 0;
    if(t.sport === sport) score += 1000;
    var ti = SPORT_SWITCH_LEVELS.indexOf(t.level);
    score -= Math.abs((ti < 0 ? li : ti) - li) * 200;
    var d = t.days_per_week || days;
    score -= (days >= 5 ? (d >= 5 ? 0 : 5 - d) : Math.abs(d - days)) * 40;
    score += Math.min(t.duration_weeks || 0, 16);
    return { t: t, score: score };
  }).sort(function(a, b){ return b.score - a.score; });
}

function sportSwitchEquipment(){
  var p = sportSwitchProfile();
  if(p && p.equipment && p.equipment.length) return p.equipment.slice();
  if(S.equipment && S.equipment.size) return Array.from(S.equipment);
  // Nothing saved yet: assume a normal gym. The template build swaps out any
  // slot that fails a stricter equipment list later, so this errs toward the
  // coach's real programming rather than a bodyweight-only watered-down plan.
  if(S.equipmentCatalog && S.equipmentCatalog.length){
    return S.equipmentCatalog.map(function(r){ return r.equipment; });
  }
  return ['Bodyweight'];
}

function showSportSwitchLoading(sport){
  var lt = document.getElementById('loadingText');
  if(lt) lt.textContent = 'Building your ' + sport + ' session and plan…';
  var cb = document.getElementById('btnCancelLoading');
  if(cb && cb.parentNode) cb.parentNode.style.display = 'none';
  show('screen-loading');
}

function applyBuiltProgram(adapted, payload, opts){
  opts = opts || {};
  adapted._usedInjuries = payload.injuries || [];
  adapted._usedInjuryStages = payload.injury_stages || {};
  adapted._usedInjurySides = payload.injury_sides || {};
  adapted._usedEquipment = payload.equipment_available || [];
  adapted._usedBiometrics = payload.biometrics;
  adapted.sport = adapted.sport || S.sport;
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
  if(!opts.background) show('screen-program');
}

function sportSwitchFail(sport, msg){
  S.lastProgram = null;
  S.lastResult = null;
  show('screen-hero');
  showErrorModal(
    msg || ('We couldn\'t build a ' + sport + ' plan right now. Check your connection and tap the sport again.'),
    { title: 'Couldn\'t build your plan' }
  );
}

// Last resort for a sport with no template coverage: the live engine,
// at the athlete's level, 4 days x 6 weeks.
function sportSwitchEngineFallback(sport, payload, token, background){
  var body = {
    mode: 'preset',
    sport: sport,
    experience_level: sportSwitchLevel(),
    equipment_available: payload.equipment_available,
    injuries: payload.injuries,
    injury_stages: payload.injury_stages,
    injury_sides: payload.injury_sides,
    days_per_week: sportSwitchDays(),
    weeks: 6,
    session_duration_minutes: S.sessionDuration || 60,
    readiness: 85,
    conditioning_emphasis: S.conditioningEmphasis,
    biometrics: payload.biometrics
  };
  return fetch(API_BASE + '/api/v1/generate-program', {
    method: 'POST', headers: jsonAuthHeaders(), body: JSON.stringify(body)
  })
    .then(function(r){
      return r.json().then(function(data){
        if(!r.ok) throw new Error(extractErrorMessage(data, 'Request failed'));
        return data;
      });
    })
    .then(function(data){
      if(token !== _sportSwitchToken) return;
      data._usedReadiness = body.readiness;
      data._usedDuration = body.session_duration_minutes;
      data._usedConditioningEmphasis = body.conditioning_emphasis;
      applyBuiltProgram(data, body, { background: background });
    });
}

// Today's session: one full workout for this sport, same endpoint and
// result handling as the wizard's Generate button (generate.js) but fed from
// the saved profile instead of the wizard's form fields.
function sportSwitchBuildSession(sport, payload, token){
  var body = {
    mode: 'preset',
    sport: sport,
    experience_level: sportSwitchLevel(),
    equipment_available: payload.equipment_available,
    readiness: S.readiness || 85,
    conditioning_emphasis: S.conditioningEmphasis,
    session_duration_minutes: S.sessionDuration || 60,
    training_emphasis: S.emphasis,
    injuries: payload.injuries,
    injury_stages: payload.injury_stages,
    injury_sides: payload.injury_sides,
    variety_seed: Math.floor(Math.random() * 1000000),
    biometrics: payload.biometrics
  };
  return fetch(API_BASE + '/api/v1/generate-workout', {
    method: 'POST', headers: jsonAuthHeaders(), body: JSON.stringify(body)
  })
    .then(function(r){
      return r.json().then(function(data){
        if(!r.ok) throw new Error(extractErrorMessage(data, 'Request failed'));
        return data;
      });
    })
    .then(function(data){
      if(token !== _sportSwitchToken) return false;
      data._usedInjuries = body.injuries || [];
      data._usedInjuryStages = body.injury_stages || {};
      data._usedInjurySides = body.injury_sides || {};
      data._usedEquipment = body.equipment_available || [];
      data._usedBiometrics = body.biometrics;
      S.sessionLog = {};
      S.lastResult = data;
      S.lastResultOriginal = JSON.parse(JSON.stringify(data));
      S.quickStart = false;
      renderResults(data);
      show('screen-results');
      return true;
    });
}

// Multi-week plan behind the session: best coach-written template for the
// sport, else the live engine.
function sportSwitchBuildProgram(sport, payload, token, background){
  var level = sportSwitchLevel();
  var days = sportSwitchDays();

  // Level filter first (exact match); if the sport has no template at that
  // exact level, retry without it and let the ranker pick the nearest level.
  function fetchList(withLevel){
    var q = new URLSearchParams({ sport: sport });
    if(withLevel) q.set('level', level);
    return fetch(API_BASE + '/api/v1/sc-templates?' + q.toString())
      .then(function(r){ return r.ok ? r.json() : { templates: [] }; })
      .then(function(d){ return d.templates || []; });
  }

  return fetchList(true)
    .then(function(list){ return list.length ? list : fetchList(false); })
    .then(function(list){
      if(token !== _sportSwitchToken) return false;
      if(!list.length){
        return sportSwitchEngineFallback(sport, payload, token, background).then(function(){ return true; });
      }
      var best = rankSportPlans(list, sport, level, days)[0].t;
      return fetch(API_BASE + '/api/v1/sc-templates/' + encodeURIComponent(best.global_id) + '/build', {
        method: 'POST', headers: jsonAuthHeaders(), body: JSON.stringify(payload)
      })
        .then(function(r){
          return r.json().then(function(data){
            if(!r.ok) throw new Error(extractErrorMessage(data, 'Request failed'));
            return data;
          });
        })
        .then(function(data){
          if(token !== _sportSwitchToken) return false;
          var adapted = adaptTemplateFidelityToProgramShape(data);
          adapted.sport = sport;
          applyBuiltProgram(adapted, payload, { background: background });
          return true;
        });
    });
}

// Builds today's session AND the plan behind it, in parallel. The person
// lands on the session (the thing they train today); the plan is ready in
// the Program tab. If only one of the two builds, they land on that one.
function buildProPlanForSport(sport){
  var token = ++_sportSwitchToken;
  var p = sportSwitchProfile();
  var payload = {
    equipment_available: sportSwitchEquipment(),
    injuries: (p && p.injuries) || [],
    injury_stages: (p && p.injuryStages) || null,
    injury_sides: (p && p.injurySides) || null,
    biometrics: (typeof qsBiometrics === 'function') ? qsBiometrics() : null
  };

  showSportSwitchLoading(sport);

  var sessionDone = false, programDone = false;
  var sessionErr = null, programErr = null;

  var sessionP = sportSwitchBuildSession(sport, payload, token)
    .then(function(ok){ sessionDone = !!ok; })
    .catch(function(e){ sessionErr = e; });
  // background=true: the program must not pull the person off the session.
  // If the session fails, we show the program ourselves below.
  var programP = sportSwitchBuildProgram(sport, payload, token, true)
    .then(function(ok){ programDone = !!ok; })
    .catch(function(e){ programErr = e; });

  Promise.all([sessionP, programP]).then(function(){
    if(token !== _sportSwitchToken) return;
    if(sessionDone) return;                       // already on the session
    if(programDone){ show('screen-program'); return; }
    var e = sessionErr || programErr;
    sportSwitchFail(sport, e && e.message ? 'We couldn\'t build a ' + sport + ' plan: ' + e.message : null);
  });
}

// ---------- entry point ----------
// Called when a sport is picked on Home. Same sport as the program already on
// screen -> just open it (nothing to rebuild). A different sport -> warn only
// if something unsaved would be lost, wipe, rebuild.
function switchSport(sport){
  var sameSport = (S.lastResult || S.lastProgram) && S.sport === sport &&
    ((S.lastResult && S.lastResult.sport) || (S.lastProgram && S.lastProgram.sport) || S.sport) === sport;
  if(sameSport){
    show(S.lastResult ? 'screen-results' : 'screen-program');
    return;
  }
  var proceed = function(){
    cancelSportSwitchInFlight();
    if(typeof cancelGenerate === 'function') cancelGenerate();
    clearCurrentWorkout();
    S.sport = sport;
    S.emphasis = emphasisForSport(sport);
    S.trainScope = 'program';
    S.mode = 'preset';
    // A previous Custom Program choice must not leak into this sport's builder.
    if(S.pgMode === 'custom'){
      var ct = document.getElementById('pgCustomModeToggle');
      if(ct){ ct.checked = false; ct.dispatchEvent(new Event('change')); } else { S.pgMode = 'preset'; }
    }
    applyTheme(sport);
    document.querySelectorAll('#disciplineGrid .choice').forEach(function(c){
      c.classList.toggle('selected', c.getAttribute('data-sport') === sport);
    });
    if(typeof saveAthleteProfile === 'function') saveAthleteProfile();
    if(typeof populateProgramForm === 'function') populateProgramForm();
    var pgSportSel = document.getElementById('pgSport');
    if(pgSportSel) pgSportSel.value = sport;
    buildProPlanForSport(sport);
  };
  if(currentWorkoutHasUnsavedWork() && typeof showConfirm === 'function'){
    showConfirm(
      'Switching to ' + sport + ' replaces your current ' + (S.sport || '') +
      ' workout with a brand-new ' + sport + ' plan. Anything you haven\'t saved will be lost.',
      { title: 'Switch to ' + sport + '?', confirmLabel: 'Switch & rebuild', danger: false }
    ).then(function(ok){ if(ok) proceed(); });
  } else {
    proceed();
  }
}

function cancelSportSwitchInFlight(){ _sportSwitchToken++; }

// Replaces home.js's jumpToDiscipline (loaded earlier; a later function
// declaration of the same name wins) so every Home tile tap rebuilds.
function jumpToDiscipline(sport){ switchSport(sport); }

// Wizard path: tapping a different sport tile inside the setup wizard must
// also drop the stale result/program of the old sport. No auto-build here -
// the wizard's own Generate step builds the new one from the full answers.
function onWizardSportChanged(newSport, previousSport){
  if(previousSport && previousSport !== newSport){
    cancelSportSwitchInFlight();
    clearCurrentWorkout();
  }
}

// Custom -> Custom PROGRAM. The setup wizard's Custom option used to run the
// single-session custom path (generate() with mode:'custom') and so produced
// one session. A custom program is the Program Builder with its own
// "Custom Program" toggle on (your own days + exercises), so Custom now
// opens that instead: old workout cleared, builder reset to step 1, toggle on.
function routeCustomToProgram(){
  cancelSportSwitchInFlight();
  if(typeof cancelGenerate === 'function') cancelGenerate();
  clearCurrentWorkout();
  S.trainScope = 'program';
  if(typeof populateProgramForm === 'function') populateProgramForm();
  // "Custom" isn't a real discipline in the engine - the builder's hidden
  // sport select only holds real ones, so leave it on its default.
  var pgSportSel = document.getElementById('pgSport');
  if(pgSportSel && S.sport && S.sport !== 'Custom') pgSportSel.value = S.sport;
  var toggle = document.getElementById('pgCustomModeToggle');
  if(toggle){
    toggle.checked = true;
    toggle.dispatchEvent(new Event('change'));   // runs the builder's own handler
  } else {
    S.pgMode = 'custom';
  }
  if(typeof setProgramResultMode === 'function') setProgramResultMode(false);
  show('screen-program');                         // lands on step 1 (no program yet)
}
