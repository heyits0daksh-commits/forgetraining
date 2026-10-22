'use strict';

// ============================================================
// BOOT
// ============================================================

// capacitor-native.js is empty in the web build, so this was undefined and threw after
// every successful boot. No-op unless the native shell defines it.
if(typeof window.hideNativeSplash !== 'function'){ window.hideNativeSplash = function(){}; }

function setStatus(online){
  var pill = document.getElementById('statusPill');
  var text = document.getElementById('statusText');
  pill.className = 'status ' + (online ? 'online' : 'offline');
  text.textContent = online ? 'Online' : 'Offline';
}

var _bootAttempt = 0;
var BOOT_MAX_ATTEMPTS = 4; // free hosts can take ~30-60s to wake from idle
function boot(isRetry){
  if(isRetry !== true) _bootAttempt = 0;
  document.getElementById('apiBaseDisplay').textContent = API_BASE;
  Promise.all([
    fetch(API_BASE + '/api/v1/metadata').then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); }),
    fetch(API_BASE + '/api/v1/splits').then(function(r){ return r.ok ? r.json() : {splits:[]}; }).catch(function(){ return {splits:[]}; }),
    fetch(API_BASE + '/api/v1/goals').then(function(r){ return r.ok ? r.json() : {goals:[]}; }).catch(function(){ return {goals:[]}; }),
    fetch(API_BASE + '/api/v1/equipment').then(function(r){ return r.ok ? r.json() : {equipment:[]}; }).catch(function(){ return {equipment:[]}; }),
    fetch(API_BASE + '/api/v1/training-phases').then(function(r){ return r.ok ? r.json() : {training_phases:[]}; }).catch(function(){ return {training_phases:[]}; }),
    // Per-sport extra question(s) (Rugby's Positional Emphasis, MMA's
    // Fight-Style Emphasis, Powerlifting's Periodization Style, ...) and
    // the list of sports with any SC template coverage at all - both
    // fetched once here rather than per-sport, so the Program wizard's
    // "Sport Focus" step (getProgramWizardStepIds/renderPgSportFocusStep
    // in program-wizard-steps.js) can decide synchronously whether to
    // show itself for whatever sport is currently selected. Falls back to
    // "no sport has an extra question" against an older backend without
    // this endpoint, same graceful-degradation pattern trainingPhases uses.
    fetch(API_BASE + '/api/v1/sc-templates/sport-questions').then(function(r){ return r.ok ? r.json() : {by_sport:{}}; }).catch(function(){ return {by_sport:{}}; }),
    fetch(API_BASE + '/api/v1/sc-templates').then(function(r){ return r.ok ? r.json() : {sports_covered:[]}; }).catch(function(){ return {sports_covered:[]}; })
  ])
    .then(function(results){
      S.metadata = results[0];
      S.splits = results[1].splits || [];
      S.goals = results[2].goals || [];
      S.equipmentCatalog = results[3].equipment || [];
      // Falls back to an empty list against an older backend without this
      // endpoint - populateProgramForm's phase select then just shows
      // "Auto" and the whole training_phase field is omitted from the
      // generate-program payload, same as before this feature existed.
      S.trainingPhases = results[4].training_phases || [];
      S.scTemplateSportQuestions = results[5].by_sport || {};
      S.scTemplateSportsCovered = results[6].sports_covered || [];
      setStatus(true);
      renderHeroFacts();
      renderSetup();
      populateProgramForm();
      renderConditioningSportGrid();
      renderHomeSportsGrid();
      renderHeroMosaic();
      updateHeroForReturningUser();
      // No account is ever required: refreshCurrentUser() just quietly
      // resolves S.currentUser if a saved cloud login happens to exist on
      // this device, then enterAppOrGate (accounts.js) always proceeds
      // straight to showInitialScreen() either way.
      refreshCurrentUser().then(enterAppOrGate);
    })
    .catch(function(){
      _bootAttempt++;
      if(_bootAttempt < BOOT_MAX_ATTEMPTS){
        // Likely a cold start or a blip - say so and retry on our own
        // instead of dumping the person on an error screen straight away.
        var lt = document.getElementById('loadingText');
        if(lt) lt.textContent = 'Waking up the server… (try ' + (_bootAttempt + 1) + ' of ' + BOOT_MAX_ATTEMPTS + ')';
        var cb = document.getElementById('btnCancelLoading');
        if(cb) cb.parentNode.style.display = 'none'; // nothing to cancel while connecting
        show('screen-loading');
        setTimeout(function(){ boot(true); }, 4000 * _bootAttempt);
        return;
      }
      setStatus(false);
      show('screen-error');
      hideNativeSplash();
    });
}

// The warning/disclaimer screen only needs to be seen once per device -
// after that, opening the app goes straight to Home (or, once onboarding
// is complete, Home's returning-user view - see updateHeroForReturningUser
// in home.js), same as any other app that only shows a first-run notice once.
function hasSeenWarning(){
  try{ return localStorage.getItem('forge_warning_seen') === '1'; }catch(e){ return false; }
}
function markWarningSeen(){
  try{ localStorage.setItem('forge_warning_seen', '1'); }catch(e){ /* storage unavailable — ignore */ }
}
function showInitialScreen(){
  show(hasSeenWarning() ? 'screen-hero' : 'screen-warning');
  hideNativeSplash();
}

function renderHeroFacts(){
  var el = document.getElementById('heroFacts');
  var m = S.metadata;
  // "Injury Profiles" (a raw taxonomy count) read as an odd thing to boast
  // about on a landing page, so this now leads with exercise-library depth
  // instead - falls back to the injuries count only against an older
  // backend that doesn't yet send exercise_count.
  var exerciseCount = m.exercise_count || m.injuries.length;
  // Rounded down to the nearest hundred for display ("800+" not "828+") -
  // a landing-page stat, not a live counter, and the exact figure just
  // shifts as exercises get added/edited, so a round number reads cleaner
  // and doesn't need re-touching every data update.
  var exerciseCountDisplay = Math.floor(exerciseCount / 100) * 100;
  el.innerHTML =
    '<div><strong>'+m.sports.length+'</strong><small>Disciplines</small></div>'+
    '<div><strong>'+m.equipment.length+'</strong><small>Equipment Types</small></div>'+
    '<div><strong>'+exerciseCountDisplay+'+</strong><small>Exercises</small></div>'+
    '<div><strong>'+loadHistory().length+'</strong><small>Logged Sessions</small></div>';
}

function esc(s){
  return String(s).replace(/[&<>"']/g, function(c){
    return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];
  });
}

