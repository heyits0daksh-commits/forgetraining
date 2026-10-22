'use strict';

// ============================================================
// DRAG REORDER — shared, touch-first reorder engine used by both
// custom-mode-picker.js and program-custom-days.js's exercise-chip lists.
//
// WHY THIS EXISTS: the previous per-file wireChipDragAndDrop/
// wirePgChipDragAndDrop used the HTML5 Drag and Drop API
// (dragstart/dragover/drop). That API has no real touch backing on iOS
// Safari or Android Chrome — on a phone those handlers simply never fire,
// so "drag to reorder" only ever worked with a mouse. The ↑/↓ buttons were
// the only way to reorder on a real phone. This file replaces that with a
// single Pointer Events implementation (pointerdown/pointermove/pointerup),
// which iOS/Android *do* deliver for both touch and mouse, so the same
// code path drives drag-to-reorder everywhere. The ↑/↓ buttons stay
// untouched as a keyboard/no-drag fallback and for anyone who prefers them.
//
// Behavior:
//  - Drag only starts from the .drag-handle (never from the whole chip),
//    so a scroll gesture that starts anywhere else on a chip still scrolls
//    the page normally.
//  - The dragged chip is lifted (elevated shadow + slight scale) and
//    follows the pointer with a plain transform (no layout thrash).
//  - Other chips animate out of the way with a FLIP transform whenever the
//    drop position changes, instead of snapping — so reordering reads as
//    motion, not a jump cut.
//  - Auto-scrolls the nearest scrollable ancestor when dragging near the
//    top/bottom edge of the viewport, since a picked-list can be longer
//    than one screen on mobile.
//  - Fires a light haptic tick (via capacitor-native.js's Haptics plugin,
//    when running in the wrapped app) on drag start and on every position
//    swap, purely cosmetic — no-ops instantly on plain web/desktop.
// ============================================================

