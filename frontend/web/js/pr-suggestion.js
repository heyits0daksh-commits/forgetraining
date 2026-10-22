'use strict';

// ============================================================
// PR -> TESTED 1RM SUGGESTION
// A PR (see computeScore/bestPriorScore above) already means "the best
// Epley-estimated 1RM logged for this exercise, ever" - this reuses that
// same estimate to notice when it has actually overtaken the tested max
// biometrics is using to anchor working weights (load_prescription.py's
// `anchor_lift`/`weight_confidence: "direct"` - see that file's docstring
// for the Squat/Hinge/Push -> squat/deadlift/bench mapping). Only fires on
// a DIRECT anchor, never an "estimated" proxy pull (a pull-up PR saying
// nothing trustworthy about a person's real deadlift max).
// Never overwrites biometrics silently - same "suggest, don't auto-apply"
// convention as the readiness suggestion and level_check advisory: this
// shows a dismissable banner with an explicit Update button, and only
// updates the wizard input fields (both single-session and program, so
// either flow benefits next time) once the person clicks it.
// ============================================================

var ANCHOR_FIELD_BY_LABEL = {"Bench Press":"bench_press_1rm", "Squat":"squat_1rm", "Deadlift":"deadlift_1rm"};
var ANCHOR_INPUT_IDS = {
  bench_press_1rm: ['bioBench', 'pgBioBench'],
  squat_1rm: ['bioSquat', 'pgBioSquat'],
  deadlift_1rm: ['bioDeadlift', 'pgBioDeadlift']
};
function kgToInputUnit(kg){
  var v = S.unit === 'lb' ? kgToLb(kg) : kg;
  return Math.round(v * 10) / 10;
}
function checkOneRMUpdate(ex, weight, reps, biometrics){
  if(!ex || !ex.prescription) return;
  var p = ex.prescription;
  if(p.type !== 'strength' || p.weight_confidence !== 'direct' || !p.anchor_lift) return;
  var field = ANCHOR_FIELD_BY_LABEL[p.anchor_lift];
  if(!field) return;
  var estKg = computeScore(weight, reps); // same Epley estimate PR detection already uses
  var currentMax = (biometrics && biometrics[field]) || 0;
  var roundedKg = Math.round(estKg / 2.5) * 2.5; // nearest plate-loadable increment, matches load_prescription.py's rounding
  if(roundedKg <= currentMax) return; // not actually past the tested max - just a PR within the current rep range
  showPRUpdateBanner(p.anchor_lift, field, roundedKg, currentMax);
}
function showPRUpdateBanner(label, field, newKg, oldKg){
  var wrap = document.getElementById('toastWrap');
  if(!wrap) return;
  var el = document.createElement('div');
  el.className = 'toast pr-banner';
  el.innerHTML = '🏆 New estimated <b>'+esc(label)+' 1RM</b>: '+fmtWeight(newKg)+
    (oldKg ? ' (was '+fmtWeight(oldKg)+')' : '') + '.' +
    ' <button type="button" class="btn small" data-pr-update-field="'+esc(field)+'" data-pr-update-kg="'+newKg+'" data-pr-update-label="'+esc(label)+'">Update 1RM</button>' +
    ' <button type="button" class="btn small secondary" data-pr-dismiss="1">Dismiss</button>';
  wrap.appendChild(el);
  requestAnimationFrame(function(){ el.classList.add('show'); });
  el.addEventListener('click', function(e){
    var updateBtn = e.target.closest('[data-pr-update-field]');
    if(updateBtn){
      var f = updateBtn.getAttribute('data-pr-update-field');
      var kg = parseFloat(updateBtn.getAttribute('data-pr-update-kg'));
      var lbl = updateBtn.getAttribute('data-pr-update-label');
      (ANCHOR_INPUT_IDS[f] || []).forEach(function(id){
        var input = document.getElementById(id);
        if(input) input.value = kgToInputUnit(kg);
      });
      dismissToastEl(el);
      showToast('Updated your ' + lbl + ' 1RM to ' + fmtWeight(kg) + ' — used from your next session/program.');
      return;
    }
    if(e.target.closest('[data-pr-dismiss]')){ dismissToastEl(el); }
  });
}
function dismissToastEl(el){
  el.classList.remove('show');
  setTimeout(function(){ el.remove(); }, 250);
}
function cssEsc(s){ return String(s).replace(/"/g,'\\"'); }

// Lightweight confirmation toast — used to make the log→sync→personalize
// loop visible instead of silent (see syncSessionToBackend), so the person
// knows whether their set actually reached the server (and therefore
// counts toward future personalization) or only saved locally.
function showToast(message, type){
  var wrap = document.getElementById('toastWrap');
  if(!wrap) return;
  var el = document.createElement('div');
  el.className = 'toast' + (type === 'error' ? ' error' : '');
  el.textContent = message;
  wrap.appendChild(el);
  requestAnimationFrame(function(){ el.classList.add('show'); });
  setTimeout(function(){
    el.classList.remove('show');
    setTimeout(function(){ el.remove(); }, 250);
  }, type === 'error' ? 7500 : 3200);
}

document.getElementById('btnDiscard').addEventListener('click', function(){
  // Discard used to wipe a session with zero warning — one misclick during
  // a workout threw away every set already logged in this session, with no
  // way to get it back (nothing was synced yet). Only worth confirming once
  // there's actually something to lose; an untouched freshly-generated
  // session can still discard instantly.
  var hasLoggedSets = Object.keys(S.sessionLog || {}).some(function(exId){
    return (S.sessionLog[exId].sets || []).length > 0;
  });
  if(!hasLoggedSets){ show('screen-hero'); return; }
  showConfirm('You have logged sets in this session that haven\'t been saved yet. Discard them?', {title:'Discard this session?'}).then(function(ok){
    if(ok) show('screen-hero');
  });
});
document.getElementById('btnSaveSession').addEventListener('click', function(){
  if(!S.lastResult) return;
  var log = Object.keys(S.sessionLog).map(function(exId){
    return {exId:exId, name:S.sessionLog[exId].name, sets:S.sessionLog[exId].sets};
  });
  var record = {
    id: Date.now(),
    date: new Date().toISOString(),
    sport: S.lastResult.sport,
    experience_level: S.lastResult.experience_level,
    deload_mode: !!S.lastResult.deload_mode,
    prescribed_count: S.lastResult.session_summary.total_prescribed,
    readiness_used: S.readiness,
    exercises: S.lastResult.prescribed_workout.map(function(ex){
      return {id:ex.id, name:ex.name, category:ex.category, prescription: renderPrescription(ex.prescription)};
    }),
    log: log
  };
  var hist = loadHistory();
  hist.push(record);
  saveHistory(hist);
  var postSorenessSel = document.getElementById('postSorenessInput');
  var postFatigueSel = document.getElementById('postFatigueInput');
  var postSoreness = postSorenessSel && postSorenessSel.value ? parseInt(postSorenessSel.value, 10) : null;
  var postFatigue = postFatigueSel && postFatigueSel.value ? parseInt(postFatigueSel.value, 10) : null;
  syncSessionToBackend(record, postSoreness, postFatigue);
  updateHeroForReturningUser();
  show('screen-history');
});

