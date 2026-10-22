'use strict';

// ============================================================
// TRENDS DASHBOARD — the top half of the Progress tab (screen-progress).
// Everything here is derived client-side from fetchHistory() - the same
// session records History/Calendar already use - so no backend schema
// change was needed for volume/reps/sets. The one thing genuinely not
// trackable yet is session *duration* (no start/end timestamp is stored
// anywhere in a session record), so unlike some reference dashboards this
// doesn't show a time-logged stat - that would have to be invented.
//
// "Muscle Groups" is an approximation: exercises.json has no single
// muscle-group field, only fine-grained movement `category` (e.g.
// "Horizontal Push", "Vertical Pull"). CATEGORY_TO_MUSCLE_GROUP buckets
// those categories into the coarse groups people actually think in terms
// of. It's a best-effort mapping, not a physiology model.
// ============================================================

var CATEGORY_TO_MUSCLE_GROUP = {
  'Horizontal Push': 'Chest',
  'Vertical Push':   'Shoulders',
  'Horizontal Pull': 'Back',
  'Vertical Pull':   'Back',
  'Pull':            'Arms',
  'Squat':           'Legs',
  'Hinge':           'Legs',
  'Calf Raise':      'Legs',
  'Jump':            'Legs',
  'Core':            'Core',
  'Rotational':      'Core',
  'Grip':            'Arms',
  'Carry':           'Full Body',
  'Conditioning':    'Full Body',
  'Full Body':       'Full Body',
  'Power':           'Full Body',
  'Sport Specific':  'Full Body'
};
var MUSCLE_GROUP_ORDER = ['Chest','Back','Shoulders','Legs','Arms','Core','Full Body'];

var _trendVolumeChartInstance = null;
var _trendMuscleChartInstance = null;

function _periodDays(period){ return {'7d':7, '1m':30, '3m':90, 'all':null}[period]; }

function _filterByPeriod(hist, period, endMs){
  var days = _periodDays(period);
  if(days == null) return hist.slice();
  var cutoff = endMs - days * 86400000;
  return hist.filter(function(r){ var t = new Date(r.date).getTime(); return t > cutoff && t <= endMs; });
}

function _sessionVolumeKg(record){
  var total = 0;
  (record.log || []).forEach(function(entry){ (entry.sets || []).forEach(function(s){ total += (s.weight||0) * (s.reps||0); }); });
  return total;
}
function _sessionReps(record){
  var total = 0;
  (record.log || []).forEach(function(entry){ (entry.sets || []).forEach(function(s){ total += (s.reps||0); }); });
  return total;
}
function _sessionSets(record){
  var total = 0;
  (record.log || []).forEach(function(entry){ total += (entry.sets || []).length; });
  return total;
}

// metric: 'reps' | 'sets' | 'volume' — accumulated per muscle-group bucket
// across every logged set in `hist`, matching each log entry's exId back
// to that same session's `exercises` list to find its category (session
// records carry both - see results-render.js's btnSaveSession handler).
function _muscleGroupTotals(hist, metric){
  var totals = {}; MUSCLE_GROUP_ORDER.forEach(function(g){ totals[g] = 0; });
  hist.forEach(function(record){
    var catById = {};
    (record.exercises || []).forEach(function(ex){ catById[ex.id] = ex.category; });
    (record.log || []).forEach(function(entry){
      var group = CATEGORY_TO_MUSCLE_GROUP[catById[entry.exId]] || null;
      if(!group) return;
      (entry.sets || []).forEach(function(s){
        if(metric === 'reps') totals[group] += (s.reps||0);
        else if(metric === 'sets') totals[group] += 1;
        else totals[group] += (s.weight||0) * (s.reps||0);
      });
    });
  });
  return totals;
}

function renderTrendsDashboard(){
  var el = document.getElementById('trendsDashboard');
  if(!el) return;
  el.innerHTML = '<div class="modal-loading">Loading your history…</div>';

  fetchHistory(function(histRaw){
    var hist = histRaw.slice().sort(function(a,b){ return new Date(a.date) - new Date(b.date); });

    if(!hist.length){
      el.innerHTML = '<div class="empty-state">'+
        '<svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3v18h18"/><path d="M7 15l4-6 4 3 5-8"/></svg>'+
        'No sessions logged yet. Once you save a session, your trends show up here.</div>';
      return;
    }

    var period = S.trendPeriod || '1m';
    var mgMetric = S.trendMgMetric || 'reps';
    _paintTrendsDashboard(el, hist, period, mgMetric);
  });
}

