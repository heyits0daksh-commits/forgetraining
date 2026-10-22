'use strict';

// ============================================================
// CONDITIONING (standalone aerobic/lactic screen — no lifting)
// ============================================================

function renderConditioningSportGrid(){
  var m = S.metadata;
  var cg = document.getElementById('condSportGrid');
  if(!m || !cg) return;
  cg.innerHTML = m.sports.map(function(sport){
    var t = themeFor(sport);
    var img = firstImg(t);
    var bg = img ? "background-image:url('"+img+"');" : '';
    var selected = sport === S.condSport ? ' selected' : '';
    return '<div class="choice'+selected+'" data-cond-sport="'+esc(sport)+'" style="--accent:'+t.accent+';'+bg+'">'+
      '<span class="checkmark">✓</span>'+
      '<div class="tile-body"><span class="icon">'+esc(t.mono)+'</span><h4>'+esc(sport)+'</h4>'+
      (t.region ? '<span class="region">'+esc(t.region)+'</span>' : '')+'</div>'+
      '</div>';
  }).join('');
  cg.querySelectorAll('.choice').forEach(function(card){
    card.addEventListener('click', function(){
      selectConditioningSport(card.getAttribute('data-cond-sport'));
    });
  });
}

function selectConditioningSport(sport){
  S.condSport = sport;
  document.querySelectorAll('#condSportGrid .choice').forEach(function(c){
    c.classList.toggle('selected', c.getAttribute('data-cond-sport') === sport);
  });
  applyTheme(sport);
  document.getElementById('condSubtitle').textContent =
    'Conditioning only for ' + sport + ' — no lifting here, just the aerobic:lactic ratio and session menus.';
  var body = document.getElementById('condBody');
  body.innerHTML = '<div class="loading-screen" style="padding:40px 0;"><div class="spinner"></div></div>';

  var refPromise = S.conditioningRef
    ? Promise.resolve(S.conditioningRef)
    : fetch(API_BASE + '/api/v1/conditioning-protocols').then(function(r){ return r.json(); }).then(function(d){ S.conditioningRef = d; return d; });

  Promise.all([
    fetch(API_BASE + '/api/v1/sports/' + encodeURIComponent(sport)).then(function(r){ return r.json(); }),
    refPromise
  ]).then(function(results){
    renderConditioningBody(sport, results[0].conditioning_profile, results[1]);
  }).catch(function(){
    body.innerHTML = '<div class="empty">Couldn\'t load conditioning data for '+esc(sport)+' — check the engine connection.</div>';
  });
}

function renderConditioningBody(sport, profile, ref){
  var body = document.getElementById('condBody');
  if(!profile || !profile.aerobic_pct){
    body.innerHTML = '<div class="callout" style="margin-top:20px;">The manual doesn\'t cover a specific aerobic:lactic ratio for '+esc(sport)+' yet — '+
      'use the general menus below and lean on the Mixed/Aerobic/Lactic conditioning-emphasis option inside Build Strength instead.</div>'+
      conditioningMenusHtml(ref);
    return;
  }
  var aer = profile.aerobic_pct, lac = profile.lactic_pct;
  body.innerHTML =
    '<div class="card" style="margin-top:20px;">'+
      '<div style="display:flex;justify-content:space-between;font-size:13px;font-weight:700;margin-bottom:8px;">'+
        '<span>Aerobic '+aer+'%</span><span>Lactic '+lac+'%</span>'+
      '</div>'+
      '<div style="display:flex;height:14px;border-radius:8px;overflow:hidden;border:1px solid var(--line);">'+
        '<div style="width:'+aer+'%;background:var(--blue);"></div>'+
        '<div style="width:'+lac+'%;background:var(--red);"></div>'+
      '</div>'+
      (profile.gym_emphasis ? '<p class="micro" style="margin-top:16px;"><b>Why this ratio:</b> '+esc(profile.gym_emphasis)+'</p>' : '')+
      (profile.conditioning_notes ? '<p class="micro" style="margin-top:8px;"><b>Weekly volume:</b> '+esc(profile.conditioning_notes)+'</p>' : '')+
      (profile.time_saver ? '<div class="callout blue" style="margin-top:16px;"><b>Time-saver:</b> '+esc(profile.time_saver)+'</div>' : '')+
    '</div>'+
    conditioningMenusHtml(ref);
}

