/* ============================================================
   FF LIKE API — Real-Time Sync Engine
   Handles: heartbeat, session verify, tab clear, validation,
            page-load minimum duration, back-button protection.
   ============================================================ */
(function () {
  'use strict';

  const HEARTBEAT_INTERVAL = 3000;   // 3s
  const MIN_LOAD_MS = 800;            // min loader duration

  const listeners = {};
  const pollers = new Map();
  let heartbeatTimer = null;
  let pageShownAt = Date.now();

  // ============================================================
  // EVENT BUS
  // ============================================================
  function on(event, cb) {
    if (!listeners[event]) listeners[event] = [];
    listeners[event].push(cb);
    return () => off(event, cb);
  }
  function off(event, cb) {
    if (!listeners[event]) return;
    listeners[event] = listeners[event].filter(f => f !== cb);
  }
  function emit(event, data) {
    (listeners[event] || []).forEach(cb => {
      try { cb(data); } catch (e) { console.error(`[realtime:${event}]`, e); }
    });
  }

  // ============================================================
  // SESSION HEARTBEAT
  // ============================================================
  async function heartbeat() {
    try {
      const res = await fetch('/auth/heartbeat', {
        credentials: 'same-origin',
        headers: { 'Accept': 'application/json' },
      });

      if (res.status === 401 || res.status === 403) {
        let reason = 'unauthorized';
        try { reason = (await res.json()).reason || reason; } catch {}
        handleSessionInvalid(reason);
        return;
      }

      if (res.ok) {
        const data = await res.json();
        emit('user:update', data.user);
      }
    } catch {
      // Network error — silent, try again next tick
    }
  }

  function handleSessionInvalid(reason) {
    stop();
    emit('session:invalid', { reason });
    // Redirect with a small delay so UI can show message if needed
    setTimeout(() => {
      location.replace('/?session=expired&reason=' + encodeURIComponent(reason));
    }, 300);
  }

  // ============================================================
  // SMART POLLER — page-specific data refresh
  // ============================================================
  function poll(key, url, intervalMs, callback) {
    // Stop existing poller with same key
    if (pollers.has(key)) {
      clearInterval(pollers.get(key).timer);
    }
    const run = async () => {
      try {
        const res = await fetch(url, {
          credentials: 'same-origin',
          headers: { 'Accept': 'application/json' },
        });
        if (res.status === 401 || res.status === 403) {
          handleSessionInvalid('unauthorized');
          return;
        }
        if (!res.ok) return;
        const data = await res.json();
        callback(data);
      } catch { /* silent */ }
    };
    run(); // immediate first call
    const timer = setInterval(run, intervalMs);
    pollers.set(key, { timer, url, intervalMs, callback });
  }

  function stopPoll(key) {
    if (pollers.has(key)) {
      clearInterval(pollers.get(key).timer);
      pollers.delete(key);
    }
  }

  function stopAllPollers() {
    pollers.forEach(p => clearInterval(p.timer));
    pollers.clear();
  }

  // ============================================================
  // TAB CHANGE — clear all inputs in old view
  // ============================================================
  function clearViewInputs(viewId) {
    const view = document.getElementById(viewId);
    if (!view) return;

    // Clear text/number/password inputs
    view.querySelectorAll('input').forEach(inp => {
      // Preserve disabled/locked inputs (keys, owner key)
      if (inp.disabled) return;
      // Preserve file inputs — user may have selected
      if (inp.type === 'file') return;

      if (inp.type === 'checkbox' || inp.type === 'radio') {
        // Keep checkbox state? No — clear on tab change
        inp.checked = false;
      } else {
        inp.value = '';
      }
      // Remove error state
      inp.classList.remove('input-error');
      const err = inp.parentElement?.querySelector('.field-error');
      if (err) err.remove();
    });

    // Clear textareas
    view.querySelectorAll('textarea').forEach(ta => {
      ta.value = '';
    });

    // Clear select boxes to first option
    view.querySelectorAll('select').forEach(sel => {
      if (sel.options.length > 0) sel.selectedIndex = 0;
    });
  }

  function attachTabClear(navSelector) {
    const navs = document.querySelectorAll(navSelector);
    let currentView = null;

    // Detect initial active view
    const initial = document.querySelector('.view.active');
    if (initial) currentView = initial.id;

    navs.forEach(nav => {
      nav.addEventListener('click', () => {
        const targetView = 'view-' + (nav.dataset.view || nav.dataset.goto || '');
        if (currentView && currentView !== targetView) {
          clearViewInputs(currentView);
          emit('view:change', { from: currentView, to: targetView });
        }
        currentView = targetView;
      });
    });
  }

  // ============================================================
  // INPUT VALIDATION — real-time field-level
  // ============================================================
  function attachValidation(input, validateFn, opts = {}) {
    const field = input.closest('.field') || input.parentElement;
    if (!field) return;

    // Create error label if not exists
    let errLabel = field.querySelector('.field-error');
    if (!errLabel) {
      errLabel = document.createElement('div');
      errLabel.className = 'field-error';
      errLabel.style.display = 'none';
      // Insert after input wrapper or input
      const anchor = input.closest('.input-wrap') || input.closest('.input-with-icon') || input;
      anchor.parentElement.insertBefore(errLabel, anchor.nextSibling);
    }

    function validate() {
      const result = validateFn(input.value);
      if (result === true) {
        errLabel.style.display = 'none';
        input.classList.remove('input-error');
        input.classList.add('input-valid');
        return true;
      } else {
        errLabel.textContent = result || 'Invalid value';
        errLabel.style.display = 'block';
        input.classList.remove('input-valid');
        input.classList.add('input-error');
        return false;
      }
    }

    // Attach listeners
    input.addEventListener('blur', validate);
    input.addEventListener('input', () => {
      // Live validate only if already in error state
      if (input.classList.contains('input-error')) validate();
    });

    return validate;
  }

  // Common validators
  const validators = {
    uid: (v) => {
      if (!v) return 'UID required';
      if (!/^\d{5,15}$/.test(v.trim())) return 'UID must be 5-15 digits';
      return true;
    },
    required: (label = 'Field') => (v) => {
      if (!v || !v.trim()) return `${label} is required`;
      return true;
    },
    number: (label = 'Value') => (v) => {
      if (!v) return `${label} required`;
      if (isNaN(Number(v))) return `${label} must be a number`;
      if (Number(v) <= 0) return `${label} must be > 0`;
      return true;
    },
    password: (v) => {
      if (!v) return 'Password required';
      if (v.length < 4) return 'Password must be at least 4 characters';
      return true;
    },
    region: (v) => {
      if (!v) return 'Region required';
      const allowed = ['AG', 'IND', 'NX'];
      if (!allowed.includes(v.toUpperCase().trim())) {
        return `Region must be one of: AG, IND, NX`;
      }
      return true;
    },
  };

  // ============================================================
  // PAGE-LOAD MINIMUM DURATION
  // ============================================================
  function ensureMinLoad(cb) {
    const elapsed = Date.now() - pageShownAt;
    const wait = Math.max(0, MIN_LOAD_MS - elapsed);
    setTimeout(cb, wait);
  }

  // ============================================================
  // BACK-BUTTON PROTECTION
  // ============================================================
  function attachBackProtection() {
    // bfcache: when user navigates back, pageshow fires
    window.addEventListener('pageshow', (event) => {
      if (event.persisted) {
        // Page came from bfcache — verify session
        heartbeat();
      }
    });

    // Fallback: visibilitychange re-verify
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') {
        heartbeat();
      }
    });
  }

  // ============================================================
  // START / STOP
  // ============================================================
  function start() {
    if (heartbeatTimer) return;
    // Immediate first heartbeat
    heartbeat();
    heartbeatTimer = setInterval(heartbeat, HEARTBEAT_INTERVAL);
  }

  function stop() {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer);
      heartbeatTimer = null;
    }
    stopAllPollers();
  }

  // ============================================================
  // EXPORT
  // ============================================================
  window.Realtime = {
    on, off, emit,
    start, stop,
    poll, stopPoll,
    ensureMinLoad,
    attachTabClear,
    attachValidation,
    validators,
    clearViewInputs,
    handleSessionInvalid,
    get isRunning() { return !!heartbeatTimer; },
  };

  // Auto-start if page has a session context (login page skips start)
  if (!document.body.dataset.noRealtime) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', () => {
        attachBackProtection();
      });
    } else {
      attachBackProtection();
    }
  }

  console.log('%c⚡ realtime.js loaded', 'color:#22d3ee;font-size:11px;font-weight:700');
})();