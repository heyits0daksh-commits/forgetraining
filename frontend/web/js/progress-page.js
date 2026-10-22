'use strict';

// ============================================================
// PROGRESS TAB — a standalone screen (nav-control.js's "progress" tab)
// that puts the per-exercise chart already used inside the exercise
// modal (progress-chart.js) somewhere it doesn't require opening a
// specific exercise first. Builds its exercise picker from whatever the
// person has actually logged (fetchHistory, same source as History/
// Calendar) rather than the full 700+ exercise catalog, since a chart
// only means anything for something with at least one logged set.
// ============================================================

var _progressPageExercises = null; // [{id, name}] — lazily built from history, cached per screen visit
var _progressPageEquipCache = {};  // exId -> equipment string, so switching back to an already-picked exercise skips the knowledge-graph fetch

function renderProgressPage(){
  var body = document.getElementById('progressPageBody');
  if(!body) return;
  body.innerHTML = '<div class="modal-loading">Loading your logged exercises…</div>';

  fetchHistory(function(hist){
    var byId = {};
    hist.forEach(function(record){
      (record.log || []).forEach(function(entry){
        if(entry.exId && entry.name && !byId[entry.exId]) byId[entry.exId] = entry.name;
      });
    });
    _progressPageExercises = Object.keys(byId).map(function(id){ return {id:id, name:byId[id]}; })
      .sort(function(a,b){ return a.name.localeCompare(b.name); });

    if(!_progressPageExercises.length){
      body.innerHTML = '<div class="empty-state">'+
        '<svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 15l4-6 4 3 5-8"/></svg>'+
        'No logged sets yet. Log a set from a session or program day, then come back here to see your trend.</div>';
      return;
    }

    var options = _progressPageExercises.map(function(ex){
      return '<option value="'+esc(ex.id)+'">'+esc(ex.name)+'</option>';
    }).join('');

    body.innerHTML =
      '<div class="card" style="margin-bottom:20px;">'+
        '<label style="display:block;font-size:12px;color:var(--muted);margin-bottom:8px;">Exercise</label>'+
        '<select id="progressPageSelect">'+options+'</select>'+
      '</div>'+
      '<div class="card"><div id="progressPageChartWrap"></div></div>';

    var select = document.getElementById('progressPageSelect');
    // Restore the last-viewed exercise if it's still in the list (e.g. after
    // switching tabs and back), otherwise default to the first one.
    if(S.progressPageExId && byId[S.progressPageExId]){ select.value = S.progressPageExId; }
    select.addEventListener('change', function(){ loadProgressPageChart(select.value, byId[select.value]); });
    loadProgressPageChart(select.value, byId[select.value]);
  });
}

function loadProgressPageChart(exId, exName){
  S.progressPageExId = exId;
  destroyProgressChart();
  if(_progressPageEquipCache.hasOwnProperty(exId)){
    renderExerciseProgressChart(exId, exName, _progressPageEquipCache[exId] === 'Dumbbell', 'progressPageChartWrap');
    return;
  }
  var wrap = document.getElementById('progressPageChartWrap');
  if(wrap) wrap.innerHTML = '<div class="modal-loading">Loading your history…</div>';
  fetch(API_BASE + '/api/v1/knowledge-graph/' + encodeURIComponent(exId))
    .then(function(r){ return r.ok ? r.json() : null; })
    .then(function(data){
      var equip = data && data.equipment;
      _progressPageEquipCache[exId] = equip;
      renderExerciseProgressChart(exId, exName, equip === 'Dumbbell', 'progressPageChartWrap');
    })
    .catch(function(){
      // Knowledge-graph lookup is only needed for the "each hand" label -
      // the chart itself doesn't depend on it, so a failed fetch still
      // renders (just without the dumbbell-specific labeling).
      renderExerciseProgressChart(exId, exName, false, 'progressPageChartWrap');
    });
}