function _paintTrendsDashboard(el, hist, period, mgMetric){
  var now = Date.now();
  var filtered = _filterByPeriod(hist, period, now);
  var days = _periodDays(period);

  var workouts = filtered.length;
  var volumeTotal = filtered.reduce(function(sum, r){ return sum + _sessionVolumeKg(r); }, 0);
  var repsTotal = filtered.reduce(function(sum, r){ return sum + _sessionReps(r); }, 0);
  var setsTotal = filtered.reduce(function(sum, r){ return sum + _sessionSets(r); }, 0);

  // Previous period of the same length, for the "vs last period" delta -
  // "all time" has no meaningful previous period, so that comparison is
  // just hidden rather than showing a fabricated 0%/∞.
  var deltaPct = null;
  if(days != null){
    var prevEnd = now - days * 86400000;
    var prevFiltered = _filterByPeriod(hist, period, prevEnd);
    var prevVolume = prevFiltered.reduce(function(sum, r){ return sum + _sessionVolumeKg(r); }, 0);
    if(prevVolume > 0){ deltaPct = Math.round(((volumeTotal - prevVolume) / prevVolume) * 100); }
    else if(volumeTotal > 0){ deltaPct = 100; }
  }

  var unit = weightUnitSuffix();
  var toDisplay = function(kg){ return S.unit === 'lb' ? kgToLb(kg) : kg; };
  var fmtVol = function(kg){
    var v = toDisplay(kg);
    return (v >= 1000 ? (Math.round(v/100)/10) + 'k' : Math.round(v)) + ' ' + unit;
  };

  el.innerHTML =
    '<div class="trend-period-row"><h3>Overview</h3>'+
      '<div class="trend-chips" id="trendPeriodChips">'+
        ['7d','1m','3m','all'].map(function(p){
          var label = {'7d':'7 Days','1m':'1 Month','3m':'3 Months','all':'All Time'}[p];
          return '<button type="button" data-trend-period="'+p+'" class="'+(p===period?'active':'')+'">'+label+'</button>';
        }).join('')+
      '</div>'+
    '</div>'+
    '<div class="stat-grid">'+
      '<div class="stat-card"><div class="stat-label">Workouts</div><div class="stat-value">'+workouts+'</div></div>'+
      '<div class="stat-card"><div class="stat-label">Volume Lifted</div><div class="stat-value">'+fmtVol(volumeTotal)+'</div></div>'+
      '<div class="stat-card"><div class="stat-label">Total Reps</div><div class="stat-value">'+repsTotal+'</div></div>'+
      '<div class="stat-card"><div class="stat-label">Total Sets</div><div class="stat-value">'+setsTotal+'</div></div>'+
    '</div>'+
    '<div class="card" style="margin-bottom:20px;">'+
      '<div class="trend-section-title">Workout Volume Trend</div>'+
      '<div class="trend-section-sub">Total weight lifted per session'+(S.unit==='lb'?'':' (kg)')+'</div>'+
      (workouts ? '<canvas id="trendVolumeCanvas" height="180"></canvas>' : '<div class="empty">No sessions in this period.</div>')+
      (workouts ? (
        '<div class="trend-summary-row">'+
          '<div class="ts-item"><div class="ts-label">Avg</div><div class="ts-value">'+fmtVol(volumeTotal/workouts)+'</div></div>'+
          '<div class="ts-item"><div class="ts-label">Best</div><div class="ts-value">'+fmtVol(Math.max.apply(null, filtered.map(_sessionVolumeKg)))+'</div></div>'+
          (deltaPct != null ? '<div class="ts-item"><div class="ts-label">vs last period</div><div class="ts-delta '+(deltaPct>=0?'up':'down')+'">'+(deltaPct>=0?'▲ +':'▼ ')+deltaPct+'%</div></div>' : '')+
        '</div>'
      ) : '')+
    '</div>'+
    '<div class="card">'+
      '<div class="trend-section-title">Muscle Groups</div>'+
      '<div class="trend-section-sub">Approximate — grouped from each exercise\'s movement category, not a per-muscle tracker.</div>'+
      '<div class="mg-tabs" id="trendMgTabs">'+
        ['reps','sets','volume'].map(function(m){
          return '<button type="button" data-trend-mg="'+m+'" class="'+(m===mgMetric?'active':'')+'">'+(m.charAt(0).toUpperCase()+m.slice(1))+'</button>';
        }).join('')+
      '</div>'+
      '<canvas id="trendMuscleCanvas" height="220"></canvas>'+
    '</div>';

  document.querySelectorAll('#trendPeriodChips button').forEach(function(btn){
    btn.addEventListener('click', function(){
      S.trendPeriod = btn.getAttribute('data-trend-period');
      _paintTrendsDashboard(el, hist, S.trendPeriod, mgMetric);
    });
  });
  document.querySelectorAll('#trendMgTabs button').forEach(function(btn){
    btn.addEventListener('click', function(){
      S.trendMgMetric = btn.getAttribute('data-trend-mg');
      _paintTrendsDashboard(el, hist, period, S.trendMgMetric);
    });
  });

  if(workouts) _drawVolumeChart(filtered, toDisplay, unit);
  _drawMuscleChart(hist, mgMetric);
}