function enableDragReorder(container, opts){
  if(!container || container.__dragReorderWired) return;
  container.__dragReorderWired = true;
  var itemSelector = opts.itemSelector;
  var handleSelector = opts.handleSelector || '.drag-handle';
  var getId = opts.getId; // (itemEl) -> string id
  var onReorder = opts.onReorder; // (idsInOrder) -> void, called after drop

  var dragEl = null, placeholder = null, startY = 0, startTop = 0, pointerId = null;
  var itemsSnapshot = []; // [{el, id, top, height}] captured at drag start
  var autoScrollRAF = null, autoScrollDir = 0;
  var scrollParent = null;

  function haptic(){
    var Haptics = (typeof nativePlugin === 'function') ? nativePlugin('Haptics') : null;
    if(Haptics) Haptics.impact({ style: 'LIGHT' }).catch(function(){});
  }

  function findScrollParent(el){
    var p = el.parentElement;
    while(p){
      var style = getComputedStyle(p);
      if(/(auto|scroll)/.test(style.overflowY) && p.scrollHeight > p.clientHeight) return p;
      p = p.parentElement;
    }
    return document.scrollingElement || document.documentElement;
  }

  function itemsInDom(){
    return Array.prototype.slice.call(container.querySelectorAll(itemSelector));
  }

  function onPointerDown(e){
    if(e.pointerType === 'mouse' && e.button !== 0) return;
    var handle = e.target.closest(handleSelector);
    if(!handle) return;
    var item = handle.closest(itemSelector);
    if(!item || !container.contains(item)) return;
    e.preventDefault();

    dragEl = item;
    pointerId = e.pointerId;
    scrollParent = findScrollParent(container);
    try{ dragEl.setPointerCapture(pointerId); }catch(err){}

    var rect = dragEl.getBoundingClientRect();
    startY = e.clientY;
    startTop = rect.top;

    itemsSnapshot = itemsInDom().map(function(el){
      var r = el.getBoundingClientRect();
      return {el: el, id: getId(el), top: r.top, height: r.height};
    });

    // Placeholder keeps the layout's height where the dragged chip was,
    // so nothing else has to reflow while it's floating.
    placeholder = document.createElement('div');
    placeholder.className = 'drag-placeholder';
    placeholder.style.height = rect.height + 'px';
    dragEl.parentNode.insertBefore(placeholder, dragEl.nextSibling);

    dragEl.classList.add('dragging-chip');
    dragEl.style.width = rect.width + 'px';
    dragEl.style.position = 'fixed';
    dragEl.style.left = rect.left + 'px';
    dragEl.style.top = rect.top + 'px';
    dragEl.style.zIndex = 999;
    dragEl.style.margin = '0';

    document.body.classList.add('dragging-active');
    haptic();

    window.addEventListener('pointermove', onPointerMove);
    window.addEventListener('pointerup', onPointerUp);
    window.addEventListener('pointercancel', onPointerUp);
  }

  function autoScrollTick(){
    if(!autoScrollDir || !scrollParent){ autoScrollRAF = null; return; }
    scrollParent.scrollBy(0, autoScrollDir * 14);
    autoScrollRAF = requestAnimationFrame(autoScrollTick);
  }

  function onPointerMove(e){
    if(!dragEl || e.pointerId !== pointerId) return;
    var dy = e.clientY - startY;
    var newTop = startTop + dy;
    dragEl.style.top = newTop + 'px';

    // Auto-scroll near the viewport edges (mobile: the picked list often
    // runs past one screen; without this you can't drag a chip further
    // than the visible viewport allows).
    var vh = window.innerHeight;
    if(e.clientY < 90) autoScrollDir = -1;
    else if(e.clientY > vh - 90) autoScrollDir = 1;
    else autoScrollDir = 0;
    if(autoScrollDir && !autoScrollRAF) autoScrollRAF = requestAnimationFrame(autoScrollTick);

    // Figure out where the dragged chip's *center* currently sits relative
    // to the other chips' last-known centers, and move the placeholder
    // there. Comparing against the snapshot (not live DOM) keeps this
    // stable even mid-animation.
    var dragCenter = newTop + dragEl.offsetHeight / 2;
    var others = itemsSnapshot.filter(function(s){ return s.el !== dragEl; });
    var targetIndex = others.length;
    for(var i = 0; i < others.length; i++){
      if(dragCenter < others[i].top + others[i].height / 2){ targetIndex = i; break; }
    }
    var currentPlaceholderIndex = Array.prototype.indexOf.call(container.children, placeholder);
    var wanted = others.slice(0, targetIndex).map(function(s){ return s.el; });
    var last = wanted.length ? wanted[wanted.length - 1] : null;
    var desiredNextSibling = last ? last.nextSibling : (others.length ? others[0].el : null);
    if(placeholder.nextSibling !== dragEl && desiredNextSibling !== placeholder){
      if(desiredNextSibling){
        if(desiredNextSibling !== placeholder) container.insertBefore(placeholder, desiredNextSibling);
      } else {
        container.appendChild(placeholder);
      }
      animateFlip();
    }
  }

  // FLIP: snapshot -> the DOM has already moved (placeholder relocated) ->
  // read new positions -> apply an inverse transform -> animate to zero.
  // Everything except the actively-dragged chip participates, so the rest
  // of the list visibly slides into its new slot instead of jump-cutting.
  function animateFlip(){
    var moved = false;
    itemsInDom().forEach(function(el){
      if(el === dragEl) return;
      var before = null;
      for(var i=0;i<itemsSnapshot.length;i++){ if(itemsSnapshot[i].el === el){ before = itemsSnapshot[i]; break; } }
      if(!before) return;
      var afterRect = el.getBoundingClientRect();
      var dy = before.top - afterRect.top;
      if(Math.abs(dy) < 0.5) return;
      moved = true;
      el.style.transition = 'none';
      el.style.transform = 'translateY(' + dy + 'px)';
      // Force layout so the transform above is committed before clearing it.
      // eslint-disable-next-line no-unused-expressions
      el.offsetHeight;
      el.style.transition = 'transform 220ms cubic-bezier(.4,0,.2,1)';
      el.style.transform = '';
    });
    // Refresh the snapshot to the post-move geometry so the next move
    // event compares against current reality, not stale positions.
    itemsSnapshot = itemsInDom().map(function(el){
      var r = el.getBoundingClientRect();
      return {el: el, id: getId(el), top: r.top, height: r.height};
    });
    if(moved) haptic();
  }

  function cleanupDragStyles(){
    if(!dragEl) return;
    dragEl.classList.remove('dragging-chip');
    dragEl.style.position = '';
    dragEl.style.left = '';
    dragEl.style.top = '';
    dragEl.style.width = '';
    dragEl.style.zIndex = '';
    dragEl.style.margin = '';
  }

  function onPointerUp(e){
    if(!dragEl || (pointerId !== null && e.pointerId !== pointerId)) return;
    window.removeEventListener('pointermove', onPointerMove);
    window.removeEventListener('pointerup', onPointerUp);
    window.removeEventListener('pointercancel', onPointerUp);
    if(autoScrollRAF){ cancelAnimationFrame(autoScrollRAF); autoScrollRAF = null; }
    autoScrollDir = 0;
    document.body.classList.remove('dragging-active');

    if(placeholder && placeholder.parentNode){
      placeholder.parentNode.insertBefore(dragEl, placeholder);
      placeholder.parentNode.removeChild(placeholder);
    }
    cleanupDragStyles();
    placeholder = null;

    var order = itemsInDom().map(function(el){ return getId(el); });
    var draggedId = getId(dragEl);
    dragEl = null; pointerId = null;
    haptic();
    if(onReorder) onReorder(order, draggedId);
  }

  container.addEventListener('pointerdown', onPointerDown);
}
