'use strict';

// ============================================================
// TRAINING PATTERNS — the visible half of the log→sync→personalize loop.
// GET /api/v1/recommendations/history exposes the exact per-exercise
// signals (times logged, days since, progressing/plateau trend) that
// generate-workout/generate-program already fold into personalization_note
// on each prescribed exercise - this panel is what makes that loop
// inspectable on its own, without regenerating a workout first, and shows
// how close the account is to MIN_SESSIONS_FOR_SIGNAL if it isn't unlocked yet.
// ============================================================

function renderTrainingPatterns(){
  var el = document.getElementById('trainingPatternsPanel');
  if(!el) return;
  if(!S.currentUser){
    el.innerHTML = '<div class="callout blue">'+
      'Log in to build a training history — once you have a few logged sessions, '+
      'FORGE starts ranking exercises using your own progress, not just static rules.'+
      '</div>';
    return;
  }
  el.innerHTML = '<div class="callout">Loading your training patterns…</div>';
  fetch(API_BASE + '/api/v1/recommendations/history', {headers: authHeaders()})
    .then(function(r){ if(!r.ok) throw new Error('bad status'); return r.json(); })
    .then(function(data){
      if(!data.has_enough_history){
        fetch(API_BASE + '/api/v1/sessions?athlete_id=' + encodeURIComponent(ATHLETE_ID) + '&limit=500', {headers: authHeaders()})
          .then(function(r){ return r.ok ? r.json() : []; })
          .then(function(rows){
            var have = Math.min(rows.length || 0, data.min_sessions_required);
            var pct = Math.round((have / data.min_sessions_required) * 100);
            el.innerHTML = '<div class="callout blue">'+
              '<b>Personalization not unlocked yet.</b> Log '+data.min_sessions_required+' sessions and FORGE '+
              'starts nudging rankings from your own progress — plateaus, stale exercises, and things trending up.'+
              '<div class="patterns-progress-row"><div class="progress-track"><div class="progress-fill" style="width:'+pct+'%;"></div></div>'+
              '<span class="progress-label">'+have+' / '+data.min_sessions_required+' sessions</span></div>'+
              '</div>';
          })
          .catch(function(){
            el.innerHTML = '<div class="callout blue">'+
              '<b>Personalization not unlocked yet.</b> Log '+data.min_sessions_required+' sessions and FORGE '+
              'starts nudging rankings from your own progress — plateaus, stale exercises, and things trending up.'+
              '</div>';
          });
        return;
      }
      var rows = Object.keys(data.exercises).map(function(exId){
        var s = data.exercises[exId];
        var tag = '';
        if(s.trend === 'progressing') tag = '<span class="pattern-tag up">↑ progressing</span>';
        else if(s.trend === 'plateau') tag = '<span class="pattern-tag flat">– plateau</span>';
        else if(s.days_since >= 21) tag = '<span class="pattern-tag stale">stale '+s.days_since+'d</span>';
        var note = s.trend === 'progressing' ? 'Numbers trending up recently'
          : s.trend === 'plateau' ? 'Flat for a few sessions'
          : 'Logged '+s.times_logged+'× · last '+s.days_since+' days ago';
        return {name: s.name, times_logged: s.times_logged, tag: tag, note: note};
      }).sort(function(a,b){ return b.times_logged - a.times_logged; }).slice(0, 8);
      var rowsHtml = rows.map(function(r){
        return '<div class="pattern-row"><div><div class="pname">'+esc(r.name)+'</div>'+
          '<div class="pnote">'+esc(r.note)+'</div></div>'+r.tag+'</div>';
      }).join('');
      el.innerHTML = '<div class="callout" style="margin-top:0;">'+
        '<b>Personalization is active</b> — these signals are currently nudging your rankings.'+
        '</div>'+rowsHtml;
    })
    .catch(function(){ el.innerHTML = ''; });
}
function renderHistoryList(hist){
  var body = document.getElementById('historyBody');
  if(!hist.length){
    body.innerHTML = '<div class="empty-state">'+
      '<svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M9 3h6v4H9z"/><rect x="5" y="7" width="14" height="14" rx="2"/><path d="M9 12h6M9 16h4"/></svg>'+
      'No sessions saved yet. Generate a prescription and hit <b>Finish &amp; Save Session</b> to start your logbook.</div>';
    return;
  }
  body.innerHTML = '<div class="history-list">' + hist.map(function(sess){
    var d = new Date(sess.date);
    var prCount = 0;
    (sess.log||[]).forEach(function(l){ l.sets.forEach(function(s){ if(s.isPR) prCount++; }); });
    var exRows = sess.exercises.map(function(ex){
      var logEntry = (sess.log||[]).find(function(l){ return l.exId === ex.id; });
      var setsStr = logEntry ? logEntry.sets.map(function(s){ return fmtWeight(s.weight)+'×'+s.reps+(s.isPR?' · PR':''); }).join(', ') : 'not logged';
      return '<div class="exrow"><b>'+esc(ex.name)+'</b> — '+ex.prescription+'<br><span style="opacity:.8">'+esc(setsStr)+'</span></div>';
    }).join('');
    return '<details class="history-item"><summary>'+
      '<div><span class="date">'+d.toLocaleDateString(undefined,{weekday:'short',year:'numeric',month:'short',day:'numeric'})+
        (sess.program_label ? ' · '+esc(sess.program_label) : '')+'</span>'+
      '<div class="titlerow">'+sportBadge(sess.sport)+esc(sess.sport)+' · '+sess.prescribed_count+' exercises'+(sess.deload_mode?' · Deload':'')+'</div></div>'+
      (prCount ? '<span class="prcount">'+prCount+' PR'+(prCount>1?'s':'')+'</span>' : '')+
      '</summary>'+
      '<div class="body">'+exRows+'<button class="delbtn" data-del="'+sess.id+'">Delete this session</button></div>'+
      '</details>';
  }).join('') + '</div>';

  body.querySelectorAll('[data-del]').forEach(function(btn){
    btn.addEventListener('click', function(){
      var id = parseInt(btn.getAttribute('data-del'),10);
      showConfirm('Delete this session permanently?', {title:'Delete session?'}).then(function(ok){
      if(!ok) return;
      var hist2 = loadHistory().filter(function(s){ return s.id !== id; });
      saveHistory(hist2);
      fetch(API_BASE + '/api/v1/sessions/' + id + '?athlete_id=' + encodeURIComponent(ATHLETE_ID), {method:'DELETE', headers: authHeaders()})
        .catch(function(){ /* offline — local copy already removed */ });
      renderHistory();
      });
    });
  });
}

