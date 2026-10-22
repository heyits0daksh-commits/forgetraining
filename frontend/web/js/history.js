'use strict';

// ============================================================
// HISTORY — backend (SQLite, persists across devices) with localStorage
// as an offline cache/fallback so the app still works if the backend is
// unreachable (e.g. opened as a bare file:// page with no server running).
// ============================================================

function loadHistory(){
  try{ return JSON.parse(localStorage.getItem(HISTORY_KEY)) || []; }
  catch(e){ return []; }
}
function saveHistory(arr){
  try{ localStorage.setItem(HISTORY_KEY, JSON.stringify(arr)); }
  catch(e){ /* storage unavailable — ignore */ }
}

// Converts a locally-shaped history record into the backend's
// SessionLogCreate shape and POSTs it. Fire-and-forget by design — saving
// a session should never block or fail in the UI just because the backend
// is momentarily unreachable; the localStorage copy (saveHistory above) is
// always written regardless of whether this succeeds.
function syncSessionToBackend(record, postSoreness, postFatigue){
  var payload = {
    athlete_id: ATHLETE_ID,
    date: record.date,
    sport: record.sport,
    program_label: record.program_label || null,
    deload_mode: !!record.deload_mode,
    prescribed_count: record.prescribed_count || 0,
    readiness_used: (typeof record.readiness_used === 'number') ? record.readiness_used : null,
    post_soreness: (postSoreness || null),
    post_fatigue: (postFatigue || null),
    exercises: record.exercises || [],
    log: record.log || []
  };
  fetch(API_BASE + '/api/v1/sessions', {
    method: 'POST',
    headers: jsonAuthHeaders(),
    body: JSON.stringify(payload)
  }).then(function(r){
    if(!r.ok) throw new Error('bad status');
    if(S.currentUser){
      showToast('Session synced — counts toward your personalized rankings.');
      renderTrainingPatterns();
    } else {
      showToast('Session saved on this device. Log in to have it personalize future workouts.');
    }
  }).catch(function(){
    showToast('Saved on this device, but it couldn\'t sync to the server. Check your connection — it will sync the next time you save a session while online.', 'error');
  });
}

// Fetches history from the backend; falls back to the local cache if the
// request fails for any reason (offline, backend not running, CORS, etc).
function fetchHistory(cb){
  fetch(API_BASE + '/api/v1/sessions?athlete_id=' + encodeURIComponent(ATHLETE_ID) + '&limit=500', {headers: authHeaders()})
    .then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); })
    .then(function(rows){
      var mapped = rows.map(function(r){
        return {
          id: r.id, date: r.date, sport: r.sport, experience_level: r.experience_level,
          deload_mode: r.deload_mode, prescribed_count: r.prescribed_count,
          program_label: r.program_label, exercises: r.exercises, log: r.log
        };
      });
      cb(mapped);
    })
    .catch(function(){ cb(loadHistory()); });
}

document.getElementById('btnHistoryTrain').addEventListener('click', function(){ show('screen-hero'); });

function renderHistory(){
  renderTrainingPatterns();
  fetchHistory(function(hist){ renderHistoryList(hist.slice().reverse()); });
}

