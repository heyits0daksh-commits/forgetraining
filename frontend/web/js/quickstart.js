'use strict';

// ============================================================
// HOME QUICK START - three taps (goal, days/week, equipment) -> the best
// matching ready-made FORGE plans from the S&C template libraries, each
// with a one-tap "Start this plan". Builds through the same
// POST /sc-templates/{id}/build + adaptTemplateFidelityToProgramShape +
// renderProgram pipeline the wizard's template path uses, so equipment/
// injury checks, "FORGE checked every exercise" note, Save Program and
// session logging all behave identically.
// ============================================================

var QS_KEY = 'forge_quickstart_v1';
var QS_GOAL_LIBRARY = { strength: 'powerlifting', muscle: 'natural_bodybuilding', both: 'strength_hypertrophy' };
var QS_LEVELS = ['Novice', 'Beginner', 'Intermediate', 'Advanced', 'Elite'];
var QS_state = { goal: null, days: null, equip: null };

function qsLoad(){
  try{ var v = JSON.parse(localStorage.getItem(QS_KEY)); if(v) QS_state = { goal: v.goal || null, days: v.days || null, equip: v.equip || null }; }
  catch(e){}
}
function qsSave(){ try{ localStorage.setItem(QS_KEY, JSON.stringify(QS_state)); }catch(e){} }

// Template levels are Novice..Elite. Fall back to Beginner when we have no
// (or an unrecognised) saved experience level.
function qsLevel(){
  var p = (typeof loadAthleteProfile === 'function') ? loadAthleteProfile() : null;
  var exp = p && p.experience ? String(p.experience) : '';
  for(var i = 0; i < QS_LEVELS.length; i++){
    if(exp.toLowerCase().indexOf(QS_LEVELS[i].toLowerCase()) === 0) return QS_LEVELS[i];
  }
  return 'Beginner';
}

// Same preset -> equipment-group mapping as applyEquipmentPreset
// (custom-mode-picker.js), but returns a plain array.
function qsEquipmentList(){
  var groups = (typeof EQ_PRESET_GROUPS !== 'undefined' && EQ_PRESET_GROUPS[QS_state.equip]) || null;
  var out = ['Bodyweight'];
  if(groups && S.equipmentCatalog && S.equipmentCatalog.length){
    out = S.equipmentCatalog.filter(function(r){ return groups.indexOf(r.group) !== -1; })
      .map(function(r){ return r.equipment; });
    if(!out.length) out = ['Bodyweight'];
  }
  return out;
}

function qsSyncButtons(){
  [['qsGoal','data-qs-goal','goal'],['qsDays','data-qs-days','days'],['qsEquip','data-qs-equip','equip']].forEach(function(r){
    var row = document.getElementById(r[0]);
    if(!row) return;
    row.querySelectorAll('.chip-btn').forEach(function(b){
      b.classList.toggle('active', String(QS_state[r[2]]) === b.getAttribute(r[1]));
    });
  });
}

function qsRenderResults(){
  var el = document.getElementById('qsResults');
  if(!el) return;
  if(QS_state.goal === 'sport'){
    el.innerHTML = '<div class="qs-note">Sport plans are matched to your discipline — pick yours below.</div>';
    var grid = document.getElementById('homeSportsSection');
    if(grid && grid.scrollIntoView) grid.scrollIntoView({behavior: smoothBehavior(), block: 'start'});
    return;
  }
  if(!QS_state.goal || !QS_state.days || !QS_state.equip){ el.innerHTML = ''; return; }

  var lib = QS_GOAL_LIBRARY[QS_state.goal];
  var level = qsLevel();
  el.innerHTML = '<div class="micro">Finding your plans…</div>';
  var token = ++qsRenderResults._t;
  var q = new URLSearchParams({ library: lib, level: level });
  fetch(API_BASE + '/api/v1/sc-templates?' + q.toString())
    .then(function(r){ return r.ok ? r.json() : { templates: [] }; })
    .then(function(data){
      if(token !== qsRenderResults._t) return; // a newer tap superseded this one
      var want = QS_state.days;
      var list = (data.templates || []).map(function(t){
        // 5+ means "five or more": exact for 5/6, distance otherwise.
        var diff = want >= 5 ? (t.days_per_week >= 5 ? 0 : 5 - t.days_per_week) : Math.abs(t.days_per_week - want);
        return { t: t, diff: diff };
      });
      list.sort(function(a, b){ return a.diff - b.diff; });
      list = list.slice(0, 3);
      if(!list.length){
        el.innerHTML = '<div class="qs-note">No ready-made plan found for that combination — use the full builder instead.</div>' + qsCustomizeBtn();
        qsWireCustomize(el);
        return;
      }
      var anyInexact = list.some(function(x){ return x.diff > 0; });
      el.innerHTML =
        (anyInexact ? '<div class="qs-note">We don\'t have a plan for exactly that many days — these are the closest.</div>' : '') +
        list.map(function(x){
          var t = x.t;
          return '<div class="qs-plan"><h4>'+esc(t.name)+'</h4>' +
            '<span class="micro">'+esc(t.level)+' · '+esc(t.days_per_week)+' days/week · '+esc(t.duration_weeks)+' weeks</span>' +
            '<button type="button" class="btn" data-qs-start="'+esc(t.global_id)+'">Start this plan →</button></div>';
        }).join('') +
        (QS_state.equip !== 'full' ? '<div class="qs-note">These plans are written for a gym. FORGE swaps in exercises you can do with your equipment and tells you what changed.</div>' : '') +
        qsCustomizeBtn();
      el.querySelectorAll('[data-qs-start]').forEach(function(b){
        b.addEventListener('click', function(){ qsStartPlan(b, b.getAttribute('data-qs-start')); });
      });
      qsWireCustomize(el);
    })
    .catch(function(){
      if(token !== qsRenderResults._t) return;
      el.innerHTML = '<div class="callout danger">Couldn\'t load plans right now. Check your connection and try again.</div>';
    });
}
qsRenderResults._t = 0;

