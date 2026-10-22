'use strict';

// ============================================================
// HOME — photo showcase of every discipline (tap one to jump straight
// into the setup wizard with that discipline pre-selected)
// ============================================================

// Get Started (warning screen) drops the person straight into the wizard's
// first step - see the onboarding order this mirrors: warning -> profile ->
// discipline -> scope -> equipment/injuries -> experience/readiness ->
// generate (getWizardStepIds in weight-unit.js).
document.getElementById('btnGetStarted').addEventListener('click', function(){
  markWarningSeen();
  // True first run - nothing saved yet, so keep the wizard linear (see
  // S.wizardEditMode in goToStep, injury-browser.js).
  S.wizardEditMode = false;
  show('screen-setup');
  goToStep(1);
});

// Terms & Conditions — Get Started stays disabled until the box is checked,
// and the checkbox/agreement choice persists so a returning device doesn't
// have to re-tick it after already agreeing once.
(function(){
  var cb = document.getElementById('tosCheckbox');
  var goBtn = document.getElementById('btnGetStarted');
  var link = document.getElementById('tosLink');
  var backdrop = document.getElementById('tosModalBackdrop');
  var closeBtn = document.getElementById('tosModalClose');
  var acceptBtn = document.getElementById('tosModalAccept');
  if(!cb || !goBtn) return;
  try{
    if(localStorage.getItem('forge_tos_accepted') === '1'){ cb.checked = true; }
  }catch(e){}
  function sync(){
    goBtn.disabled = !cb.checked;
    try{ if(cb.checked) localStorage.setItem('forge_tos_accepted','1'); }catch(e){}
  }
  cb.addEventListener('change', sync);
  sync();
  function openModal(e){ if(e) e.preventDefault(); if(backdrop) backdrop.style.display='flex'; }
  function closeModal(){ if(backdrop) backdrop.style.display='none'; }
  if(link) link.addEventListener('click', openModal);
  if(closeBtn) closeBtn.addEventListener('click', closeModal);
  if(backdrop) backdrop.addEventListener('click', function(e){ if(e.target === backdrop) closeModal(); });
  if(acceptBtn) acceptBtn.addEventListener('click', function(){ cb.checked = true; sync(); closeModal(); });
})();

// Once someone has a saved profile, Home stops pitching "build your
// profile" at them every time and instead opens on a compact returning-user
// view - same pattern as most fitness apps switching from onboarding to a
// dashboard after first use. This used to key off logged history instead
// of the profile itself, which meant "Build Strength" sent even a
// returning user back through the whole wizard the moment they hadn't yet
// logged a session (or wanted to train again before logging the last one).
//
// A third, even quieter state kicks in once a program has actually been
// saved (loadSavedProgramsLocal().length, program-wizard-steps.js): at that
// point the discipline pitch and the full tile grid below aren't decisions
// left to make, so Home collapses to just "View Your Program" / "Make A
// New Program" - see hasSavedProgram().
function hasSavedProgram(){
  return loadSavedProgramsLocal().length > 0;
}
function updateHeroForReturningUser(){
  var hist = loadHistory();
  var isReturning = hasAthleteProfile();
  var hasProgram = hasSavedProgram();
  var firstRun = document.getElementById('heroFirstRun');
  var returning = document.getElementById('heroReturning');
  var hasProgramHero = document.getElementById('heroHasProgram');
  var sportsSection = document.getElementById('homeSportsSection');
  if(!firstRun || !returning || !hasProgramHero) return;
  firstRun.style.display = (hasProgram || isReturning) ? 'none' : '';
  returning.style.display = (hasProgram || !isReturning) ? 'none' : '';
  hasProgramHero.style.display = hasProgram ? '' : 'none';
  // The discipline tile grid ("Every Discipline. One System.") is only a
  // decision worth re-surfacing before a program exists - once one is
  // saved, "Make A New Program" is the way back into it.
  if(sportsSection) sportsSection.style.display = hasProgram ? 'none' : '';
  var qsSection = document.getElementById('homeQuickStart');
  if(qsSection) qsSection.style.display = hasProgram ? 'none' : '';
  if(hasProgram){
    var savedList = loadSavedProgramsLocal();
    var p = loadAthleteProfile();
    var name = p && p.name ? p.name.trim() : '';
    document.getElementById('heroProgramEyebrow').textContent = name ? 'Welcome Back, '+name : 'Welcome Back';
    document.getElementById('heroProgramSub').textContent = savedList.length > 1
      ? 'You have '+savedList.length+' saved programs — jump back in, or build a new one.'
      : 'Jump back into your saved program, or build a new one.';
  } else if(isReturning){
    var last = hist[hist.length - 1];
    var p2 = loadAthleteProfile();
    var name2 = p2 && p2.name ? p2.name.trim() : '';
    document.getElementById('heroReturningEyebrow').textContent = name2 ? 'Welcome Back, '+name2 : 'Welcome Back';
    document.getElementById('heroReturningFacts').innerHTML =
      '<div><strong>'+hist.length+'</strong><small>Logged Sessions</small></div>'+
      (last && last.sport ? '<div><strong>'+esc(last.sport)+'</strong><small>Last Discipline</small></div>' : '');
  }
}
// "View Your Program" - straight to the one saved program if that's all
// there is, otherwise the existing "My Saved Programs" picker
// (openSavedProgramsModal, program-wizard-steps.js) so they choose which.
document.getElementById('btnViewProgram').addEventListener('click', function(){
  var saved = loadSavedProgramsLocal();
  if(saved.length === 1){
    // Set S.lastProgram before show('screen-program') so its own
    // first-visit check (nav-control.js) doesn't think this is a fresh
    // visit and reset to wizard step 1 out from under the loaded program.
    loadSavedProgram(saved[0]);
    show('screen-program');
  } else {
    openSavedProgramsModal();
  }
});
// Shared by "Make A New Program" (a program already exists) and "Build
// Your Program" (returning user, profile saved, no program yet) - a saved
// profile already exists in both cases, so this pre-fills the wizard from
// it (name, biometrics, equipment, injuries, experience, last discipline)
// the same way editAthleteProfile() does (profile.js) - the person is only
// choosing what's different for this program (usually just discipline),
// not retyping their whole profile from scratch every time they build one.
function startNewProgramFromProfile(){
  markWarningSeen();
  S.quickStart = false;
  // Same reasoning as editAthleteProfile (profile.js) - profile's already
  // filled in below, so unlock the progress dots to jump straight to a step.
  S.wizardEditMode = true;
  applyAthleteProfileToState();
  show('screen-setup');
  goToStep(1);
}
document.getElementById('btnMakeNewProgram').addEventListener('click', startNewProgramFromProfile);
document.getElementById('btnBuildProgram').addEventListener('click', startNewProgramFromProfile);