function _drawVolumeChart(filtered, toDisplay, unit){
  var ctx = document.getElementById('trendVolumeCanvas');
  if(!ctx) return;
  // Chart.js is inlined directly in index.html's <head> (no <script src>,
  // no separate file, no external CDN request at all) so this should
  // always be defined by the time we get here - but the guard stays as a
  // defensive fallback: if it's ever missing, this used to just `return`, leaving
  // the canvas element sitting there empty with no error and no message
  // (exactly the blank "Workout Volume Trend" card users were seeing -
  // not a data bug, the volume numbers above it were already correct,
  // just nothing ever got drawn into the canvas). Matches the fallback
  // progress-chart.js already shows for the same failure mode instead of
  // failing silently.
  if(typeof Chart === 'undefined'){
    ctx.replaceWith(_chartUnavailableEl());
    return;
  }
  if(_trendVolumeChartInstance){ _trendVolumeChartInstance.destroy(); }
  var labels = filtered.map(function(r){ return new Date(r.date).toLocaleDateString(undefined, {month:'short', day:'numeric'}); });
  var data = filtered.map(function(r){ return toDisplay(_sessionVolumeKg(r)); });
  _trendVolumeChartInstance = new Chart(ctx, {
    type: 'line',
    data: { labels: labels, datasets: [{
      data: data, borderColor: '#c3e85e', backgroundColor: 'rgba(195,232,94,0.15)',
      tension: 0.35, fill: true, pointRadius: 4, pointBackgroundColor: '#0A0A0B', pointBorderColor: '#c3e85e', pointBorderWidth: 2
    }] },
    options: {
      responsive: true,
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: function(item){ return Math.round(item.parsed.y) + ' ' + unit; } } } },
      scales: {
        x: { ticks: { color: '#9a9aa5' }, grid: { display: false } },
        y: { ticks: { color: '#9a9aa5' }, grid: { color: 'rgba(255,255,255,0.06)' } }
      }
    }
  });
}

function _chartUnavailableEl(){
  var el = document.createElement('div');
  el.className = 'empty';
  el.textContent = 'Chart could not load — check your connection and try again.';
  return el;
}

function _drawMuscleChart(hist, metric){
  var ctx = document.getElementById('trendMuscleCanvas');
  if(!ctx) return;
  if(typeof Chart === 'undefined'){
    ctx.replaceWith(_chartUnavailableEl());
    return;
  }
  if(_trendMuscleChartInstance){ _trendMuscleChartInstance.destroy(); }
  var totals = _muscleGroupTotals(hist, metric);
  var toDisplay = function(v){ return metric === 'volume' ? (S.unit === 'lb' ? kgToLb(v) : v) : v; };
  var data = MUSCLE_GROUP_ORDER.map(function(g){ return Math.round(toDisplay(totals[g])); });

  if(!data.some(function(v){ return v > 0; })){
    ctx.parentNode.querySelectorAll('.empty').forEach(function(n){ n.remove(); });
    var emptyMsg = document.createElement('div');
    emptyMsg.className = 'empty';
    emptyMsg.textContent = 'No logged sets to break down yet.';
    ctx.replaceWith(emptyMsg);
    return;
  }

  _trendMuscleChartInstance = new Chart(ctx, {
    type: 'radar',
    data: {
      labels: MUSCLE_GROUP_ORDER,
      datasets: [{
        data: data,
        backgroundColor: 'rgba(199,154,75,0.25)',
        borderColor: '#C79A4B',
        pointBackgroundColor: '#C79A4B',
        pointRadius: 3
      }]
    },
    options: {
      responsive: true,
      plugins: { legend: { display: false } },
      scales: {
        r: {
          angleLines: { color: 'rgba(255,255,255,0.08)' },
          grid: { color: 'rgba(255,255,255,0.08)' },
          pointLabels: { color: '#e8e8ec', font: { size: 11 } },
          ticks: { display: false, beginAtZero: true }
        }
      }
    }
  });
}
