'use strict';

// ============================================================
// ACCESSIBILITY LAYER
// ------------------------------------------------------------
// FORGE renders most of its UI from template strings, and many
// "buttons" are <div>/<span> elements with a click handler. Rather
// than touching every renderer, this file makes them keyboard- and
// screen-reader-usable in one place, and adds the dialog behavior
// (Escape, focus trap, focus restore, background scroll lock) that
// the modals were missing.
// ============================================================

(function(){
  // Elements that behave like buttons but are rendered as non-buttons.
  var CLICKABLE = '.choice, .eq-group-head, .inj-section-head, .exname, .cal-cell.has-session, .progress-dots span.clickable';

  function enhance(root){
    if(!root || !root.querySelectorAll) return;
    var list = root.matches && root.matches(CLICKABLE) ? [root] : [];
    root.querySelectorAll(CLICKABLE).forEach(function(el){ list.push(el); });
    list.forEach(function(el){
      if(el.getAttribute('data-a11y') === '1') return;
      el.setAttribute('data-a11y', '1');
      el.setAttribute('role', 'button');
      el.setAttribute('tabindex', '0');
      if(el.classList.contains('choice')){
        var label = el.querySelector('h4');
        if(label) el.setAttribute('aria-label', label.textContent.trim());
      }
      if(el.parentNode && el.parentNode.classList.contains('progress-dots')){
        el.setAttribute('aria-label', 'Go to step ' + el.getAttribute('data-goto-step'));
      }
    });
    syncState(root);
  }

  // Selected / expanded state for screen readers.
  function syncState(root){
    (root || document).querySelectorAll('.choice[data-a11y]').forEach(function(el){
      el.setAttribute('aria-pressed', el.classList.contains('selected') ? 'true' : 'false');
    });
    (root || document).querySelectorAll('.eq-group-head[data-a11y], .inj-section-head[data-a11y]').forEach(function(el){
      var p = el.parentNode;
      el.setAttribute('aria-expanded', p && p.classList.contains('open') ? 'true' : 'false');
    });
  }

  document.addEventListener('keydown', function(e){
    var el = e.target;
    if(!el || el.getAttribute('data-a11y') !== '1') return;
    if(e.key === 'Enter' || e.key === ' '){
      e.preventDefault();
      el.click();
      setTimeout(function(){ syncState(document); }, 0);
    }
  });
  document.addEventListener('click', function(){ setTimeout(function(){ syncState(document); }, 0); });

  var pending = false;
  var observer = new MutationObserver(function(muts){
    if(pending) return;
    pending = true;
    requestAnimationFrame(function(){
      pending = false;
      enhance(document.body);
      // Inline error boxes should be announced when they appear.
      document.querySelectorAll('.auth-error-box:not([role])').forEach(function(b){ b.setAttribute('role', 'alert'); });
    });
  });
  observer.observe(document.body, {childList:true, subtree:true});
  enhance(document.body);

  // ---------------- dialogs ----------------
  var DIALOGS = [
    {el:'confirmModalBackdrop', isOpen:function(e){ return e.style.display === 'flex'; }, close:function(){ var b = document.getElementById('confirmModalCancel'); if(b) b.click(); }},
    {el:'tosModalBackdrop',     isOpen:function(e){ return e.style.display === 'flex'; }, close:function(){ var b = document.getElementById('tosModalClose'); if(b) b.click(); }},
    {el:'modalOverlay',         isOpen:function(e){ return e.classList.contains('active'); }, close:function(){ if(typeof closeModal === 'function') closeModal(); }}
  ];
  var openerByDialog = {};
  var wasOpen = {};
  var FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]):not([type=hidden]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function visibleFocusables(container){
    return Array.prototype.filter.call(container.querySelectorAll(FOCUSABLE), function(n){ return n.offsetParent !== null; });
  }
  function topOpenDialog(){
    // Later entries stack above earlier ones (confirm is z-index 200, same as ToS).
    for(var i = 0; i < DIALOGS.length; i++){
      var e = document.getElementById(DIALOGS[i].el);
      if(e && DIALOGS[i].isOpen(e)) return {def:DIALOGS[i], el:e};
    }
    return null;
  }
  function syncDialogs(){
    var anyOpen = false;
    DIALOGS.forEach(function(d){
      var e = document.getElementById(d.el);
      if(!e) return;
      var open = d.isOpen(e);
      anyOpen = anyOpen || open;
      if(open && !wasOpen[d.el]){
        openerByDialog[d.el] = document.activeElement;
        setTimeout(function(){
          var f = visibleFocusables(e);
          // Prefer a non-destructive first focus; the confirm modal manages its own.
          if(d.el !== 'confirmModalBackdrop' && f.length && !e.contains(document.activeElement)) f[0].focus();
        }, 30);
      }
      if(!open && wasOpen[d.el]){
        var op = openerByDialog[d.el];
        if(op && op.focus && document.body.contains(op)) op.focus();
      }
      wasOpen[d.el] = open;
    });
    document.body.classList.toggle('modal-open', anyOpen);
  }
  DIALOGS.forEach(function(d){
    var e = document.getElementById(d.el);
    if(e) new MutationObserver(syncDialogs).observe(e, {attributes:true, attributeFilter:['style','class']});
  });

  document.addEventListener('keydown', function(e){
    var top = topOpenDialog();
    if(e.key === 'Escape'){
      // Notification popover first - it isn't a modal.
      var panel = document.getElementById('notifPanel');
      if(panel && panel.style.display !== 'none'){
        panel.style.display = 'none';
        var nb = document.getElementById('notifBtn'); if(nb){ nb.setAttribute('aria-expanded','false'); nb.focus(); }
        return;
      }
      if(top) top.def.close();
      return;
    }
    if(e.key === 'Tab' && top){
      var f = visibleFocusables(top.el);
      if(!f.length) return;
      var first = f[0], last = f[f.length - 1];
      if(!top.el.contains(document.activeElement)){ e.preventDefault(); first.focus(); }
      else if(e.shiftKey && document.activeElement === first){ e.preventDefault(); last.focus(); }
      else if(!e.shiftKey && document.activeElement === last){ e.preventDefault(); first.focus(); }
    }
  });

  // Keep aria-expanded on the notification button in sync with the panel.
  var nb = document.getElementById('notifBtn'), np = document.getElementById('notifPanel');
  if(nb && np){
    new MutationObserver(function(){ nb.setAttribute('aria-expanded', np.style.display !== 'none' ? 'true' : 'false'); })
      .observe(np, {attributes:true, attributeFilter:['style']});
  }
})();