document.getElementById('btnViewHistory').addEventListener('click', function(){ show('screen-history'); });

// Clears any previous tile's rotation timers before re-rendering, so we
// never stack up intervals across repeated Home renders.
var homeTileRotationTimers = [];
function stopHomeTileRotation(){
  homeTileRotationTimers.forEach(function(id){ clearInterval(id); });
  homeTileRotationTimers = [];
}

// Builds the photo mosaic behind the hero text out of every discipline's
// tile image (shuffled so the grid doesn't just mirror the order sports are
// listed in) instead of the single static background photo it used to be.
function renderHeroMosaic(){
  var m = S.metadata;
  var el = document.getElementById('heroMosaic');
  if(!m || !el) return;
  var imgs = [];
  m.sports.forEach(function(sport){
    var img = firstImg(themeFor(sport));
    if(img) imgs.push(img);
  });
  if(!imgs.length) return;
  // simple shuffle so adjacent grid cells rarely repeat the same photo
  for(var i = imgs.length - 1; i > 0; i--){
    var j = Math.floor(Math.random() * (i + 1));
    var tmp = imgs[i]; imgs[i] = imgs[j]; imgs[j] = tmp;
  }
  var cells = 18; // 6 columns x 3 rows, see .hero-mosaic
  var html = '';
  for(var k = 0; k < cells; k++){
    html += '<div style="background-image:url(\''+imgs[k % imgs.length]+'\');--i:'+k+'"></div>';
  }
  el.innerHTML = html;
}

function renderHomeSportsGrid(){
  var m = S.metadata;
  var hg = document.getElementById('homeSportsGrid');
  if(!m || !hg) return;
  stopHomeTileRotation();
  hg.innerHTML = m.sports.map(function(sport){
    var t = themeFor(sport);
    var imgs = Array.isArray(t.img) ? t.img : (t.img ? [t.img] : []);
    var bg = imgs.length ? "background-image:url('"+imgs[0]+"');" : '';
    return '<div class="choice" data-home-sport="'+esc(sport)+'" data-img-index="0" style="--accent:'+t.accent+';'+bg+'">'+
      '<div class="tile-body"><span class="icon">'+esc(t.mono)+'</span><h4>'+esc(sport)+'</h4>'+
      (t.region ? '<span class="region">'+esc(t.region)+'</span>' : '')+'</div>'+
      '</div>';
  }).join('');
  hg.querySelectorAll('.choice').forEach(function(card){
    card.addEventListener('click', function(){
      jumpToDiscipline(card.getAttribute('data-home-sport'));
    });
    // Tiles with more than one photo cycle through them every few seconds
    // so a discipline can show off a small gallery instead of one static shot.
    var sport = card.getAttribute('data-home-sport');
    var t = themeFor(sport);
    var imgs = Array.isArray(t.img) ? t.img : (t.img ? [t.img] : []);
    if(imgs.length > 1){
      var id = setInterval(function(){
        var next = (parseInt(card.getAttribute('data-img-index'), 10) + 1) % imgs.length;
        card.setAttribute('data-img-index', next);
        card.style.backgroundImage = "url('"+imgs[next]+"')";
      }, 4000 + Math.floor(Math.random() * 800)); // slight stagger so tiles don't flip in unison
      homeTileRotationTimers.push(id);
    }
  });
}
// Tapping a discipline tile is always a preset pick (Custom Mode only
// exists as a toggle on the wizard's own discipline step, which this
// bypasses) - so this drops the person straight into the Program Builder,
// same as confirming "discipline" mid-wizard does (see the discipline-step
// branch in btnWizNext, injury-browser.js), instead of routing through the
// setup wizard's screens at all.
function jumpToDiscipline(sport){
  S.sport = sport;
  S.emphasis = emphasisForSport(sport);
  S.trainScope = 'program';
  applyTheme(sport);
  document.querySelectorAll('#disciplineGrid .choice').forEach(function(c){
    c.classList.toggle('selected', c.getAttribute('data-sport') === sport);
  });
  if(typeof saveAthleteProfile === 'function') saveAthleteProfile();
  populateProgramForm();
  var pgSportSel = document.getElementById('pgSport');
  if(pgSportSel) pgSportSel.value = sport;
  show('screen-program');
}

