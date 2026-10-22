'use strict';

// ============================================================
// WIZARD (SETUP)
// ============================================================

function renderSetup(){
  var m = S.metadata;

  var nameInput = document.getElementById('bioName');
  if(nameInput){
    nameInput.value = S.athleteName || '';
    nameInput.addEventListener('input', function(){
      S.athleteName = nameInput.value;
      updateWizardNav();
    });
  }

  var dg = document.getElementById('disciplineGrid');
  // "Custom" is appended after the real, data-driven sports rather than
  // mixed into m.sports - it's a UI-only "no discipline" escape hatch, not
  // something the engine actually knows training demands for (see
  // SPORT_THEME's 'Custom' entry for why sending it is still safe).
  dg.innerHTML = m.sports.concat(['Custom']).map(function(sport){
    var t = themeFor(sport);
    var img = firstImg(t);
    var bg = img ? "background-image:url('"+img+"');" : '';
    return '<div class="choice" data-sport="'+esc(sport)+'" style="--accent:'+t.accent+';'+bg+'">'+
      '<span class="checkmark">✓</span>'+
      '<div class="tile-body"><span class="icon">'+esc(t.mono)+'</span><h4>'+esc(sport)+'</h4>'+
      (t.region ? '<span class="region">'+esc(t.region)+'</span>' : '')+'</div>'+
      '</div>';
  }).join('');
  dg.querySelectorAll('.choice').forEach(function(card){
    card.addEventListener('click', function(){
      dg.querySelectorAll('.choice').forEach(function(c){ c.classList.remove('selected'); });
      card.classList.add('selected');
      var prevSport = S.sport;
      S.sport = card.getAttribute('data-sport');
      if(typeof onWizardSportChanged === 'function') onWizardSportChanged(S.sport, prevSport);
      // "Look Jacked" and "Strength + Hypertrophy" are prescription-style
      // modes by definition (see SPORT_THEME) - picking either as a
      // discipline should carry the same training_emphasis nudge the old
      // dedicated home button used to set for "Look Jacked", now extended
      // to its "Strength + Hypertrophy" sibling (see emphasisForSport).
      // Any other discipline clears the nudge back to the default
      // (power/balanced).
      S.emphasis = emphasisForSport(S.sport);
      applyTheme(S.sport);
      // Tapping "Custom" here IS the person saying "no specific
      // discipline" - same intent as flipping the Custom Mode toggle
      // below, which already auto-selects this tile the other way around
      // (see that toggle's own handler). Without this, picking "Custom"
      // straight from the grid left Custom Mode off and silently built an
      // engine-generated (non-custom) session for a "sport" called
      // "Custom" that the engine has no real training profile for.
      var cmtEl = document.getElementById('customModeToggle');
      if(S.sport === 'Custom' && cmtEl && !cmtEl.checked){
        cmtEl.checked = true;
        S.mode = 'custom';
      }
      updateWizardNav();
    });
  });
  // No discipline is pre-selected: the wizard used to auto-click "Special
  // Forces" here on load, which silently picked a discipline before the
  // person had looked at the grid - easy to miss and then generate a
  // program for a sport they never chose. updateWizardNav() already keeps
  // "Next" disabled until S.sport is set, so leaving nothing selected just
  // makes that requirement visible instead of working around it.

  var eg = document.getElementById('experienceGroup');
  eg.innerHTML = m.experience_levels.map(function(lvl){
    var checked = lvl === S.experience ? 'checked' : '';
    return '<label class="'+(lvl===S.experience?'checked':'')+'">'+
      '<input type="radio" name="exp" value="'+esc(lvl)+'" '+checked+'>'+esc(lvl)+'</label>';
  }).join('');
  eg.querySelectorAll('input').forEach(function(inp){
    inp.addEventListener('change', function(){
      S.experience = inp.value;
      eg.querySelectorAll('label').forEach(function(l){ l.classList.remove('checked'); });
      inp.closest('label').classList.add('checked');
    });
  });

  // Readiness is now calculated from the "how are you feeling" recovery
  // inputs below (sleep/soreness/stress/energy/motivation) instead of a
  // bare 1-100 slider the person had to guess a number for. The old raw
  // slider still exists (#readinessInput, hidden) purely as the value
  // S.readiness actually reads from downstream (generate.js, review, PR
  // suggestions) so nothing else has to change. A visible manual override
  // slider (#readinessManualInput) lets someone bypass the calculation
  // entirely if they'd rather just set a number themselves.
  var ri = document.getElementById('readinessInput');
  ri.value = S.readiness;
  S.readinessManual = false;
  recalcReadinessFromRecovery();

  wireRecoverySlider('riSleep', 'riSleepReadout', function(v){ return v+'h'; });
  wireRecoverySlider('riSoreness', 'riSorenessReadout', function(v){ return v+'/5'; });
  wireRecoverySlider('riStress', 'riStressReadout', function(v){ return v+'/5'; });
  wireRecoverySlider('riEnergy', 'riEnergyReadout', function(v){ return v+'/5'; });
  wireRecoverySlider('riMotivation', 'riMotivationReadout', function(v){ return v+'/5'; });
  ['riSleep','riSoreness','riStress','riEnergy','riMotivation'].forEach(function(id){
    document.getElementById(id).addEventListener('input', function(){
      if(!S.readinessManual) recalcReadinessFromRecovery();
      clearQuickFeelSelection();
    });
  });
  wireQuickFeelPresets();

  var rmi = document.getElementById('readinessManualInput');
  rmi.value = S.readiness;
  document.getElementById('readinessManualReadout').textContent = rmi.value + '%';
  rmi.addEventListener('input', function(){
    S.readinessManual = true;
    S.readiness = parseInt(rmi.value, 10);
    document.getElementById('readinessManualReadout').textContent = rmi.value + '%';
    ri.value = S.readiness;
    updateReadinessUI();
  });

  populateConditioningSelect('conditioningEmphasis', 'conditioningEmphasisHint', S.conditioningEmphasis, function(v){
    S.conditioningEmphasis = v;
  });

  var sd = document.getElementById('sessionDuration');
  sd.value = String(S.sessionDuration);
  sd.addEventListener('change', function(){
    S.sessionDuration = parseInt(sd.value, 10) || 60;
  });

  var eqEl = document.getElementById('equipmentChecks');
  S.equipment.add('Bodyweight');
  renderEquipmentGroups(eqEl, S.equipment, S.equipmentCatalog);

  renderInjuryBrowser();

  var cmt = document.getElementById('customModeToggle');
  cmt.checked = S.mode === 'custom';
  cmt.addEventListener('change', function(){
    S.mode = cmt.checked ? 'custom' : 'preset';
    // Flipping Custom Mode on is itself "I don't want to pick a discipline" -
    // auto-select the grid's 'Custom' tile (only if nothing real was already
    // chosen) so the toggle alone unlocks Next, instead of also making the
    // person separately click a tile in disciplineGrid above.
    if(cmt.checked && !S.sport){
      S.sport = 'Custom';
      S.emphasis = null;
      applyTheme(S.sport);
      dg.querySelectorAll('.choice').forEach(function(c){
        c.classList.toggle('selected', c.getAttribute('data-sport') === 'Custom');
      });
    }
    updateWizardNav();
  });

  // Recovery inputs (sleep/soreness/stress/energy/motivation) are always
  // visible now and drive the readiness calculation directly - see
  // recalcReadinessFromRecovery() wiring above, no separate enable toggle.

  var exSearch = document.getElementById('exPickerSearch');
  exSearch.value = S.exPickerQuery;
  var exSearchTimer = null;
  exSearch.addEventListener('input', function(){
    S.exPickerQuery = exSearch.value;
    clearTimeout(exSearchTimer);
    exSearchTimer = setTimeout(renderExercisePicker, 250);
  });

  goToStep(1);
}
// One-tap mood presets over the same 5 sliders recalcReadinessFromRecovery()
// already reads - this is a simpler default entry point layered on top of
// the existing fine-grained control, not a second source of truth. Tapping
// a preset sets all 5 sliders (and their readouts) to a sensible combo,
// then reuses the exact same recalc/update path a manual slider drag would
// have triggered, so downstream behavior (S.readiness, deload warning,
// review screen) is identical either way.
var QUICK_FEEL_PRESETS = {
  great:    { riSleep: 8.5, riSoreness: 1, riStress: 1, riEnergy: 5, riMotivation: 5 },
  good:     { riSleep: 7,   riSoreness: 2, riStress: 2, riEnergy: 4, riMotivation: 4 },
  okay:     { riSleep: 6,   riSoreness: 3, riStress: 3, riEnergy: 3, riMotivation: 3 },
  rough:    { riSleep: 5,   riSoreness: 4, riStress: 4, riEnergy: 2, riMotivation: 2 },
  terrible: { riSleep: 4,   riSoreness: 5, riStress: 5, riEnergy: 1, riMotivation: 1 }
};
var QUICK_FEEL_FORMATS = {
  riSleep: function(v){ return v+'h'; },
  riSoreness: function(v){ return v+'/5'; },
  riStress: function(v){ return v+'/5'; },
  riEnergy: function(v){ return v+'/5'; },
  riMotivation: function(v){ return v+'/5'; }
};
function wireQuickFeelPresets(){
  var row = document.getElementById('quickFeelRow');
  if(!row) return;
  row.querySelectorAll('.quick-feel-btn').forEach(function(btn){
    btn.addEventListener('click', function(){
      var preset = QUICK_FEEL_PRESETS[btn.getAttribute('data-preset')];
      if(!preset) return;
      row.querySelectorAll('.quick-feel-btn').forEach(function(b){ b.classList.remove('selected'); });
      btn.classList.add('selected');
      Object.keys(preset).forEach(function(id){
        var input = document.getElementById(id);
        var readout = document.getElementById(id+'Readout');
        if(!input) return;
        input.value = preset[id];
        if(readout) readout.textContent = QUICK_FEEL_FORMATS[id](preset[id]);
      });
      if(!S.readinessManual) recalcReadinessFromRecovery();
    });
  });
}
function clearQuickFeelSelection(){
  var row = document.getElementById('quickFeelRow');
  if(row){ row.querySelectorAll('.quick-feel-btn').forEach(function(b){ b.classList.remove('selected'); }); }
}
function wireRecoverySlider(inputId, readoutId, format){
  var input = document.getElementById(inputId);
  var readout = document.getElementById(readoutId);
  readout.textContent = format(input.value);
  input.addEventListener('input', function(){ readout.textContent = format(input.value); });
}
// Turns the five "how are you feeling" sliders into a single 0-100
// readiness number - same shape as the backend's own post-session
// soreness_score formula ((5-soreness)/4*100) in readiness_service.py, so
// the two stay conceptually consistent even though this one runs
// client-side on today's pre-session inputs rather than session history.
// Only runs while S.readinessManual is false - once someone opens the
// advanced override and drags it themselves, their number stands until
// the wizard is reopened.
function recalcReadinessFromRecovery(){
  var sleepH = parseFloat(document.getElementById('riSleep').value);
  var soreness = parseFloat(document.getElementById('riSoreness').value);
  var stress = parseFloat(document.getElementById('riStress').value);
  var energy = parseFloat(document.getElementById('riEnergy').value);
  var motivation = parseFloat(document.getElementById('riMotivation').value);
  var sleepScore = Math.min(sleepH / 8, 1) * 100;
  var sorenessScore = (5 - soreness) / 4 * 100;
  var stressScore = (5 - stress) / 4 * 100;
  var energyScore = (energy - 1) / 4 * 100;
  var motivationScore = (motivation - 1) / 4 * 100;
  var score = Math.round((sleepScore + sorenessScore + stressScore + energyScore + motivationScore) / 5);
  S.readiness = Math.max(1, Math.min(100, score));
  document.getElementById('readinessInput').value = S.readiness;
  var rmi = document.getElementById('readinessManualInput');
  if(rmi){ rmi.value = S.readiness; document.getElementById('readinessManualReadout').textContent = S.readiness + '%'; }
  updateReadinessUI();
}

