'use strict';

// ============================================================
// ATHLETE PROFILE — persisted once, reused every session.
//
// Everything in the wizard used to live only in memory (S.*), so it reset
// to blank every time the app was reopened, and "Build Strength" always
// dropped the person back at step 1 even after they'd already set
// everything up once. This is the fix: the "slow-changing" wizard answers
// (discipline, experience, equipment, injuries, biometrics) get saved here
// as one profile after the first successful generate(), and every visit
// after that restores them instead of asking again.
// ============================================================

var ATHLETE_PROFILE_KEY = 'forge_athlete_profile';

function hasAthleteProfile(){
  try{ return !!localStorage.getItem(ATHLETE_PROFILE_KEY); }
  catch(e){ return false; }
}

function loadAthleteProfile(){
  try{ return JSON.parse(localStorage.getItem(ATHLETE_PROFILE_KEY)) || null; }
  catch(e){ return null; }
}

// Snapshots the current wizard answers as the athlete's profile. Called at
// the top of generate() (generate.js) so the profile always reflects
// whatever was just confirmed on the Review step, since it all flows
// through generate().
function saveAthleteProfile(){
  var nameEl = document.getElementById('bioName');
  var profile = {
    name: nameEl ? nameEl.value.trim() : (S.athleteName || ''),
    sport: S.sport,
    mode: S.mode,
    emphasis: S.emphasis,
    experience: S.experience,
    conditioningEmphasis: S.conditioningEmphasis,
    sessionDuration: S.sessionDuration,
    equipment: Array.from(S.equipment),
    injuries: Array.from(S.injuries),
    injuryStages: S.injuryStages,
    injurySides: S.injurySides,
    biometrics: {
      height_cm: numVal('bioHeight'),
      weight_kg: inputToKg(numVal('bioWeight')),
      bench_press_1rm_kg: inputToKg(numVal('bioBench')),
      squat_1rm_kg: inputToKg(numVal('bioSquat')),
      deadlift_1rm_kg: inputToKg(numVal('bioDeadlift')),
      pullups_max_reps: numVal('bioPullups'),
      pushups_max_reps: numVal('bioPushups'),
      sex: document.getElementById('bioSex').value || null
    },
    savedAt: Date.now()
  };
  try{ localStorage.setItem(ATHLETE_PROFILE_KEY, JSON.stringify(profile)); }
  catch(e){ /* storage unavailable — profile just won't persist this run */ }
}

// Restores a saved profile into S and the wizard's own DOM fields (the
// wizard steps are static, always-in-the-DOM panels - see index.html - so
// setting values here is enough even for steps the person never opens
// during a quick session). Safe to call even with no saved profile (no-op).
function applyAthleteProfileToState(){
  var p = loadAthleteProfile();
  if(!p) return false;

  // A restored profile's biometrics are just as "confirmed" as clicking
  // Next past the wizard's own Profile step - see bioStepConfirmedThisSession
  // (weight-unit.js) and prefillProgramBiometricsFromProfile (program-wizard-steps.js).
  S.bioStepConfirmedThisSession = true;
  S.athleteName = p.name || '';
  var nameEl = document.getElementById('bioName');
  if(nameEl) nameEl.value = S.athleteName;
  S.sport = p.sport;
  S.mode = p.mode || 'preset';
  S.emphasis = p.emphasis;
  S.experience = p.experience || S.experience;
  S.conditioningEmphasis = p.conditioningEmphasis || S.conditioningEmphasis;
  S.sessionDuration = p.sessionDuration || S.sessionDuration;

  S.equipment = new Set(p.equipment && p.equipment.length ? p.equipment : ['Bodyweight']);
  S.injuries = new Set(p.injuries || []);
  S.injuryStages = p.injuryStages || {};
  S.injurySides = p.injurySides || {};

  var b = p.biometrics || {};
  setNumField('bioHeight', b.height_cm);
  setNumField('bioWeight', kgToDisplay(b.weight_kg));
  setNumField('bioBench', kgToDisplay(b.bench_press_1rm_kg));
  setNumField('bioSquat', kgToDisplay(b.squat_1rm_kg));
  setNumField('bioDeadlift', kgToDisplay(b.deadlift_1rm_kg));
  setNumField('bioPullups', b.pullups_max_reps);
  setNumField('bioPushups', b.pushups_max_reps);
  if(b.sex){ var sexEl = document.getElementById('bioSex'); if(sexEl) sexEl.value = b.sex; }

  syncWizardUIToState();
  applyTheme(S.sport);
  return true;
}

function kgToDisplay(kg){
  if(kg == null || isNaN(kg)) return null;
  return S.unit === 'lb' ? Math.round(kgToLb(kg)) : kg;
}
function setNumField(id, val){
  var el = document.getElementById(id);
  if(el && val != null && !isNaN(val)) el.value = val;
}

