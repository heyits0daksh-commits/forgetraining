'use strict';

// ============================================================
// CONFIRM MODAL
// ------------------------------------------------------------
// UX gap fix: destructive actions (delete session/program/custom
// workout) and blocking error messages used the browser's native
// confirm()/alert(). Those render as an unstyled OS popup — jarring
// against FORGE's own UI, inconsistent across browsers, and look
// especially out of place inside the Capacitor app shell (mobile.js).
// This gives every caller a themed, promise-based replacement that
// reuses the app's existing .modal-backdrop/.modal chrome.
// ============================================================

var _confirmModalResolve = null;

function showConfirm(message, opts){
  opts = opts || {};
  var backdrop = document.getElementById('confirmModalBackdrop');
  var title = document.getElementById('confirmModalTitle');
  var body = document.getElementById('confirmModalBody');
  var okBtn = document.getElementById('confirmModalOk');
  var cancelBtn = document.getElementById('confirmModalCancel');
  if(!backdrop) return Promise.resolve(window.confirm(message)); // fallback safety net

  title.textContent = opts.title || 'Are you sure?';
  body.textContent = message;
  okBtn.textContent = opts.confirmLabel || 'Delete';
  okBtn.className = 'btn' + (opts.danger === false ? '' : ' danger');
  cancelBtn.style.display = opts.hideCancel ? 'none' : '';
  backdrop.style.display = 'flex';
  // Focus the safer default (Cancel) rather than the destructive action,
  // so an accidental Enter/Space press can't confirm a delete. When Cancel
  // is hidden (plain notice), focus OK instead.
  requestAnimationFrame(function(){ (opts.hideCancel ? okBtn : cancelBtn).focus(); });

  return new Promise(function(resolve){
    _confirmModalResolve = resolve;
  });
}

// Same modal, used as a one-button error notice instead of a confirmation
// (e.g. a failed generate-workout call) — more visible than a toast for
// something that stops the flow, but still on-brand instead of native alert().
function showErrorModal(message, opts){
  opts = opts || {};
  return showConfirm(message, {
    title: opts.title || 'Something went wrong',
    confirmLabel: opts.okLabel || 'OK',
    danger: false,
    hideCancel: true
  });
}

function _closeConfirmModal(result){
  var backdrop = document.getElementById('confirmModalBackdrop');
  if(backdrop) backdrop.style.display = 'none';
  if(_confirmModalResolve){
    var r = _confirmModalResolve;
    _confirmModalResolve = null;
    r(result);
  }
}

document.addEventListener('DOMContentLoaded', function(){
  var backdrop = document.getElementById('confirmModalBackdrop');
  var okBtn = document.getElementById('confirmModalOk');
  var cancelBtn = document.getElementById('confirmModalCancel');
  var closeBtn = document.getElementById('confirmModalClose');
  if(!backdrop) return;

  okBtn.addEventListener('click', function(){ _closeConfirmModal(true); });
  cancelBtn.addEventListener('click', function(){ _closeConfirmModal(false); });
  closeBtn.addEventListener('click', function(){ _closeConfirmModal(false); });
  // Click on the dimmed backdrop itself (not the modal card) cancels —
  // matches how the Terms modal and exercise modal already behave.
  backdrop.addEventListener('click', function(e){
    if(e.target === backdrop) _closeConfirmModal(false);
  });
  document.addEventListener('keydown', function(e){
    if(e.key === 'Escape' && backdrop.style.display === 'flex') _closeConfirmModal(false);
  });
});
