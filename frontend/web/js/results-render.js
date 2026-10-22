'use strict';

// ============================================================
// RESULTS RENDER
// ============================================================

function renderPrescription(p){
  if(!p) return '';
  if(p.type === 'strength'){
    var loadStr;
    if(p.working_weight_kg != null){
      loadStr = fmtWeight(p.working_weight_kg)+(p.weight_confidence === 'estimated' ? ' (est.)' : '')+
        ' <span class="pill" title="'+esc(p.anchor_lift+' 1RM × '+p.load_pct_1rm+'%')+'">'+p.load_pct_1rm+'% 1RM</span>';
    } else {
      loadStr = p.load_pct_1rm+'% 1RM'+(p.weight_note ? ' <span class="pill" title="'+esc(p.weight_note)+'">add 1RM for weight</span>' : '');
    }
    return p.sets+' × '+p.reps+' reps @ '+loadStr+' &nbsp;·&nbsp; rest '+p.rest_seconds+'s';
  }
  if(p.type === 'strength_bodyweight') return p.sets+' × '+p.reps+' reps (bodyweight) &nbsp;·&nbsp; rest '+p.rest_seconds+'s';
  if(p.type === 'isolation') return p.sets+' × '+p.reps+' reps'+(p.note ? ' <span class="pill" title="'+esc(p.note)+'">moderate load, adjust by feel</span>' : '')+' &nbsp;·&nbsp; rest '+p.rest_seconds+'s';
  if(p.type === 'conditioning') return p.sets+' rounds × '+p.work_seconds+'s effort &nbsp;·&nbsp; rest '+p.rest_seconds+'s'+
    (p.energy_system ? ' &nbsp;·&nbsp; <span class="pill">'+esc((CONDITIONING_LABELS[p.energy_system]||{}).label || p.energy_system)+'</span>' : '');
  if(p.type === 'carry') return p.sets+' rounds × '+p.distance_meters+'m carry &nbsp;·&nbsp; rest '+p.rest_seconds+'s';
  if(p.type === 'isometric') return p.sets+' × '+p.hold_seconds+'s hold &nbsp;·&nbsp; rest '+p.rest_seconds+'s';
  if(p.type === 'custom'){
    var bits = [];
    if(p.set_type && p.set_type !== 'working' && typeof setTypeLabel === 'function') bits.push(setTypeLabel(p.set_type));
    if(p.rpe != null) bits.push('RPE '+p.rpe);
    if(p.rir != null) bits.push('RIR '+p.rir);
    if(p.tempo) bits.push('Tempo '+esc(p.tempo));
    if(p.warmup_sets) bits.push(p.warmup_sets+' warm-up sets');
    return p.sets+' × '+p.reps+' reps'+(p.working_weight_kg ? ' @ '+fmtWeight(p.working_weight_kg) : '')+
      ' <span class="pill">your own pick</span> &nbsp;·&nbsp; rest '+p.rest_seconds+'s'+
      (bits.length ? ' &nbsp;·&nbsp; <span class="pill">'+bits.map(esc).join(' · ')+'</span>' : '');
  }
  return p.sets+' × '+(p.reps || '—')+' reps (technical) &nbsp;·&nbsp; rest '+p.rest_seconds+'s';
}

