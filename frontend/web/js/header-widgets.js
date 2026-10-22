'use strict';

// ============================================================
// HEADER WIDGETS — small "sessions per week" sparkline + a lightweight
// notification popover, both driven entirely by locally-logged history
// (see history.js) so they work offline and need no new backend endpoint.
// ============================================================

// Buckets logged sessions into the last 7 calendar weeks and renders a tiny
// bar sparkline in the header — a quick "am I actually training" glance
// without opening the full Progress page.
function renderHeaderMiniSpark(){
  var el = document.getElementById('headerMiniSpark');
  if(!el) return;
  var hist = loadHistory();
  var weeks = 7;
  var counts = new Array(weeks).fill(0);
  var now = new Date();
  var msPerWeek = 7*24*60*60*1000;
  hist.forEach(function(h){
    if(!h.date) return;
    var d = new Date(h.date);
    if(isNaN(d)) return;
    var weeksAgo = Math.floor((now - d) / msPerWeek);
    if(weeksAgo >= 0 && weeksAgo < weeks){
      counts[weeks - 1 - weeksAgo]++;
    }
  });
  var max = Math.max(1, Math.max.apply(null, counts));
  if(!hist.length){ el.innerHTML = ''; el.style.display = 'none'; return; }
  el.style.display = 'flex';
  el.innerHTML = counts.map(function(c){
    var h = Math.max(3, Math.round((c / max) * 20));
    return '<i style="height:'+h+'px;'+(c===0 ? 'opacity:.25;' : '')+'"></i>';
  }).join('');
}

// Small, local-only notification set — deload warnings and readiness dips
// already exist elsewhere in the app; this surfaces the same signals as a
// glanceable header list instead of inventing a server-side notification
// system. Nothing here is fetched remotely.
function computeHeaderNotifications(){
  var notes = [];
  var hist = loadHistory();
  if(!hist.length){
    notes.push({text:'Log your first session to start tracking progress.', tone:'info'});
    return notes;
  }
  var last = hist[hist.length - 1];
  if(last && last.date){
    var daysSince = Math.floor((Date.now() - new Date(last.date)) / (24*60*60*1000));
    if(daysSince >= 5){
      notes.push({text:'It\u2019s been '+daysSince+' days since your last logged session.', tone:'warn'});
    }
  }
  if(last && last.deload_mode){
    notes.push({text:'Your last session was a deload — readiness was running low.', tone:'warn'});
  }
  notes.push({text:hist.length+' session'+(hist.length===1?'':'s')+' logged so far. Nice work.', tone:'info'});
  return notes;
}

function renderNotifPanel(){
  var panel = document.getElementById('notifPanel');
  var dot = document.getElementById('notifDot');
  if(!panel) return;
  var notes = computeHeaderNotifications();
  var hasWarn = notes.some(function(n){ return n.tone === 'warn'; });
  if(dot) dot.style.display = hasWarn ? '' : 'none';
  panel.innerHTML = notes.map(function(n){
    return '<div class="notif-item notif-'+n.tone+'">'+esc(n.text)+'</div>';
  }).join('') || '<div class="notif-item">You\u2019re all caught up.</div>';
}

(function(){
  var btn = document.getElementById('notifBtn');
  var panel = document.getElementById('notifPanel');
  if(!btn || !panel) return;
  btn.addEventListener('click', function(e){
    e.stopPropagation();
    var open = panel.style.display !== 'none';
    if(open){ panel.style.display = 'none'; return; }
    renderNotifPanel();
    panel.style.display = 'block';
  });
  document.addEventListener('click', function(e){
    if(!panel.contains(e.target) && e.target !== btn){ panel.style.display = 'none'; }
  });
})();

// Refresh both widgets whenever Home is shown (mirrors updateHeroForReturningUser's
// call site in show()) and once on boot.
var _origShowForHeaderWidgets = show;
show = function(id){
  _origShowForHeaderWidgets(id);
  renderHeaderMiniSpark();
  if(document.getElementById('notifDot')){
    var hasWarn = computeHeaderNotifications().some(function(n){ return n.tone === 'warn'; });
    document.getElementById('notifDot').style.display = hasWarn ? '' : 'none';
  }
};