function conditioningMenusHtml(ref){
  if(!ref) return '';
  var aerobicRows = (ref.aerobic_session_menu || []).map(function(m){
    return '<div class="card" style="margin-top:10px;"><b>'+esc(m.modality)+'</b> <span class="micro">— '+esc(m.duration)+'</span>'+
      (m.notes ? '<p class="micro" style="margin-top:6px;">'+esc(m.notes)+'</p>' : '')+'</div>';
  }).join('');
  var lacticRows = (ref.lactic_session_menu || []).map(function(m){
    return '<div class="card" style="margin-top:10px;"><b>'+esc(m.protocol)+'</b> <span class="micro">— '+esc(m.structure)+'</span>'+
      (m.best_for ? '<p class="micro" style="margin-top:6px;">'+esc(m.best_for)+'</p>' : '')+'</div>';
  }).join('');
  return ''+
    '<h3 style="margin:26px 0 6px;">Aerobic Menu — pick 1 per session</h3>'+aerobicRows+
    '<h3 style="margin:26px 0 6px;">Lactic Menu — pick 1-2 per session</h3>'+lacticRows+
    (ref.weekly_fitting_note ? '<div class="callout" style="margin-top:20px;">'+esc(ref.weekly_fitting_note)+'</div>' : '');
}

// Human-readable label + coach's-explanation hint for each energy-system
// option the backend accepts (schemas.CONDITIONING_EMPHASES). Falls back to
// the bare value for any option this list doesn't yet know about, so an
// older frontend against a newer backend still degrades gracefully.
var CONDITIONING_LABELS = {
  'Mixed':   {label:'Mixed — General Conditioning',   hint:'Balanced, general-purpose intervals — no specific energy system emphasis.'},
  'Alactic': {label:'Alactic — Power & Speed',         hint:'Short max-effort bursts (5-15s) with long, near-full recovery. Quality over fatigue — pure power/speed.'},
  'Lactic':  {label:'Lactic — Anaerobic Capacity',     hint:'Sustained high-output efforts (20-60s) with incomplete rest. The classic "burn" zone.'},
  'Aerobic': {label:'Aerobic — Endurance',             hint:'Longer steady-state intervals, short rest — keeps heart rate elevated to build aerobic base.'}
};
// Populates a <select> with every conditioning_emphasis option the backend's
// /api/v1/metadata reported (falls back to the 4 known values if an older
// backend doesn't send the list yet), wires its hint text and change handler.
function populateConditioningSelect(selectId, hintId, currentValue, onChange){
  var sel = document.getElementById(selectId);
  var hint = document.getElementById(hintId);
  if(!sel) return;
  var options = (S.metadata && S.metadata.conditioning_emphases && S.metadata.conditioning_emphases.length)
    ? S.metadata.conditioning_emphases
    : ['Mixed', 'Alactic', 'Lactic', 'Aerobic'];
  sel.innerHTML = options.map(function(opt){
    var meta = CONDITIONING_LABELS[opt] || {label:opt};
    return '<option value="'+esc(opt)+'"'+(opt===currentValue?' selected':'')+'>'+esc(meta.label)+'</option>';
  }).join('');
  function reflectHint(){
    var meta = CONDITIONING_LABELS[sel.value] || {hint:''};
    if(hint) hint.textContent = meta.hint || '';
  }
  reflectHint();
  sel.addEventListener('change', function(){
    reflectHint();
    if(onChange) onChange(sel.value);
  });
}

