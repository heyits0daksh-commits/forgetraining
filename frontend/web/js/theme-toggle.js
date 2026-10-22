'use strict';

// ============================================================
// THEME TOGGLE
// ============================================================

(function initTheme(){
  var btn = document.getElementById('themeToggle');
  var moon = document.getElementById('themeIconMoon');
  var sun = document.getElementById('themeIconSun');
  function reflect(theme){
    if(moon && sun){
      moon.style.display = theme === 'dark' ? '' : 'none';
      sun.style.display = theme === 'light' ? '' : 'none';
    }
  }
  reflect(document.documentElement.getAttribute('data-theme') || 'dark');
  if(btn){
    btn.addEventListener('click', function(){
      var current = document.documentElement.getAttribute('data-theme') || 'dark';
      var next = current === 'dark' ? 'light' : 'dark';
      document.documentElement.setAttribute('data-theme', next);
      reflect(next);
      try{ localStorage.setItem('forge_theme', next); }catch(e){}
    });
  }
})();

