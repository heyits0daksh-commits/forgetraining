'use strict';

// ============================================================
// ACCOUNTS (Phase 6 backend, wired to the UI) — an authenticated request
// always overrides ATHLETE_ID server-side with the caller's own account id
// (see backend/api/routes.py's athlete_id resolution note), so ATHLETE_ID
// above stays exactly what it always was for anonymous use; logging in
// just makes the same endpoints personal without any extra plumbing here.
// ============================================================

var AUTH_TOKEN_KEY = 'forge_auth_token';
// Long-lived, revocable credential (see backend REFRESH_TOKEN_EXPIRE_DAYS).
// Stored separately from the short-lived access token so the two can be
// refreshed independently.
var AUTH_REFRESH_KEY = 'forge_refresh_token';
function loadToken(){
  try{ return localStorage.getItem(AUTH_TOKEN_KEY) || null; }catch(e){ return null; }
}
function saveToken(token){
  try{
    if(token){ localStorage.setItem(AUTH_TOKEN_KEY, token); }
    else{ localStorage.removeItem(AUTH_TOKEN_KEY); }
  }catch(e){ /* storage unavailable — token just won't survive a refresh */ }
}
function loadRefreshToken(){
  try{ return localStorage.getItem(AUTH_REFRESH_KEY) || null; }catch(e){ return null; }
}
function saveRefreshToken(token){
  try{
    if(token){ localStorage.setItem(AUTH_REFRESH_KEY, token); }
    else{ localStorage.removeItem(AUTH_REFRESH_KEY); }
  }catch(e){ /* storage unavailable */ }
}
// Every authenticated request adds this; anonymous requests get an empty
// object (same as not sending the header at all), so nothing about
// existing anonymous behavior changes.
function authHeaders(){
  return S.authToken ? {'Authorization': 'Bearer ' + S.authToken} : {};
}
function jsonAuthHeaders(){
  var h = {'Content-Type': 'application/json'};
  var a = authHeaders();
  for(var k in a){ h[k] = a[k]; }
  return h;
}
function logout(){
  var rt = loadRefreshToken();
  S.authToken = null;
  S.currentUser = null;
  saveToken(null);
  saveRefreshToken(null);
  updateAccountUI();
  // Best-effort revoke on the server so the old refresh token can't be
  // reused later; doesn't block the local logout either way.
  if(rt){
    _nativeFetch(API_BASE + '/api/v1/auth/logout', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({refresh_token: rt})
    }).catch(function(){});
  }
}
// ------------------------------------------------------------------
// Silent refresh: the access token only lasts 30 minutes
// (ACCESS_TOKEN_EXPIRE_MINUTES), but the refresh token lasts a year and
// rotates on every use (backend/services/auth_service.py), so as long as
// this runs at least once whenever the app is opened, the user stays
// signed in indefinitely on that device instead of being bounced back to
// the login form. This wraps the global fetch() so every authenticated
// call in the app (accounts.js, generate.js, history.js, etc.) gets this
// transparently, with no changes needed at each call site.
// ------------------------------------------------------------------
var _nativeFetch = window.fetch.bind(window);
var _refreshInFlight = null;
function _doTokenRefresh(){
  if(_refreshInFlight){ return _refreshInFlight; }
  var rt = loadRefreshToken();
  if(!rt){ return Promise.resolve(false); }
  _refreshInFlight = _nativeFetch(API_BASE + '/api/v1/auth/refresh', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({refresh_token: rt})
  }).then(function(r){
    if(!r.ok){ return false; }
    return r.json().then(function(data){
      S.authToken = data.access_token;
      saveToken(data.access_token);
      saveRefreshToken(data.refresh_token);
      return true;
    });
  }).catch(function(){ return false; })
    .then(function(ok){ _refreshInFlight = null; return ok; });
  return _refreshInFlight;
}
window.fetch = function(input, init){
  var url = (typeof input === 'string') ? input : (input && input.url) || '';
  var hadAuthHeader = !!(init && init.headers && init.headers['Authorization']);
  return _nativeFetch(input, init).then(function(resp){
    if(resp.status !== 401 || !hadAuthHeader || url.indexOf(API_BASE) !== 0){
      return resp;
    }
    return _doTokenRefresh().then(function(ok){
      if(!ok){ logout(); return resp; }
      var retryInit = {};
      for(var k in init){ retryInit[k] = init[k]; }
      retryInit.headers = {};
      for(var h in init.headers){ retryInit.headers[h] = init.headers[h]; }
      retryInit.headers['Authorization'] = 'Bearer ' + S.authToken;
      return _nativeFetch(input, retryInit);
    });
  });
};
// Resolves the current token into a profile (GET /api/v1/auth/me). Called
// once at boot and again right after login/register. If there's no access
// token but a refresh token survived (e.g. it expired between visits),
// this silently mints a new one first instead of dropping the user back
// to the login form.
function refreshCurrentUser(){
  var proceed = S.authToken ? Promise.resolve(true)
    : (loadRefreshToken() ? _doTokenRefresh() : Promise.resolve(false));
  return proceed.then(function(haveToken){
    if(!haveToken){ updateAccountUI(); return null; }
    return fetch(API_BASE + '/api/v1/auth/me', {headers: authHeaders()})
      .then(function(r){
        if(!r.ok){ return null; }
        return r.json();
      })
      .then(function(user){
        S.currentUser = user;
        updateAccountUI();
        return user;
      })
      .catch(function(){ return null; });
  });
}
// No account is ever required to use or save FORGE - the profile built in
// the wizard's first step lives in localStorage (see profile.js) and that
// alone is enough to save/restore everything. "Profile" (accountBtn) is
// strictly about that local, on-device profile — sport/equipment/injuries
// — and always opens the same summary/wizard regardless of login state.
// "Log In" (cloudAuthBtn) is the separate, always-visible entry point for
// the optional cloud account that syncs across devices; it used to only
// be reachable by first logging in some other way (there wasn't one), so
// a signed-out person had no way to find login/signup at all. Keeping the
// two buttons distinct (rather than overloading accountBtn's label with
// the signed-in user's name, as before) means login stays visible and
// obvious no matter what's saved locally.
function updateAccountUI(){
  var btn = document.getElementById('accountBtn');
  if(btn){
    var p = loadAthleteProfile();
    btn.textContent = (p && p.name) ? p.name : 'Profile';
  }
  var cloudBtn = document.getElementById('cloudAuthBtn');
  var cloudLabel = document.getElementById('cloudAuthBtnLabel');
  if(cloudBtn && cloudLabel){
    if(S.currentUser){
      cloudLabel.textContent = S.currentUser.display_name || S.currentUser.email;
      cloudBtn.classList.add('logged-in');
      cloudBtn.title = 'Account';
      cloudBtn.setAttribute('aria-label', 'Account');
    }else{
      cloudLabel.textContent = 'Log In';
      cloudBtn.classList.remove('logged-in');
      cloudBtn.title = 'Log in or create an account';
      cloudBtn.setAttribute('aria-label', 'Log in or create an account');
    }
  }
}
function onAccountBtnClick(){
  // A saved local profile opens a read-only summary first (profile.js)
  // rather than dropping straight into the wizard's edit mode - that jump
  // used to happen with no warning, which read as the wrong screen opening.
  // The summary's own "Edit Profile" button still calls editAthleteProfile().
  if(hasAthleteProfile()){ openProfileSummaryModal(); return; }
  markWarningSeen();
  show('screen-setup');
  goToStep(1);
}
function onCloudAuthBtnClick(){
  if(S.currentUser){ openAccountModal(); return; }
  openAuthModal('login');
}
var accountBtnEl = document.getElementById('accountBtn');
if(accountBtnEl) accountBtnEl.addEventListener('click', onAccountBtnClick);
var cloudAuthBtnEl = document.getElementById('cloudAuthBtn');
if(cloudAuthBtnEl) cloudAuthBtnEl.addEventListener('click', onCloudAuthBtnClick);
// The app never gates on an account - it opens straight to the normal
// first-run/returning-user Home screen either way (see home.js).
function enterAppOrGate(){
  showInitialScreen();
}
// ------------------------------------------------------------------
// Shared icon set for the auth/account modals — same 24x24, currentColor,
// stroke-width:2 convention used by every other icon in the app (header,
// nav, callouts), so these read as part of FORGE rather than a bolted-on
// third-party form.
// ------------------------------------------------------------------
var AUTH_ICONS = {
  mail:'<svg class="field-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="20" height="16" rx="2"/><path d="m22 6-10 7L2 6"/></svg>',
  lock:'<svg class="field-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="4" y="11" width="16" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>',
  user:'<svg class="field-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21a8 8 0 0 0-16 0"/><circle cx="12" cy="7" r="4"/></svg>',
  eye:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"/><circle cx="12" cy="12" r="3"/></svg>',
  eyeOff:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-6.4 0-10-8-10-8a19 19 0 0 1 4.22-5.94M9.9 4.24A9.6 9.6 0 0 1 12 4c6.4 0 10 8 10 8a19 19 0 0 1-2.16 3.19M14.12 14.12a3 3 0 1 1-4.24-4.24"/><path d="M2 2l20 20"/></svg>',
  check:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6 9 17l-5-5"/></svg>',
  alert:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/><path d="M12 9v4"/><path d="M12 17h.01"/></svg>',
  trash:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 6h18"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/></svg>',
  keyIcon:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="7.5" cy="15.5" r="5.5"/><path d="m21 2-9.6 9.6"/><path d="m15.5 7.5 3 3L22 7l-3-3"/></svg>'
};
var EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
// Toggles the invalid/valid look on one .field wrapper + its inline
// helper text, so a bad email or a too-short password is flagged right
// where it happened instead of only in one shared box at the bottom.
function setFieldState(fieldId, state, msg){
  var field = document.getElementById(fieldId);
  if(!field) return;
  field.classList.remove('invalid','valid');
  if(state){ field.classList.add(state); }
  var msgEl = field.querySelector('.field-msg');
  if(msgEl && msg !== undefined){
    msgEl.textContent = msg || '';
    msgEl.classList.toggle('error', state === 'invalid');
  }
}
function showAuthFormError(boxId, msg){
  var box = document.getElementById(boxId);
  if(!box) return;
  if(!msg){ box.classList.remove('show'); box.innerHTML = ''; return; }
  box.innerHTML = AUTH_ICONS.alert + '<span>'+esc(msg)+'</span>';
  box.classList.remove('show');
  // restart the shake animation even if the box was already showing a
  // different message
  void box.offsetWidth;
  box.classList.add('show');
}
// Wires a password field's show/hide eye toggle. Shared by login,
// register (both password fields) and the reset-password form.
function wirePasswordToggle(inputId, btnId){
  var input = document.getElementById(inputId);
  var btn = document.getElementById(btnId);
  if(!input || !btn) return;
  btn.addEventListener('click', function(){
    var toText = input.type === 'password';
    input.type = toText ? 'text' : 'password';
    btn.innerHTML = toText ? AUTH_ICONS.eyeOff : AUTH_ICONS.eye;
    btn.setAttribute('aria-label', toText ? 'Hide password' : 'Show password');
    input.focus();
  });
}
function setBtnLoading(btn, loading, loadingLabel, idleLabel){
  btn.disabled = loading;
  btn.innerHTML = loading ? ('<span class="btn-spinner"></span>'+esc(loadingLabel)) : esc(idleLabel);
}
// One shared form for both register and login — reuses the app's existing
// modal-overlay (see openExerciseModal/closeModal) rather than building a
// second modal system just for this.
// gate=true (only used at boot, when there's no logged-in user yet) hides
// the close button and blocks click-outside-to-close (see the modalOverlay
// click handler in exercise-modal.js), so the form can't be dismissed
// without an account - login/register is genuinely required, not optional.
function openAuthModal(mode, gate){
  mode = mode || 'login';
  S.authGate = !!gate;
  var overlay = document.getElementById('modalOverlay');
  var content = document.getElementById('modalContent');
  content.innerHTML = authFormHtml(mode, S.authGate);
  overlay.classList.add('active');
  wireAuthForm(mode);
}
function authFormHtml(mode, gate){
  var isLogin = mode === 'login';
  return (gate ? '' : '<button class="close-btn" id="modalClose">&times;</button>')+
    '<div class="auth-modal">'+
    '<div class="auth-head">'+
      '<div class="auth-badge">'+AUTH_ICONS.lock+'</div>'+
      '<div class="eyebrow">'+(gate ? 'Account Required' : 'FORGE Account')+'</div>'+
      '<h3>'+(isLogin ? 'Welcome Back' : 'Create Your Account')+'</h3>'+
      (gate ? '<div class="modal-sub">An account is required to use FORGE.</div>'
            : '<div class="modal-sub">'+(isLogin ? 'Log in to sync your training across devices.' : 'Your programs and history, synced everywhere.')+'</div>')+
    '</div>'+
    '<form id="authForm" novalidate>'+
    '<div class="auth-error-box" id="authError"></div>'+
    (isLogin ? '' :
      '<div class="field" id="fieldDisplayName">'+
      '<label for="authDisplayName">Display Name</label>'+
      '<div class="input-wrap">'+AUTH_ICONS.user+
      '<input type="text" id="authDisplayName" placeholder="Optional" autocomplete="name">'+
      '</div></div>')+
    '<div class="field" id="fieldEmail">'+
    '<label for="authEmail">Email</label>'+
    '<div class="input-wrap">'+AUTH_ICONS.mail+
    '<input type="email" id="authEmail" placeholder="you@example.com" autocomplete="email">'+
    '</div><div class="field-msg"></div></div>'+
    '<div class="field" id="fieldPassword">'+
    '<label for="authPassword">Password</label>'+
    '<div class="input-wrap">'+AUTH_ICONS.lock+
    '<input type="password" id="authPassword" data-has-toggle placeholder="'+(isLogin?'Your password':'Min. 8 characters')+'" autocomplete="'+(isLogin?'current-password':'new-password')+'">'+
    '<button type="button" class="pw-toggle" id="authPasswordToggle" aria-label="Show password">'+AUTH_ICONS.eye+'</button>'+
    '</div>'+
    (isLogin ? '<div class="field-msg"></div>' :
      '<div class="field-check" id="pwLenCheck">'+AUTH_ICONS.check+'<span>At least 8 characters</span></div>')+
    '</div>'+
    (isLogin ?
      '<div class="auth-forgot-row"><a href="#" id="authForgotLink">Forgot password?</a></div>' :
      '<div class="field" id="fieldPassword2">'+
      '<label for="authPassword2">Confirm Password</label>'+
      '<div class="input-wrap">'+AUTH_ICONS.lock+
      '<input type="password" id="authPassword2" placeholder="Re-enter password" autocomplete="new-password">'+
      '</div><div class="field-msg"></div></div>')+
    (isLogin ? '' :
      '<label class="auth-terms" for="authAcceptTerms">'+
      '<input type="checkbox" id="authAcceptTerms">'+
      '<span>I agree to the <a href="terms.html" target="_blank" rel="noopener">Terms of Service</a>, '+
      '<a href="privacy.html" target="_blank" rel="noopener">Privacy Policy</a>, and '+
      '<a href="disclaimer.html" target="_blank" rel="noopener">Medical Disclaimer</a>.</span>'+
      '</label>')+
    '<button type="submit" class="btn" id="authSubmit" style="width:100%;">'+(isLogin ? 'Log In' : 'Create Account')+'</button>'+
    '<div class="auth-switch-row">'+
    (isLogin
      ? 'No account yet? <a href="#" id="authSwitch">Create one</a>'
      : 'Already have an account? <a href="#" id="authSwitch">Log in</a>')+
    '</div></form></div>';
}
function wireAuthForm(mode){
  var isLogin = mode === 'login';
  var closeBtn = document.getElementById('modalClose');
  if(closeBtn){ closeBtn.addEventListener('click', closeModal); }
  document.getElementById('authSwitch').addEventListener('click', function(e){
    e.preventDefault();
    openAuthModal(mode === 'login' ? 'register' : 'login', S.authGate);
  });
  var forgotLink = document.getElementById('authForgotLink');
  if(forgotLink){
    forgotLink.addEventListener('click', function(e){
      e.preventDefault();
      openForgotPasswordModal(document.getElementById('authEmail').value.trim());
    });
  }
  wirePasswordToggle('authPassword', 'authPasswordToggle');
  var pwEl = document.getElementById('authPassword');
  var pwLenCheck = document.getElementById('pwLenCheck');
  if(pwLenCheck){
    pwEl.addEventListener('input', function(){
      pwLenCheck.classList.toggle('met', pwEl.value.length >= 8);
    });
  }
  var form = document.getElementById('authForm');
  var submitBtn = document.getElementById('authSubmit');
  var idleLabel = isLogin ? 'Log In' : 'Create Account';
  form.addEventListener('submit', function(e){
    e.preventDefault();
    showAuthFormError('authError', null);
    setFieldState('fieldEmail', null, '');
    setFieldState('fieldPassword', null, '');
    if(!isLogin){ setFieldState('fieldPassword2', null, ''); }

    var email = document.getElementById('authEmail').value.trim();
    var password = document.getElementById('authPassword').value;
    var valid = true;
    if(!email){ setFieldState('fieldEmail', 'invalid', 'Email is required.'); valid = false; }
    else if(!EMAIL_RE.test(email)){ setFieldState('fieldEmail', 'invalid', 'Enter a valid email address.'); valid = false; }
    if(!password){ setFieldState('fieldPassword', 'invalid', 'Password is required.'); valid = false; }
    else if(!isLogin && password.length < 8){ setFieldState('fieldPassword', 'invalid', 'Use at least 8 characters.'); valid = false; }

    var body;
    if(isLogin){
      body = {email: email, password: password};
    }else{
      var password2 = document.getElementById('authPassword2').value;
      if(password2 !== password){ setFieldState('fieldPassword2', 'invalid', 'Passwords don\'t match.'); valid = false; }
      var termsEl = document.getElementById('authAcceptTerms');
      if(!termsEl || !termsEl.checked){
        showAuthFormError('authError', 'Please agree to the Terms of Service, Privacy Policy, and Medical Disclaimer to continue.');
        valid = false;
      }
      body = {
        email: email,
        password: password,
        display_name: (document.getElementById('authDisplayName').value.trim() || null),
        accepted_terms: true
      };
    }
    if(!valid) return;

    setBtnLoading(submitBtn, true, isLogin ? 'Logging in…' : 'Creating account…', idleLabel);
    fetch(API_BASE + (isLogin ? '/api/v1/auth/login' : '/api/v1/auth/register'), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify(body)
    })
      .then(function(r){ return r.json().then(function(data){ return {ok: r.ok, data: data}; }); })
      .then(function(res){
        if(!res.ok){ throw new Error(extractErrorMessage(res.data, 'Something went wrong.')); }
        S.authToken = res.data.access_token;
        S.currentUser = res.data.user;
        saveToken(S.authToken);
        saveRefreshToken(res.data.refresh_token);
        updateAccountUI();
        var wasGate = S.authGate;
        S.authGate = false;
        closeModal();
        if(wasGate){ showInitialScreen(); }
        if(typeof showToast === 'function'){
          showToast(isLogin ? ('Welcome back' + (S.currentUser.display_name ? ', '+S.currentUser.display_name : '') + '.') : 'Account created — you\'re all set.');
        }
      })
      .catch(function(err){
        showAuthFormError('authError', err.message || 'Something went wrong.');
        setBtnLoading(submitBtn, false, '', idleLabel);
      });
  });
}
// Forgot-password — request step only. The backend issues a reset token
// and (per auth_service.request_password_reset's docstring) logs it
// server-side rather than emailing it, since no outbound email provider
// is wired up yet; the UI is honest about "if an account exists" instead
// of implying a confirmation-code screen that has nowhere to get its code
// from yet. Reachable from the login form so the flow that already exists
// on the backend isn't stranded with zero UI in front of it.
function openForgotPasswordModal(prefillEmail){
  var overlay = document.getElementById('modalOverlay');
  var content = document.getElementById('modalContent');
  content.innerHTML =
    '<button class="close-btn" id="modalClose">&times;</button>'+
    '<div class="auth-modal">'+
    '<div class="auth-head">'+
      '<div class="auth-badge muted">'+AUTH_ICONS.keyIcon+'</div>'+
      '<div class="eyebrow">Account Recovery</div>'+
      '<h3>Reset Password</h3>'+
      '<div class="modal-sub">Enter your email and we\'ll send a reset link if an account exists.</div>'+
    '</div>'+
    '<form id="forgotForm" novalidate>'+
    '<div class="auth-error-box" id="forgotError"></div>'+
    '<div id="forgotSuccess"></div>'+
    '<div class="field" id="fieldForgotEmail">'+
    '<label for="forgotEmail">Email</label>'+
    '<div class="input-wrap">'+AUTH_ICONS.mail+
    '<input type="email" id="forgotEmail" placeholder="you@example.com" autocomplete="email" value="'+esc(prefillEmail || '')+'">'+
    '</div><div class="field-msg"></div></div>'+
    '<button type="submit" class="btn" id="forgotSubmit" style="width:100%;">Send Reset Link</button>'+
    '<div class="auth-switch-row"><a href="#" id="forgotBackToLogin">Back to log in</a></div>'+
    '</form></div>';
  overlay.classList.add('active');
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('forgotBackToLogin').addEventListener('click', function(e){
    e.preventDefault();
    openAuthModal('login', S.authGate);
  });
  var form = document.getElementById('forgotForm');
  var submitBtn = document.getElementById('forgotSubmit');
  form.addEventListener('submit', function(e){
    e.preventDefault();
    showAuthFormError('forgotError', null);
    setFieldState('fieldForgotEmail', null, '');
    var email = document.getElementById('forgotEmail').value.trim();
    if(!email || !EMAIL_RE.test(email)){
      setFieldState('fieldForgotEmail', 'invalid', 'Enter a valid email address.');
      return;
    }
    setBtnLoading(submitBtn, true, 'Sending…', 'Send Reset Link');
    fetch(API_BASE + '/api/v1/auth/password-reset/request', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({email: email})
    })
      .then(function(r){ return r.json().then(function(data){ return {ok: r.ok, data: data}; }).catch(function(){ return {ok: r.ok, data: {}}; }); })
      .then(function(res){
        if(!res.ok){ throw new Error(extractErrorMessage(res.data, 'Something went wrong.')); }
        document.getElementById('forgotSuccess').innerHTML =
          '<div class="auth-success-box">'+AUTH_ICONS.check+'<span>If an account exists for <b>'+esc(email)+'</b>, a reset link has been sent.</span></div>';
        document.getElementById('fieldForgotEmail').style.display = 'none';
        submitBtn.style.display = 'none';
      })
      .catch(function(err){
        showAuthFormError('forgotError', err.message || 'Something went wrong.');
        setBtnLoading(submitBtn, false, '', 'Send Reset Link');
      });
  });
}
// Small profile panel — view/edit the fields generate-workout/generate-
// program prefill from (see backend's _apply_profile_defaults), plus
// logout. Opens in the same shared modal.
function initials(u){
  var src = (u.display_name || u.email || '?').trim();
  var parts = src.split(/\s+/).filter(Boolean);
  if(parts.length >= 2){ return (parts[0][0] + parts[1][0]).toUpperCase(); }
  return src.slice(0, 2).toUpperCase();
}
function openAccountModal(){
  var overlay = document.getElementById('modalOverlay');
  var content = document.getElementById('modalContent');
  var u = S.currentUser;
  if(!u){ openAuthModal('login'); return; }
  content.innerHTML =
    '<button class="close-btn" id="modalClose">&times;</button>'+
    '<div class="account-identity">'+
    '<div class="avatar-badge">'+esc(initials(u))+'</div>'+
    '<div><h3>'+esc(u.display_name || u.email)+'</h3>'+
    '<div class="modal-sub">'+esc(u.email)+'</div></div>'+
    '</div>'+
    '<div class="modal-section">'+
    '<p class="account-note">Your saved sport, experience level, equipment, and injuries prefill new sessions/programs automatically whenever you don\'t set them explicitly. Update them from the Setup/Program wizards — this just signs you out.</p>'+
    '<button class="btn secondary" id="authLogout" style="width:100%;">Log Out</button>'+
    '<div class="danger-zone">'+
    '<div class="danger-zone-label">'+AUTH_ICONS.alert+'<span>Danger Zone</span></div>'+
    '<p>Deleting your account permanently removes your profile, saved workouts, saved programs, and session history. This cannot be undone.</p>'+
    '<button class="btn secondary danger" id="authDeleteAccount" style="width:100%;">'+AUTH_ICONS.trash+' Delete Account</button>'+
    '</div>'+
    '</div>';
  overlay.classList.add('active');
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('authLogout').addEventListener('click', function(){
    var name = u.display_name || null;
    logout();
    closeModal();
    if(typeof showToast === 'function'){ showToast('Logged out' + (name ? ' — see you soon, '+name+'.' : '.')); }
  });
  document.getElementById('authDeleteAccount').addEventListener('click', function(){
    openDeleteAccountConfirm();
  });
}
// Two-step confirmation (typed email match) before the irreversible
// DELETE /api/v1/auth/me call - a single "Are you sure?" is too easy to
// click through by accident given what this destroys (see modal copy).
// The submit button stays disabled until the typed email matches exactly,
// so the destructive action can't be clicked before it's actually armed.
function openDeleteAccountConfirm(){
  var overlay = document.getElementById('modalOverlay');
  var content = document.getElementById('modalContent');
  var u = S.currentUser;
  content.innerHTML =
    '<button class="close-btn" id="modalClose">&times;</button>'+
    '<div class="auth-modal">'+
    '<div class="auth-head">'+
      '<div class="auth-badge danger">'+AUTH_ICONS.trash+'</div>'+
      '<div class="eyebrow">Irreversible</div>'+
      '<h3>Delete Account</h3>'+
      '<div class="modal-sub">This permanently deletes your account, profile, saved workouts, saved programs, and session history.</div>'+
    '</div>'+
    '<form id="deleteConfirmForm" novalidate>'+
    '<div class="auth-error-box" id="deleteConfirmError"></div>'+
    '<p class="account-note" style="margin-top:-4px;">Type your email (<b>'+esc(u.email)+'</b>) to confirm.</p>'+
    '<div class="field" id="fieldDeleteEmail">'+
    '<label for="deleteConfirmEmail">Confirm Email</label>'+
    '<div class="input-wrap">'+AUTH_ICONS.mail+
    '<input type="email" id="deleteConfirmEmail" placeholder="'+esc(u.email)+'" autocomplete="off">'+
    '</div></div>'+
    '<button type="submit" class="btn secondary danger" id="deleteConfirmSubmit" style="width:100%;" disabled>'+AUTH_ICONS.trash+' Permanently Delete My Account</button>'+
    '<button type="button" class="btn secondary" id="deleteConfirmCancel" style="width:100%;margin-top:8px;">Cancel</button>'+
    '</form></div>';
  overlay.classList.add('active');
  document.getElementById('modalClose').addEventListener('click', closeModal);
  document.getElementById('deleteConfirmCancel').addEventListener('click', function(){
    openAccountModal();
  });
  var emailInput = document.getElementById('deleteConfirmEmail');
  var form = document.getElementById('deleteConfirmForm');
  var submitBtn = document.getElementById('deleteConfirmSubmit');
  emailInput.addEventListener('input', function(){
    var matches = emailInput.value.trim().toLowerCase() === u.email.toLowerCase();
    submitBtn.disabled = !matches;
    setFieldState('fieldDeleteEmail', matches ? 'valid' : null, '');
  });
  form.addEventListener('submit', function(e){
    e.preventDefault();
    var typed = emailInput.value.trim().toLowerCase();
    showAuthFormError('deleteConfirmError', null);
    if(typed !== u.email.toLowerCase()){
      setFieldState('fieldDeleteEmail', 'invalid', 'Email doesn\'t match — type it exactly to confirm.');
      return;
    }
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="btn-spinner"></span>Deleting…';
    fetch(API_BASE + '/api/v1/auth/me', {
      method: 'DELETE',
      headers: authHeaders()
    }).then(function(r){
      if(!r.ok && r.status !== 204){ throw new Error('Something went wrong deleting your account.'); }
      logout();
      closeModal();
      if(typeof showToast === 'function'){ showToast('Your account has been permanently deleted.'); }
    }).catch(function(err){
      showAuthFormError('deleteConfirmError', err.message || 'Something went wrong.');
      submitBtn.disabled = false;
      submitBtn.innerHTML = AUTH_ICONS.trash + ' Permanently Delete My Account';
    });
  });
}

