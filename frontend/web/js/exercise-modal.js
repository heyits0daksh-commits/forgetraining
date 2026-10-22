'use strict';

// ============================================================
// EXERCISE KNOWLEDGE-GRAPH MODAL
// ============================================================

function openExerciseModal(exId){
  var overlay = document.getElementById('modalOverlay');
  var content = document.getElementById('modalContent');
  content.innerHTML = '<button class="close-btn" id="modalClose">&times;</button><div class="modal-loading">Reading the knowledge graph…</div>';
  overlay.classList.add('active');
  document.getElementById('modalClose').addEventListener('click', closeModal);
  S.modalExerciseId = exId; // read by progress-chart.js once renderModal appends its section

  fetch(API_BASE + '/api/v1/knowledge-graph/' + encodeURIComponent(exId))
    .then(function(r){ if(!r.ok) throw new Error('not found'); return r.json(); })
    .then(renderModal)
    .catch(function(){
      content.innerHTML = '<button class="close-btn" id="modalClose">&times;</button>'+
        '<div class="modal-loading">Could not load graph data for this exercise.</div>';
      document.getElementById('modalClose').addEventListener('click', closeModal);
    });
}
function closeModal(){
  // While the login gate is up (S.authGate, set by openAuthModal in
  // accounts.js), the modal must not be dismissible any other way - it's
  // the only thing standing between an anonymous visitor and the app.
  if(S.authGate){ return; }
  document.getElementById('modalOverlay').classList.remove('active');
  if(typeof destroyProgressChart === 'function'){ destroyProgressChart(); }
}
document.getElementById('modalOverlay').addEventListener('click', function(e){
  if(e.target === this) closeModal();
});
function chipList(items, keyFn){
  if(!items || !items.length) return '<div class="empty">None on file</div>';
  return '<div class="chip-row">'+items.map(function(it){ return '<span class="chip">'+esc(keyFn(it))+'</span>'; }).join('')+'</div>';
}
function renderModal(data){
  var content = document.getElementById('modalContent');
  var sportRows = (data.sport_transfer || []).slice(0,6).map(function(s){
    return '<div class="transfer-row"><span>'+esc(s.sport)+'</span><b>'+s.score+'</b></div>';
  }).join('') || '<div class="empty">No measurable transfer on file</div>';

  content.innerHTML =
    '<button class="close-btn" id="modalClose">&times;</button>'+
    '<h3>'+esc(data.name)+'</h3>'+
    '<div class="modal-sub">'+esc(data.programming_role || '')+'</div>'+
    (data.programming_role_rationale ? '<div class="callout" style="margin-top:0;margin-bottom:20px;">'+esc(data.programming_role_rationale)+'</div>' : '')+
    '<div class="modal-section" id="videoSection"><h5>Demo Video</h5><div id="videoWrap"><button class="btn secondary" id="btnLoadVideo" style="width:100%;">Watch Demo</button></div></div>'+
    '<div class="modal-section"><h5>Progresses To</h5>'+chipList(data.progressions, function(p){return p.name;})+'</div>'+
    '<div class="modal-section"><h5>Builds Up From</h5>'+chipList(data.regressions, function(p){return p.name;})+'</div>'+
    '<div class="modal-section"><h5>Equipment Substitutes</h5>'+chipList(data.substitutes, function(p){return p.name;})+'</div>'+
    '<div class="modal-section"><h5>Joints Stressed</h5>'+chipList(data.joints_stressed, function(p){return p.joint + (p.difficulty ? ' (diff '+p.difficulty+')' : '');})+'</div>'+
    '<div class="modal-section"><h5>Rehab Candidate For</h5>'+chipList(data.rehab_candidate_for, function(p){return p.injury;})+'</div>'+
    '<div class="modal-section"><h5>Sport Transfer</h5>'+sportRows+'</div>'+
    '<div class="modal-section" id="progressSection"><h5>Your Progress</h5><div id="progressChartWrap"><button class="btn secondary" id="btnLoadProgress" style="width:100%;">Show Progress Chart</button></div></div>';
  document.getElementById('modalClose').addEventListener('click', closeModal);
  var progressBtn = document.getElementById('btnLoadProgress');
  if(progressBtn){ progressBtn.addEventListener('click', function(){ renderExerciseProgressChart(S.modalExerciseId, data.name, data.equipment === 'Dumbbell'); }); }
  var videoBtn = document.getElementById('btnLoadVideo');
  if(videoBtn){ videoBtn.addEventListener('click', function(){ loadExerciseVideo(S.modalExerciseId); }); }
}

// Fetches the resolved demo video for this exercise and, whenever
// possible, embeds it in-app (youtube-nocookie.com / Vimeo iframe, or a
// plain <video> tag for a direct file link from a curated link - see
// backend/data/exercise_video_links.py) instead of redirecting out. Only
// when the backend reports `embeddable: false` (a curated link to a site
// that doesn't reliably embed, e.g. Instagram/TikTok/an article page) does
// this fall back to a "Watch on <source>" button that opens in a new tab -
// see backend/services/video_lookup.py's resolve_static_video_link for
// exactly which link shapes embed vs link out.
function loadExerciseVideo(exId){
  var wrap = document.getElementById('videoWrap');
  if(!wrap) return;
  wrap.innerHTML = '<div class="empty">Loading…</div>';
  fetch(API_BASE + '/api/v1/exercises/' + encodeURIComponent(exId) + '/video')
    .then(function(r){ return r.json(); })
    .then(function(data){
      if(!data.available){
        wrap.innerHTML = '<div class="empty">No demo video available for this exercise yet.</div>';
        return;
      }
      if(data.embeddable === false){
        wrap.innerHTML =
          '<a class="btn secondary" style="width:100%;display:block;text-align:center;" target="_blank" rel="noopener noreferrer" href="'+esc(data.watch_url)+'">Watch on '+esc(data.channel_name || 'external site')+'</a>'+
          '<div class="video-embed-meta">'+esc(data.title)+'</div>';
        return;
      }
      var player = (data.source_type === 'direct_file')
        ? '<video class="video-embed-native" src="'+esc(data.embed_url)+'" controls playsinline style="width:100%;height:100%;"></video>'
        : '<iframe src="'+esc(data.embed_url)+'" title="'+esc(data.title)+'" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe>';
      wrap.innerHTML =
        '<div class="video-embed-wrap">'+player+'</div>'+
        '<div class="video-embed-meta">'+esc(data.title)+' — '+esc(data.channel_name)+'</div>';
    })
    .catch(function(){
      wrap.innerHTML = '<div class="empty">Could not load the demo video right now.</div>';
    });
}