// Re-renders/re-highlights every wizard control that doesn't automatically
// pick up a change to the underlying S sets/values on its own - discipline
// tile selection, experience radios, equipment checks, and the injury
// browser all render off S at specific trigger points (a click, or initial
// boot), not reactively, so restoring a profile needs to explicitly refresh
// each one.
function syncWizardUIToState(){
  document.querySelectorAll('#disciplineGrid .choice').forEach(function(c){
    c.classList.toggle('selected', c.getAttribute('data-sport') === S.sport);
  });
  document.querySelectorAll('#experienceGroup label').forEach(function(l){
    var inp = l.querySelector('input');
    var checked = inp && inp.value === S.experience;
    if(inp) inp.checked = checked;
    l.classList.toggle('checked', !!checked);
  });
  var eqEl = document.getElementById('equipmentChecks');
  if(eqEl) renderEquipmentGroups(eqEl, S.equipment, S.equipmentCatalog);
  if(typeof renderInjuryBrowser === 'function') renderInjuryBrowser('wiz');
  var cmt = document.getElementById('customModeToggle');
  if(cmt) cmt.checked = S.mode === 'custom';
  var sd = document.getElementById('sessionDuration');
  if(sd) sd.value = String(S.sessionDuration);
}

// Wired from the History screen's "Edit Profile" button (index.html) - the
// only way back into the full wizard once a profile exists. Pre-fills
// everything from the saved profile instead of the blank-slate wizard
// btnBuildStrength starts, and lands on step 1 (discipline) so a person can
// change sport too, not just tweak equipment/injuries/biometrics.
function editAthleteProfile(){
  S.quickStart = false;
  // Every field is already filled in from the saved profile below, so this
  // is genuinely editing, not onboarding - unlock the progress dots (see
  // S.wizardEditMode in goToStep, injury-browser.js) so a click jumps
  // straight to whichever step actually needs changing, instead of Next
  // through every screen first.
  S.wizardEditMode = true;
  applyAthleteProfileToState();
  show('screen-setup');
  goToStep(1);
}
var btnEditProfileEl = document.getElementById('btnEditProfile');
if(btnEditProfileEl) btnEditProfileEl.addEventListener('click', editAthleteProfile);

// ------------------------------------------------------------------
// Read-only profile summary — what the Home "Profile" button opens when
// a local profile already exists. Landing straight in the 7-step wizard
// (editAthleteProfile above) with no warning felt like the app had
// launched an unrelated flow; this shows what's actually saved first,
// with an explicit "Edit Profile" action for anyone who wants to change
// something. editAthleteProfile() itself is unchanged and still does the
// full wizard-edit-mode jump.
// ------------------------------------------------------------------
function profileSummaryRow(label, value){
  if(value == null || value === '') return '';
  return '<div class="transfer-row"><span>'+esc(label)+'</span><b>'+esc(String(value))+'</b></div>';
}
function openProfileSummaryModal(){
  var p = loadAthleteProfile();
  if(!p){ editAthleteProfile(); return; }
  var overlay = document.getElementById('modalOverlay');
  var content = document.getElementById('modalContent');
  var b = p.biometrics || {};
  var rows = [
    profileSummaryRow('Sport', p.sport),
    profileSummaryRow('Experience', p.experience),
    profileSummaryRow('Sex', b.sex),
    profileSummaryRow('Height', b.height_cm != null ? b.height_cm+'cm' : null),
    profileSummaryRow('Weight', b.weight_kg != null ? fmtWeight(b.weight_kg) : null),
    profileSummaryRow('Bench Press 1RM', b.bench_press_1rm_kg != null ? fmtWeight(b.bench_press_1rm_kg) : null),
    profileSummaryRow('Squat 1RM', b.squat_1rm_kg != null ? fmtWeight(b.squat_1rm_kg) : null),
    profileSummaryRow('Deadlift 1RM', b.deadlift_1rm_kg != null ? fmtWeight(b.deadlift_1rm_kg) : null),
    profileSummaryRow('Max Pull-ups', b.pullups_max_reps),
    profileSummaryRow('Max Push-ups', b.pushups_max_reps)
  ].join('');
  content.innerHTML =
    '<button class="close-btn" id="modalClose">&times;</button>'+
    '<h3>'+esc(p.name || 'Your Profile')+'</h3>'+
    '<div class="modal-sub">Saved on this device</div>'+
    '<div class="modal-section">'+rows+'</div>'+
    '<button class="btn" id="btnProfileSummaryEdit" style="width:100%;">Edit Profile</button>'+
    '<div class="auth-switch-row">'+
    (S.currentUser
      ? 'Signed in as '+esc(S.currentUser.display_name || S.currentUser.email)+'.'
      : 'Want this synced across devices? <a href="#" id="profileSummaryLogin">Log In / Create Account</a>')+
    '</div>';
  overlay.classList.add('active');
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('btnProfileSummaryEdit').addEventListener('click', function(){
    closeModal();
    editAthleteProfile();
  });
  var loginLink = document.getElementById('profileSummaryLogin');
  if(loginLink){
    loginLink.addEventListener('click', function(e){
      e.preventDefault();
      openAuthModal('login');
    });
  }
}
