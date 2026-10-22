'use strict';

// ============================================================
// SCREEN / NAV CONTROL
// ============================================================

// Honors the OS "reduce motion" setting for every scripted scroll.
function smoothBehavior(){
  try{ return window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth'; }catch(e){ return 'auto'; }
}

function show(id){
  document.querySelectorAll('.screen').forEach(function(s){ s.classList.remove('active'); });
  document.getElementById(id).classList.add('active');
  var nav = document.getElementById('mainNav');
  // Nav stays hidden on the disclaimer (it must be accepted first - tapping
  // a tab used to skip it), the loading screen (leaving mid-build used to get
  // you yanked back to results later) and the error screen.
  nav.style.display = (id === 'screen-error' || id === 'screen-warning' || id === 'screen-loading') ? 'none' : 'flex';
  nav.querySelectorAll('button').forEach(function(b){
    var target = b.getAttribute('data-nav');
    b.classList.toggle('active', ('screen-'+target) === id);
  });
  if(id === 'screen-history') renderHistory();
  if(id === 'screen-hero') updateHeroForReturningUser();
  if(id === 'screen-calendar') renderCalendar();
  if(id === 'screen-progress'){ renderTrendsDashboard(); renderProgressPage(); }
  if(id === 'screen-program'){
    updateProgramInjuryNote();
    // Only jump back to wizard step 1 on a genuinely fresh visit. Without
    // this guard, re-clicking the "Program" nav tab after a program was
    // already built re-ran goToProgramStep(1) every time, which reveals
    // #pgWizardChrome again on top of the still-visible #programResult
    // (that visibility is intentionally left alone on revisits - see
    // setProgramResultMode) - the wizard and the built program stacked
    // together, looking like the screen was looping between two pages.
    if(!S.lastProgram){ prefillProgramBiometricsFromProfile(); goToProgramStep(1); }
  }
  if(id === 'screen-conditioning' && !S.condSport && S.metadata){ selectConditioningSport(S.metadata.sports[0]); }

  // The ambience only makes sense while one discipline is in focus —
  // history/calendar/progress mix every sport together, so they stay neutral.
  if(id === 'screen-hero' || id === 'screen-history' || id === 'screen-calendar' || id === 'screen-progress' || id === 'screen-error'){
    applyTheme(null);
  } else if(id === 'screen-setup'){
    applyTheme(S.sport);
  } else if(id === 'screen-conditioning'){
    applyTheme(S.condSport);
  } else if(id === 'screen-program'){
    applyTheme(S.sport);
  } else if(id === 'screen-results' && S.lastResult){
    applyTheme(S.lastResult.sport);
  }

  // Instant, not smooth: the new screen already fades in, and a long animated
  // scroll from deep in a page just feels sluggish.
  window.scrollTo(0, 0);
}

// Same unsaved-session risk as the Discard button (see pr-suggestion.js) —
// tapping a nav tab while mid-workout on screen-results used to jump away
// instantly with zero warning, silently dropping every set logged so far
// since nothing is synced until "Finish & Save Session" is pressed.
function hasUnsavedSessionLog(){
  var active = document.querySelector('.screen.active');
  if(!active || active.id !== 'screen-results') return false;
  return Object.keys(S.sessionLog || {}).some(function(exId){
    return (S.sessionLog[exId].sets || []).length > 0;
  });
}
function confirmLeaveResultsIfNeeded(onProceed){
  if(!hasUnsavedSessionLog()){ onProceed(); return; }
  showConfirm('You have logged sets in this session that haven\'t been saved yet. Leave without saving?', {title:'Leave this session?'}).then(function(ok){
    if(ok) onProceed();
  });
}

document.getElementById('mainNav').addEventListener('click', function(e){
  var btn = e.target.closest('button[data-nav]');
  if(!btn) return;
  var target = btn.getAttribute('data-nav');
  confirmLeaveResultsIfNeeded(function(){
    show(target === 'hero' ? 'screen-hero' : 'screen-'+target);
  });
});

// "Powerlifting", "Look Jacked", and "Strength + Hypertrophy" are pure
// strength/muscle-building modes sourced from guide PDFs, not a sport - the
// "Transfer N" score and "Sport transfer" rationale describe transfer to a
// sport's on-field qualities, which means nothing for these three, so all
// are hidden from the exercise card wherever this returns true (see
// renderProgramDay/renderResults). Custom Mode's "Custom" discipline is the
// same situation: it isn't a real sport the backend has any quality profile
// or authored priority for, so the engine's transfer score/rationale for it
// is a meaningless 0 / generic sentence (see backend/services/sport_profiles.py's
// blended_transfer_score and transfer_rationale fallbacks) - lumped in with
// the strength modes here so callers get one check instead of two.
function isStrengthMode(){
  return S.sport === 'Powerlifting' || S.sport === 'Look Jacked' || S.sport === 'Strength + Hypertrophy' || S.sport === 'Custom';
}