function qsCustomizeBtn(){ return '<button type="button" class="qs-more" id="qsCustomize">Customize everything instead →</button>'; }
function qsWireCustomize(el){
  var b = el.querySelector('#qsCustomize');
  if(b) b.addEventListener('click', function(){
    if(typeof hasAthleteProfile === 'function' && hasAthleteProfile()){ startNewProgramFromProfile(); }
    else { markWarningSeen(); S.wizardEditMode = false; show('screen-setup'); goToStep(1); }
  });
}

function qsBiometrics(){
  var p = (typeof loadAthleteProfile === 'function') ? loadAthleteProfile() : null;
  var b = (p && p.biometrics) || {};
  return {
    height_cm: b.height_cm || 175,
    weight_kg: b.weight_kg || 75,
    bench_press_1rm: b.bench_press_1rm_kg || 0,
    squat_1rm: b.squat_1rm_kg || 0,
    deadlift_1rm: b.deadlift_1rm_kg || 0,
    pullups_max_reps: b.pullups_max_reps || 0,
    pushups_max_reps: b.pushups_max_reps || 0,
    sex: b.sex || null
  };
}

function qsStartPlan(btn, globalId){
  var p = (typeof loadAthleteProfile === 'function') ? loadAthleteProfile() : null;
  var payload = {
    equipment_available: qsEquipmentList(),
    injuries: (p && p.injuries) || [],
    injury_stages: (p && p.injuryStages) || null,
    injury_sides: (p && p.injurySides) || null,
    biometrics: qsBiometrics()
  };
  var label = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Building your plan…';
  fetch(API_BASE + '/api/v1/sc-templates/' + encodeURIComponent(globalId) + '/build', {
    method: 'POST', headers: jsonAuthHeaders(), body: JSON.stringify(payload)
  })
    .then(function(r){
      return r.json().then(function(data){
        if(!r.ok) throw new Error(extractErrorMessage(data, 'Request failed'));
        return data;
      });
    })
    .then(function(data){
      var adapted = adaptTemplateFidelityToProgramShape(data);
      adapted._usedInjuries = payload.injuries;
      adapted._usedInjuryStages = payload.injury_stages || {};
      adapted._usedInjurySides = payload.injury_sides || {};
      adapted._usedEquipment = payload.equipment_available;
      adapted._usedBiometrics = payload.biometrics;
      // S.lastProgram must be set before show('screen-program') so the
      // screen's first-visit check doesn't reset to wizard step 1.
      S.lastProgram = adapted;
      S.lastProgramOriginal = JSON.parse(JSON.stringify(adapted));
      S.pgSavedProgramId = null;
      S.programWeek = 1;
      S.programDayIndex = 0;
      S.programWhyOpen = {};
      S.programSessionLog = {};
      S.programSavedDays = {};
      show('screen-program');
      setProgramResultMode(true);
      renderProgram(adapted);
    })
    .catch(function(err){
      btn.disabled = false;
      btn.textContent = label;
      var el = document.getElementById('qsResults');
      if(el) el.insertAdjacentHTML('afterbegin',
        '<div class="callout danger"><b>Couldn\'t build this plan.</b> '+esc(err.message || String(err))+'</div>');
    });
}

function wireQuickStart(){
  var root = document.getElementById('homeQuickStart');
  if(!root) return;
  qsLoad();
  qsSyncButtons();
  root.addEventListener('click', function(e){
    var g = e.target.closest('[data-qs-goal]');
    var d = e.target.closest('[data-qs-days]');
    var q = e.target.closest('[data-qs-equip]');
    if(g) QS_state.goal = g.getAttribute('data-qs-goal');
    else if(d) QS_state.days = parseInt(d.getAttribute('data-qs-days'), 10);
    else if(q) QS_state.equip = q.getAttribute('data-qs-equip');
    else return;
    qsSave(); qsSyncButtons(); qsRenderResults();
  });
  qsRenderResults();
}
wireQuickStart();
