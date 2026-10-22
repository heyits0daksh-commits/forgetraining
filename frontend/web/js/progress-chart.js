'use strict';

// ============================================================
// EXERCISE PROGRESS CHART — reuses fetchHistory (history.js) rather than
// a dedicated endpoint: session history already carries every logged set
// per exercise (record.log[i] = {exId, name, sets:[{weight,reps,isPR}]}),
// so building a per-exercise trend is a client-side filter/reduce over
// data the app already fetches for the History tab. Kept in its own file
// (rather than folded into exercise-modal.js) since it owns a Chart.js
// instance that needs explicit teardown on modal close.
//
// Used from two places now: the exercise knowledge-graph modal (single
// exercise, wrap id "progressChartWrap") and the standalone Progress tab
// (progress-page.js, wrap id "progressPageChartWrap") - both pass their
// own wrapId in so the two never fight over the same <canvas>.
// ============================================================

var _progressChartInstance = null;

// Best set of a given exercise within one session, by the same Epley-ish
// score pr-suggestion.js already uses for PR detection — keeps "what
// counts as your best set that day" consistent across the app instead of
// inventing a second definition just for the chart.
function _bestSetForExercise(record, exId){
  var entry = (record.log || []).find(function(l){ return l.exId === exId; });
  if(!entry || !entry.sets || !entry.sets.length) return null;
  var best = entry.sets[0];
  var bestScore = computeScore(best.weight, best.reps);
  entry.sets.forEach(function(s){
    var sc = computeScore(s.weight, s.reps);
    if(sc > bestScore){ best = s; bestScore = sc; }
  });
  return {weight: best.weight, reps: best.reps, score: bestScore};
}

function weightUnitSuffix(){ return S.unit === 'lb' ? 'lb' : 'kg'; }

// isDumbbell: true when this exercise's equipment is "Dumbbell" - every
// weight logged for it (see the logrow inputs in exercise-editing.js /
// program-wizard-steps.js) is a single hand's load, not a combined total,
// so the chart says so explicitly instead of showing a bare kg/lb number
// that reads like a total load the way a Barbell exercise's would.
function renderExerciseProgressChart(exId, exName, isDumbbell, wrapId){
  wrapId = wrapId || 'progressChartWrap';
  var wrap = document.getElementById(wrapId);
  if(!wrap) return;
  wrap.innerHTML = '<div class="modal-loading">Loading your history…</div>';

  fetchHistory(function(hist){
    var points = hist
      .slice()
      .sort(function(a,b){ return new Date(a.date) - new Date(b.date); })
      .map(function(record){
        var best = _bestSetForExercise(record, exId);
        return best ? {date: record.date, weight: best.weight, reps: best.reps, score: best.score} : null;
      })
      .filter(Boolean);

    if(!points.length){
      wrap.innerHTML = '<div class="empty">No logged sets for this exercise yet.</div>';
      return;
    }
    if(points.length < 2){
      wrap.innerHTML = '<div class="empty">Log this exercise in at least 2 sessions to see a progress chart.</div>';
      return;
    }

    var canvasId = wrapId + 'Canvas';
    wrap.innerHTML = '<canvas id="'+canvasId+'" height="180"></canvas>';
    var ctx = document.getElementById(canvasId);
    if(!ctx || typeof Chart === 'undefined'){
      wrap.innerHTML = '<div class="empty">Chart could not load — check your connection and try again.</div>';
      return;
    }
    if(_progressChartInstance){ _progressChartInstance.destroy(); }

    var labels = points.map(function(p){ return new Date(p.date).toLocaleDateString(undefined, {month:'short', day:'numeric'}); });
    var weights = points.map(function(p){ return S.unit === 'lb' ? kgToLb(p.weight) : p.weight; });
    var reps = points.map(function(p){ return p.reps; });
    var unitLabel = weightUnitSuffix();
    var weightWord = isDumbbell ? unitLabel + ' each hand' : unitLabel;

    _progressChartInstance = new Chart(ctx, {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: (exName || 'Exercise') + ' — best set (' + weightWord + ')',
          data: weights,
          borderColor: '#3fb27f',
          backgroundColor: 'rgba(63,178,127,0.15)',
          tension: 0.25,
          fill: true,
          pointRadius: 4
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          title: { display: true, text: (exName || 'Exercise') + ' progress' + (isDumbbell ? ' (each hand)' : ''), color: '#e8e8ec' },
          // Reps ride along in the tooltip rather than a second axis/line -
          // "went up" is about weight, reps are context for why a given
          // point counted as the best set that day.
          tooltip: {
            callbacks: {
              label: function(item){
                var w = item.parsed.y;
                var r = reps[item.dataIndex];
                return w + unitLabel + (isDumbbell ? ' each hand' : '') + ' × ' + r + ' reps';
              }
            }
          }
        },
        scales: {
          x: { ticks: { color: '#9a9aa5' }, grid: { color: 'rgba(255,255,255,0.06)' } },
          y: { ticks: { color: '#9a9aa5' }, grid: { color: 'rgba(255,255,255,0.06)' }, title: { display: true, text: weightWord, color: '#9a9aa5' } }
        }
      }
    });
  });
}

// Chart.js instances hold a canvas reference — closeModal() (exercise-modal.js)
// calls this on every close path (X button, click-outside) so a stale
// instance doesn't leak or draw into a canvas that no longer exists. The
// Progress tab (progress-page.js) also calls this before drawing a new
// selection, for the same reason.
function destroyProgressChart(){
  if(_progressChartInstance){ _progressChartInstance.destroy(); _progressChartInstance = null; }
}
