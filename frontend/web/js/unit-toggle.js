'use strict';

// ============================================================
// UNIT TOGGLE (kg/lb display)
// ============================================================

(function initUnit(){
  var btn = document.getElementById('unitToggle');
  var label = document.getElementById('unitToggleLabel');
  // S isn't assigned yet at this point in script execution (var S = {...}
  // runs further down) - paint the initial label straight from storage
  // instead of via S, same as initTheme does for data-theme above.
  function reflect(){ if(label) label.textContent = (typeof S !== 'undefined' ? S.unit : loadUnit()) === 'lb' ? 'LB' : 'KG'; }
  if(label) label.textContent = loadUnit() === 'lb' ? 'LB' : 'KG';
  // The biometrics fields (Weight/Bench/Squat/Deadlift, in both the Train
  // wizard and the Program Builder wizard) are plain static inputs, not
  // re-rendered by renderResults/renderProgramWeek/renderHistory below - so
  // unlike the log-weight placeholders, nothing was updating their "(kg)"
  // labels or converting their on-screen values when the toggle flipped.
  // That's the actual "kg to lb converter doesn't work" bug: a person who
  // switches to LB, then types their real bodyweight/1RMs (in lb) into a
  // box still silently labeled "(kg)", gets that number sent straight to
  // the engine as kg with no conversion - a 165 lb lifter becomes a 165 kg
  // (364 lb) one in every downstream BMI/strength-ratio/load calculation.
  // Fix: convert every .unit-weight-input's on-screen value in place (so
  // the underlying real-world quantity is preserved across the switch) and
  // relabel every .unit-label span, every time the toggle fires.
  function convertUnitWeightInputs(oldUnit, newUnit){
    if(oldUnit === newUnit) return;
    document.querySelectorAll('.unit-weight-input').forEach(function(input){
      var raw = parseFloat(input.value);
      if(isNaN(raw)) return;
      var kg = oldUnit === 'lb' ? lbToKg(raw) : raw;
      var converted = newUnit === 'lb' ? kgToLb(kg) : kg;
      input.value = Math.round(converted * 10) / 10;
    });
  }
  function relabelUnitSpans(){
    var txt = S.unit === 'lb' ? 'lb' : 'kg';
    document.querySelectorAll('.unit-label').forEach(function(span){ span.textContent = txt; });
    document.querySelectorAll('.unit-label-height').forEach(function(span){ span.textContent = S.unit === 'lb' ? 'in' : 'cm'; });
  }
  // The Profile step's #bioHeight isn't a .unit-weight-input (it's a length,
  // not a weight) so it needs its own tiny cm<->in conversion, same
  // in-place-on-toggle pattern as convertUnitWeightInputs above.
  function convertUnitHeightInput(oldUnit, newUnit){
    if(oldUnit === newUnit) return;
    var input = document.getElementById('bioHeight');
    if(!input) return;
    var raw = parseFloat(input.value);
    if(isNaN(raw)) return;
    var cm = oldUnit === 'lb' ? inToCm(raw) : raw;
    var converted = newUnit === 'lb' ? cmToIn(cm) : cm;
    input.value = Math.round(converted * 10) / 10;
  }
  // Reflects S.unit onto the Profile step's Metric/Imperial segmented
  // buttons (#bioUnitMetricBtn/#bioUnitImperialBtn) whenever it changes,
  // from wherever it changed — the header toggle, the profile step
  // buttons themselves, or a restored profile.
  function reflectBioUnitButtons(){
    var m = document.getElementById('bioUnitMetricBtn');
    var i = document.getElementById('bioUnitImperialBtn');
    if(m) m.classList.toggle('active', S.unit !== 'lb');
    if(i) i.classList.toggle('active', S.unit === 'lb');
  }
  function setUnit(newUnit){
    var oldUnit = S.unit;
    if(oldUnit === newUnit) return;
    S.unit = newUnit;
    try{ localStorage.setItem(UNIT_KEY, S.unit); }catch(e){}
    reflect();
    convertUnitWeightInputs(oldUnit, S.unit);
    convertUnitHeightInput(oldUnit, S.unit);
    relabelUnitSpans();
    reflectBioUnitButtons();
    // Re-render whatever's currently on screen so the switch is immediate
    // rather than waiting for the next navigation.
    var active = document.querySelector('.screen.active');
    var activeId = active && active.id;
    if(activeId === 'screen-results' && S.lastResult){ renderResults(S.lastResult); }
    else if(activeId === 'screen-program' && S.lastProgram){ renderProgramWeek(S.lastProgram); }
    else if(activeId === 'screen-history'){ renderHistory(); }
  }
  if(btn){
    btn.addEventListener('click', function(){ setUnit(S.unit === 'lb' ? 'kg' : 'lb'); });
  }
  document.addEventListener('DOMContentLoaded', function(){
    reflectBioUnitButtons();
    var mBtn = document.getElementById('bioUnitMetricBtn');
    var iBtn = document.getElementById('bioUnitImperialBtn');
    if(mBtn) mBtn.addEventListener('click', function(){ setUnit('kg'); });
    if(iBtn) iBtn.addEventListener('click', function(){ setUnit('lb'); });
  });
})();

