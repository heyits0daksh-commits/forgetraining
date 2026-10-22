'use strict';

// ============================================================
// CALENDAR
// ============================================================

function ymd(d){ return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0'); }

function renderCalendar(){
  var grid = document.getElementById('calGrid');
  var label = document.getElementById('calMonthLabel');
  var details = document.getElementById('calDetails');
  details.classList.remove('show');
  details.innerHTML = '';

  var year = S.calDate.getFullYear();
  var month = S.calDate.getMonth();
  label.textContent = S.calDate.toLocaleDateString(undefined,{month:'long',year:'numeric'});

  fetchHistory(function(hist){
    var byDay = {};
    hist.forEach(function(sess){
      var key = ymd(new Date(sess.date));
      if(!byDay[key]) byDay[key] = [];
      byDay[key].push(sess);
    });

    var firstDay = new Date(year, month, 1);
    var startOffset = firstDay.getDay();
    var daysInMonth = new Date(year, month+1, 0).getDate();
    var todayKey = ymd(new Date());

    var html = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'].map(function(l){
      return '<div class="cal-day-label">'+l+'</div>';
    }).join('');

    for(var i=0;i<startOffset;i++){ html += '<div class="cal-cell pad"></div>'; }

    for(var day=1; day<=daysInMonth; day++){
      var d = new Date(year, month, day);
      var key = ymd(d);
      var sessions = byDay[key] || [];
      var classes = ['cal-cell'];
      if(key === todayKey) classes.push('today');
      if(sessions.length){
        classes.push('has-session');
        classes.push(sessions.some(function(s){return s.deload_mode;}) ? 'deload' : 'logged');
      }
      var info = '';
      if(sessions.length){
        var s0 = sessions[0];
        info = '<div class="cal-info '+(s0.deload_mode?'blue':'green')+'">'+sportDot(s0.sport)+esc(s0.sport)+(sessions.length > 1 ? ' <b>+'+(sessions.length-1)+'</b>' : '')+'</div>';
      }
      html += '<div class="'+classes.join(' ')+'" data-day="'+key+'"'+(sessions.length ? ' aria-label="'+d.toLocaleDateString(undefined,{month:'long',day:'numeric'})+': '+sessions.length+' session'+(sessions.length>1?'s':'')+'"' : '')+'><span class="cal-date">'+day+'</span>'+info+'</div>';
    }

    grid.innerHTML = html;
    grid.querySelectorAll('.cal-cell.has-session').forEach(function(cell){
      cell.addEventListener('click', function(){ showDayDetails(cell.getAttribute('data-day'), byDay[cell.getAttribute('data-day')]); });
    });
  });
}

function showDayDetails(key, sessions){
  var details = document.getElementById('calDetails');
  var html = sessions.map(function(sess){
    var rows = sess.exercises.map(function(ex){
      return '<div class="exrow"><b>'+esc(ex.name)+'</b> — '+ex.prescription+'</div>';
    }).join('');
    return '<h4 style="display:flex;align-items:center;">'+sportBadge(sess.sport)+esc(sess.sport)+(sess.deload_mode?' (Deload)':'')+'</h4>'+rows;
  }).join('<div style="height:14px;"></div>');
  details.innerHTML = html;
  details.classList.add('show');
  // On a phone the details open below the fold - bring them into view.
  details.scrollIntoView({behavior:smoothBehavior(), block:'nearest'});
}

document.getElementById('calPrev').addEventListener('click', function(){
  S.calDate = new Date(S.calDate.getFullYear(), S.calDate.getMonth()-1, 1);
  renderCalendar();
});
document.getElementById('calNext').addEventListener('click', function(){
  S.calDate = new Date(S.calDate.getFullYear(), S.calDate.getMonth()+1, 1);
  renderCalendar();
});

// ============================================================
document.getElementById('btnRetry').addEventListener('click', boot);
boot();
