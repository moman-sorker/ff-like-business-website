/* ============================================================
   FF LIKE API — Login Page
   ============================================================ */
(() => {
  'use strict';

  const $  = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  // ============================================================
  // LIVE CLOCK
  // ============================================================
  (function clock() {
    const el = $('#clock');
    if (!el) return;
    const tick = () => {
      const d = new Date();
      const pad = (n) => String(n).padStart(2, '0');
      el.textContent = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
    };
    tick();
    setInterval(tick, 1000);
  })();

  // ============================================================
  // PASSWORD / KEY SHOW-TOGGLE
  // ============================================================
  $$('.toggle-pw').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      if (!input) return;
      const isPw = input.type === 'password';
      input.type = isPw ? 'text' : 'password';
      btn.style.color = isPw ? 'var(--cyan)' : 'var(--faint)';
    });
  });

  // ============================================================
  // TERMINAL LOG
  // ============================================================
  const termLog = $('#termLog');
  function logLine(text, kind = '') {
    if (!termLog) return;
    const line = document.createElement('div');
    line.className = 'term-line ' + kind;
    line.textContent = text;
    termLog.appendChild(line);
    termLog.scrollTop = termLog.scrollHeight;

    // keep only last 6 lines
    while (termLog.children.length > 6) {
      termLog.removeChild(termLog.firstChild);
    }
  }

  // ============================================================
  // UI HELPERS
  // ============================================================
  const errorBox   = $('#errorBox');
  const successBox = $('#successBox');
  const errorText  = $('#errorText');
  const successText= $('#successText');
  const submitBtn  = $('#submitBtn');
  const keyLabel   = $('#keyLabel');
  const keyHint    = $('#keyHint');

  function showError(msg) {
    if (!errorBox) return;
    errorText.textContent = msg;
    errorBox.hidden = false;
    successBox.hidden = true;
  }
  function showSuccess(msg) {
    if (!successBox) return;
    successText.textContent = msg;
    successBox.hidden = false;
    errorBox.hidden = true;
  }
  function clearMessages() {
    errorBox.hidden = true;
    successBox.hidden = true;
  }

  function setLoading(on) {
    submitBtn.disabled = on;
    submitBtn.classList.toggle('loading', on);
  }

  // ============================================================
  // ERROR MESSAGES
  // ============================================================
  const ERRORS = {
    invalid_credentials: 'Invalid username or password',
    invalid_master_key:  'Invalid owner master key',
    key_required:        'Access key is required',
    invalid_key_format:  'Invalid key format. Expected FF-API-… or FF-LK-…',
    expired:             'This key has expired',
    already_assigned:    'This key is already bound to another user',
    account_suspended:   'This account is suspended',
    not_bound:           'Key is not bound yet. Login with key to bind',
    unauthorized:        'Session expired. Please login again',
    login_failed:        'Authentication failed',
  };

  // ============================================================
  // SESSION EXPIRED MESSAGE
  // ============================================================
  (function showSessionMessage() {
    const params = new URLSearchParams(window.location.search);
    const sessionParam = params.get('session');
    const reason = params.get('reason');

    if (sessionParam === 'expired') {
      const msgMap = {
        unauthorized: 'Your session expired. Please login again.',
        account_suspended: 'Your account has been suspended. Contact admin.',
        account_deleted: 'Your account was deleted.',
      };
      const msg = msgMap[reason] || 'Session ended. Please login again.';

      // Use existing showError if available
      setTimeout(() => {
        if (typeof showError === 'function') {
          showError(msg);
          logLine(`session: ${reason || 'expired'}`, 'err');
        }
      }, 300);
    }
  })();

  // ============================================================
  // LIVE KEY LABEL — detect owner vs client
  // ============================================================
  const keyInput = $('#key');
  keyInput?.addEventListener('input', () => {
    const v = keyInput.value.trim();
    if (!v) {
      keyLabel.textContent = 'Access Key';
      keyHint.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg> Owner/Admin/User — enter your assigned key';
    } else if (v.startsWith('FF-API-')) {
      keyLabel.textContent = 'API Key';
      keyHint.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg> Detected: subscription API key';
    } else if (v.startsWith('FF-LK-')) {
      keyLabel.textContent = 'Like Key';
      keyHint.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg> Detected: subscription Like key';
    } else {
      keyLabel.textContent = 'Master Key';
      keyHint.innerHTML = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/></svg> Owner login detected';
    }
  });

  // ============================================================
  // LOGIN SUBMIT
  // ============================================================
  const form = $('#loginForm');

  // ============================================================
  // REMEMBER ME — save/load credentials
  // ============================================================
  const REMEMBER_KEY = 'fflike_remember';

  (function loadRemembered() {
    try {
      const saved = localStorage.getItem(REMEMBER_KEY);
      if (!saved) return;
      const data = JSON.parse(saved);
      if (data.name) $('#name').value = data.name;
      if (data.key) $('#key').value = data.key;
      if (data.remember) $('#rememberMe').checked = true;
    } catch { /* silent */ }
  })();

  function saveRemember(name, key, remember) {
    try {
      if (remember) {
        localStorage.setItem(REMEMBER_KEY, JSON.stringify({ name, key, remember: true }));
      } else {
        localStorage.removeItem(REMEMBER_KEY);
      }
    } catch { /* silent */ }
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    clearMessages();

    const name     = $('#name').value.trim();
    const password = $('#password').value;
    const key      = $('#key').value.trim();

    // ---- client-side validation ----
    if (!name || !password) {
      showError('Username and password are required');
      logLine('validation failed: empty credentials', 'err');
      return;
    }
    if (!key) {
      showError('Access key is required');
      logLine('validation failed: no key', 'err');
      return;
    }

    setLoading(true);
    logLine(`authenticating user ${name}…`);

    const t0 = performance.now();

    try {
      const res = await fetch('/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'same-origin',
        body: JSON.stringify({ name, password, key }),
      });

      let data;
      const text = await res.text();
      try { data = JSON.parse(text); }
      catch { data = { error: text || 'Invalid server response' }; }

      const elapsed = ((performance.now() - t0) / 1000).toFixed(2);

      if (!res.ok) {
        const reason = data.error || 'login_failed';
        const msg = ERRORS[reason] || reason;
        showError(msg);
        logLine(`auth failed (${reason}) in ${elapsed}s`, 'err');
        return;
      }
      // ---- success ----
      const user = data.user || {};
      // 🔥 Save remember me
      saveRemember(name, key, $('#rememberMe').checked);
      
      showSuccess(`Welcome ${user.name}. Redirecting…`);
      logLine(`auth ok — role=${user.role} in ${elapsed}s`, 'ok');

      setTimeout(() => {
        if (user.role === 'owner' || user.role === 'admin') {
          location.href = '/admin';
        } else {
          location.href = '/clients';
        }
      }, 700);

    } catch (err) {
      showError('Network error. Please try again.');
      logLine('network error: ' + err.message, 'err');
    } finally {
      setLoading(false);
    }
  });

  // ============================================================
  // SESSION CHECK — redirect if already logged in
  // ============================================================
  (async () => {
    try {
      const res = await fetch('/auth/me', { credentials: 'same-origin' });
      if (res.ok) {
        const data = await res.json();
        const user = data.user || {};
        if (user.role === 'owner' || user.role === 'admin') {
          location.href = '/admin';
        } else if (user.role === 'user') {
          location.href = '/clients';
        }
      }
    } catch { /* silent */ }
  })();

  // ============================================================
  // BOOT LOG
  // ============================================================
  console.log(
    '%c🔥 FF LIKE API — Auth Terminal',
    'color:#22d3ee;font-size:15px;font-weight:800;text-shadow:0 0 12px #22d3ee'
  );
  console.log(
    '%cSecure access · OB55 · v1.0.0',
    'color:#8b9ab8;font-size:11px'
  );
})();