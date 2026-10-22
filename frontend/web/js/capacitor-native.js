'use strict';

// ============================================================
// NATIVE SHELL — Capacitor integration (see /mobile in the repo root).
//
// This file is loaded on every platform, including plain desktop/mobile
// browsers where window.Capacitor doesn't exist - every function here
// checks isNative() first and no-ops otherwise, so nothing in here can
// break the regular web app. Inside the wrapped iOS/Android app,
// window.Capacitor.Plugins.<Name> is injected automatically by the native
// runtime once the corresponding @capacitor/* package has been synced into
// the native project (npx cap sync) - no bundler or JS import required.
// ============================================================

function isNative(){
  return !!(window.Capacitor && window.Capacitor.isNativePlatform && window.Capacitor.isNativePlatform());
}
function nativePlugin(name){
  return (window.Capacitor && window.Capacitor.Plugins && window.Capacitor.Plugins[name]) || null;
}

// ---------- status bar ----------
// Kept in sync with the app's own theme (--bg) rather than a fixed color,
// so flipping the in-app light/dark toggle (theme-toggle.js) re-colors the
// OS status bar too instead of leaving a mismatched black/white strip.
function syncNativeStatusBar(){
  var StatusBar = nativePlugin('StatusBar');
  if(!isNative() || !StatusBar) return;
  var light = document.documentElement.getAttribute('data-theme') === 'light';
  StatusBar.setStyle({ style: light ? 'LIGHT' : 'DARK' }).catch(function(){});
  StatusBar.setBackgroundColor({ color: light ? '#F3F1EC' : '#0A0A0B' }).catch(function(){});
}

// ---------- splash screen ----------
// launchAutoHide is off in capacitor.config.json so the splash stays up
// (matching --bg, no flash of blank white) until boot() has actually
// finished loading metadata and picked the first real screen to show -
// see the call to this at the end of showInitialScreen() in boot.js.
function hideNativeSplash(){
  var SplashScreen = nativePlugin('SplashScreen');
  if(!isNative() || !SplashScreen) return;
  SplashScreen.hide().catch(function(){});
}

// ---------- haptics ----------
// A light tap on every primary action (buttons, tappable tiles/cards) -
// the single biggest thing that makes a wrapped web app stop feeling like
// a website and start feeling like the rest of the OS. Delegated to one
// listener instead of wiring every button individually.
function wireNativeHaptics(){
  var Haptics = nativePlugin('Haptics');
  if(!isNative() || !Haptics) return;
  document.addEventListener('click', function(e){
    var el = e.target.closest('.btn, .choice, .scope-card, .mainnav button, .quick-feel-btn, .card.scope-card, .tab, .toggle-pill');
    if(!el) return;
    Haptics.impact({ style: 'LIGHT' }).catch(function(){});
  }, { passive: true });
}

// ---------- Android hardware back button ----------
// Without this, Android's back gesture/button exits the whole app from
// anywhere - including mid-wizard, which loses whatever the person just
// filled in. This makes it behave like every other screen's own Back
// button first, and only exits once there's nowhere left to go back to.
function wireNativeBackButton(){
  var App = nativePlugin('App');
  if(!isNative() || !App) return;
  App.addListener('backButton', function(){
    var active = document.querySelector('.screen.active');
    var id = active && active.id;
    if(id === 'screen-setup'){
      document.getElementById('btnWizBack').click();
      return;
    }
    if(id === 'screen-program'){
      var pgBack = document.getElementById('btnPgBack');
      if(pgBack && pgBack.style.visibility !== 'hidden'){ pgBack.click(); return; }
    }
    if(id && id !== 'screen-hero'){
      show('screen-hero');
      return;
    }
    App.exitApp();
  });
}

// ---------- boot ----------
function initNativeShell(){
  if(!isNative()) return;
  // Keeps the two-way binding: theme-toggle.js already updates
  // data-theme + localStorage on click - this just also recolors the OS
  // chrome whenever that happens, in either direction.
  var themeObserver = new MutationObserver(syncNativeStatusBar);
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
  syncNativeStatusBar();
  wireNativeHaptics();
  wireNativeBackButton();
}
initNativeShell();
