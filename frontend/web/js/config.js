'use strict';

// ============================================================
// CONFIG
// ============================================================

var API_BASE = (function(){
  var qp = new URLSearchParams(location.search).get('api');
  if(qp){ return qp; }
  // Local double-click (file://) or the old dev workflow (frontend opened
  // separately from the backend): keep talking to the documented local
  // dev address. Anything else (served over http/https - e.g. deployed
  // as one Render/Railway/Fly service, per backend/main.py's StaticFiles
  // mount) means the API lives on this same origin, so use that instead
  // of a hardcoded localhost address that would only work on the
  // developer's own machine.
  if(location.protocol === 'file:' || location.hostname === '127.0.0.1' || location.hostname === 'localhost'){
    return 'http://127.0.0.1:8000';
  }
  return location.origin;
})();
// Reads a failed API response body under either error shape this backend
// can return: the ForgeError envelope `{error: {code, message, request_id}}`
// (backend/core/exceptions.py - register/login/refresh/most other failures,
// plus the catch-all unhandled-exception handler) or FastAPI's own default
// `{detail: ...}` shape, which still slips through for two paths that
// deliberately never got migrated to ForgeError: raw pydantic 422 validation
// errors, and program_builder.py's local `HTTPException(400, ...)` for an
// unknown split id (see docs/ROADMAP.md's error-handling completion pass
// notes on why that one call site stayed as-is). Falls back to
// fallbackMsg when neither shape yields a usable string.
function extractErrorMessage(data, fallbackMsg){
  if(data && data.error && data.error.message){ return data.error.message; }
  if(data && typeof data.detail === 'string'){ return data.detail; }
  return fallbackMsg;
}
var HISTORY_KEY = 'forge_history_v1';
// No accounts/auth yet (see backend/core/database.py's docstring) - every
// session syncs to the backend under this single fixed athlete id.
var ATHLETE_ID = 'default';

