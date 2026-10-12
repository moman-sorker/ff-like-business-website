/* ============================================================
   FF LIKE API — Client Panel (API + Like Client)
   ============================================================ */
(() => {
  'use strict';

  const $  = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const ERROR_MESSAGES = {
    invalid_account_or_server: 'All tokens exhausted or player not found. Try again in a moment.',
    no_tokens: 'No tokens available. Server refreshing — try again soon.',
    encrypt_failed: 'Request encryption failed. Please retry.',
    after_failed: 'Likes sent but verification failed. Check game.',
    no_key_assigned: 'No key assigned. Contact admin.',
    region_not_allowed: 'Your key does not allow this region.',
    daily_limit_reached: 'Daily credit limit reached. Resets at 12 AM UTC.',
    uid_daily_limit_reached: 'This UID already received max likes today.',
    expired: 'Your key has expired. Contact admin.',
    not_bound: 'Key not bound. Please login again.',
    uid_exists_for_you: 'You already have a job for this UID.',
    invalid_add_likes: 'Likes to add must be greater than 0.',
    duration_exceeds_key: 'Duration exceeds key expiry.',
  };

  function friendlyError(code) {
    return ERROR_MESSAGES[code] || code || 'Something went wrong.';
  }

  function friendlyError(code) {
    return ERROR_MAP[code] || code || 'Something went wrong.';
  }

  // 🔥 Null-safe text setter
  function setText(sel, text) {
    const el = document.querySelector(sel);
    if (el) el.textContent = text;
  }

  function setHTML(sel, html) {
    const el = document.querySelector(sel);
    if (el) el.innerHTML = html;
  }

  function setValue(sel, value) {
    const el = document.querySelector(sel);
    if (el) el.value = value;
  }
  const state = {
    user: null,
    apiKey: null,
    likeKey: null,
    likeUsage: [],
    clientType: null,   // 'api' | 'like'
    view: 'dashboard',
    boostJobs: [],
    autoJobs: [],
    refreshInterval: null,
  };

  // ============================================================
  // HELPERS
  // ============================================================
  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function fmtDate(iso, short = false) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      const opts = short
        ? { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }
        : { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' };
      return d.toLocaleString('en-GB', opts);
    } catch { return iso; }
  }

  function daysBetween(iso) {
    if (!iso) return null;
    try {
      const target = new Date(iso);
      const now = new Date();
      const ms = target - now;
      const d = Math.ceil(ms / (1000 * 60 * 60 * 24));
      return Math.max(0, d);
    } catch { return null; }
  }

  function copyToClipboard(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      return navigator.clipboard.writeText(text).then(() => true).catch(() => legacyCopy(text));
    }
    return Promise.resolve(legacyCopy(text));
  }
  function legacyCopy(text) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.top = '-9999px';
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch { return false; }
  }

  // ============================================================
  // TOASTS / LOADER / MODAL
  // ============================================================
  const TOAST_ICONS = {
    ok:   '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/>',
    err:  '<circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/>',
    info: '<circle cx="12" cy="12" r="10"/><path d="M12 16v-4M12 8h.01"/>',
    warn: '<path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><path d="M12 9v4M12 17h.01"/>',
  };
  function toast(title, msg = '', type = 'info', ms = 4000) {
    const el = document.createElement('div');
    el.className = 'toast ' + type;
    el.innerHTML = `
      <svg class="t-icon" viewBox="0 0 24 24" fill="none" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">${TOAST_ICONS[type] || TOAST_ICONS.info}</svg>
      <div><strong>${escapeHtml(title)}</strong>${msg ? `<p>${escapeHtml(msg)}</p>` : ''}</div>`;
    $('#toasts').appendChild(el);
    setTimeout(() => {
      el.classList.add('out');
      setTimeout(() => el.remove(), 300);
    }, ms);
  }

  function showLoader(text = 'Loading…') {
    $('#loaderText').textContent = text;
    $('#loader').classList.add('show');
  }
  function hideLoader() { $('#loader').classList.remove('show'); }

  let modalResolver = null;
  function confirmModal(title, body) {
    return new Promise((resolve) => {
      $('#modalTitle').textContent = title;
      $('#modalBody').textContent = body;
      $('#modalBg').classList.add('show');
      modalResolver = resolve;
    });
  }
  $('#modalCancel').addEventListener('click', () => {
    $('#modalBg').classList.remove('show');
    modalResolver?.(false);
    modalResolver = null;
  });
  $('#modalConfirm').addEventListener('click', () => {
    $('#modalBg').classList.remove('show');
    modalResolver?.(true);
    modalResolver = null;
  });

  async function api(path, opts = {}) {
    const res = await fetch(path, {
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/json' },
      ...opts,
    });
    let data;
    const text = await res.text();
    try { data = JSON.parse(text); }
    catch { data = { error: text || 'Invalid response' }; }
    if (!res.ok && !data.error) data.error = `HTTP ${res.status}`;
    return { ok: res.ok, data };
  }

  // ============================================================
  // NAV
  // ============================================================
  const TITLES = {
    dashboard: ['Dashboard', 'Your account overview'],
    keys:      ['My Keys', 'Key details & feature status'],
    credit:    ['Credit Use', 'Send likes, boost, and auto jobs'],
    activity:  ['Activity', 'Your personal log'],
    account:   ['Account Info', 'Session & system details'],
  };

  function setView(name) {
    state.view = name;
    $$('.view').forEach(v => v.classList.remove('active'));
    const el = document.getElementById('view-' + name);
    if (el) el.classList.add('active');
    $$('.nav-item').forEach(n => n.classList.toggle('active', n.dataset.view === name));

    const t = TITLES[name] || TITLES.dashboard;
    $('#pageTitle').textContent = t[0];
    $('#pageSub').textContent = t[1];

    if (name === 'activity') loadActivity();
    if (name === 'keys')     renderKeys();
    if (name === 'account')  renderAccount();
    if (name === 'credit')   renderCreditUse();

    closeSidebar();
  }

  $$('.nav-item').forEach(n => n.addEventListener('click', () => setView(n.dataset.view)));
  $$('[data-goto-credit]').forEach(b => {
    b.addEventListener('click', () => setView('credit'));
  });

  function closeSidebar() {
    $('#sidebar').classList.remove('open');
    $('#sidebarOverlay').classList.remove('show');
  }
  $('#hamburger').addEventListener('click', () => {
    $('#sidebar').classList.toggle('open');
    $('#sidebarOverlay').classList.toggle('show');
  });
  $('#sidebarOverlay').addEventListener('click', closeSidebar);

  function attachCopy(btn) {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const key = btn.dataset.copy;
      copyToClipboard(key).then((ok) => {
        if (ok) toast('Copied!', key, 'ok', 2000);
        else toast('Copy failed', 'Select manually', 'warn');
      });
    });
  }

  // ============================================================
  // LOAD USER
  // ============================================================
  async function loadMe() {
    const { ok, data } = await api('/client/me');
    if (!ok) {
      location.href = '/';
      return false;
    }

    state.user = data.user;
    state.apiKey = data.api_key;
    state.likeKey = data.like_key;
    state.likeUsage = data.like_usage || [];

    // 🔥 Client type detection
    if (state.apiKey) state.clientType = 'api';
    else if (state.likeKey) state.clientType = 'like';
    else state.clientType = null;

    const name = data.user.name || 'User';
    $('#userName').textContent = name;
    $('#userRole').textContent = data.user.role;
    $('#userAvatar').textContent = name.charAt(0).toUpperCase();
    $('#welcomeName').textContent = name;
    $('#brandSub').textContent = state.clientType === 'api' ? 'API CLIENT' : 'LIKE CLIENT';

    // Show/hide Credit Use tab (API clients only)
    const creditNav = $('#navCredit');
    if (creditNav) {
      creditNav.style.display = (state.clientType === 'api') ? 'flex' : 'none';
    }

    // Load jobs in background
    loadJobs();

    renderDashboardStats();
    return true;
  }

  async function loadJobs() {
    try {
      const { ok, data } = await api('/client/jobs');
      if (ok) {
        state.boostJobs = data.boost || [];
        state.autoJobs = data.auto || [];
      }
    } catch {}
  }

  // ============================================================
  // DASHBOARD STATS
  // ============================================================
  function renderDashboardStats() {
    const key = state.apiKey || state.likeKey;
    const isLikeClient = state.clientType === 'like';

    if (isLikeClient) {
      // 🔥 Like Client — show: Like Credits Left, Days Remaining, Total Requests, Requests Remaining
      const lk = state.likeKey;
      
      if (lk) {
        const today = new Date().toISOString().slice(0, 10);
        const todayUsage = state.likeUsage.find(u => u.date === today) || { uids: {} };
        const usedToday = Object.keys(todayUsage.uids || {}).length;
        
        $('#statCreditsLeft').textContent = lk.per_uid_per_day;
        $('#statCreditsLeft').closest('.stat-card').querySelector('.stat-label').textContent = 'Like Credits Left';
        $('#statCreditsSub').textContent = 'per UID per day';

        // Days
        const days = daysBetween(lk.expires_at);
        $('#statDays').textContent = days !== null ? days : '—';
        $('#statDays').closest('.stat-card').querySelector('.stat-label').textContent = 'Days Remaining';

        // Total Requests (unique UIDs used today)
        $('#statTotalReq').textContent = usedToday;
        $('#statTotalReq').closest('.stat-card').querySelector('.stat-label').textContent = 'UIDs Today';

        // Requests Remaining (slots left today = per_uid_per_day * current uids - used)
        const remaining = Math.max(0, (lk.per_uid_per_day || 0) - usedToday);
        const jobsCard = $('#statJobs');
        if (jobsCard) {
          jobsCard.textContent = remaining;
          jobsCard.closest('.stat-card').querySelector('.stat-label').textContent = 'Requests Remaining';
          $('#statJobsSub').textContent = `until reset`;
        }
      } else {
        // No like key
        ['#statCreditsLeft', '#statDays', '#statTotalReq', '#statJobs'].forEach(sel => {
          const el = $(sel);
          if (el) el.textContent = '—';
        });
      }

      // Hide Quick Actions Boost + Auto buttons for Like Clients
      document.querySelectorAll('[data-goto-credit="boost"], [data-goto-credit="auto"]').forEach(el => {
        el.style.display = 'none';
      });

      return;
    }

    // API Client (default)
    if (state.apiKey) {
      if (state.apiKey.type === 'unlimited') {
        $('#statCreditsLeft').textContent = '∞';
        $('#statCreditsSub').textContent = 'unlimited';
      } else {
        const remaining = Math.max(0, (state.apiKey.credits_per_day || 0) - (state.apiKey.used_today || 0));
        $('#statCreditsLeft').textContent = remaining;
        $('#statCreditsSub').textContent = `${state.apiKey.used_today || 0}/${state.apiKey.credits_per_day || 0} used`;
      }
    }

    const days = key ? daysBetween(key.expires_at) : null;
    $('#statDays').textContent = days !== null ? days : '—';

    const used = (state.apiKey && state.apiKey.used_today) || 0;
    $('#statTotalReq').textContent = used || '0';

    const activeJobs = (state.boostJobs.filter(j => j.status === 'active').length
                     + state.autoJobs.filter(j => j.status === 'active').length);
    $('#statJobs').textContent = activeJobs;
    $('#statJobsSub').textContent = `${state.boostJobs.length} boost · ${state.autoJobs.length} auto`;
  }

  // ============================================================
  // RENDER MY KEYS
  // ============================================================
  function renderKeys() {
    const ak = state.apiKey;
    const lk = state.likeKey;
    const isLikeClient = state.clientType === 'like';

    // ==================== API KEY CARD ====================
    if (ak && !isLikeClient) {
      const statusCls = ak.status === 'active' ? 'active' : 'danger';
      setText('#apiKeyBadge', ak.status || 'active');
      const statusEl = document.querySelector('#apiKeyStatus');
      if (statusEl) statusEl.className = 'mini-badge ' + statusCls;

      const used = ak.used_today || 0;
      const limit = ak.credits_per_day || 0;
      const pct = ak.type === 'unlimited' ? 0 : Math.min(100, Math.round((used / limit) * 100));
      const daysLeft = daysBetween(ak.expires_at);

      setHTML('#apiKeyDetail', `
        <div class="key-display">
          <span>${escapeHtml(ak.key)}</span>
          <button class="copy-btn" data-copy="${escapeHtml(ak.key)}">Copy</button>
        </div>
        <div class="key-stats">
          <div class="key-stat">
            <div class="key-stat-label">Type</div>
            <div class="key-stat-value cyan">${ak.type === 'unlimited' ? 'Unlimited' : 'Credits'}</div>
          </div>
          <div class="key-stat">
            <div class="key-stat-label">Region</div>
            <div class="key-stat-value violet">${escapeHtml(ak.region || 'ALL')}</div>
          </div>
          <div class="key-stat">
            <div class="key-stat-label">Used Today</div>
            <div class="key-stat-value amber">${used}${ak.type === 'unlimited' ? '' : '/' + limit}</div>
          </div>
          <div class="key-stat">
            <div class="key-stat-label">Days Left</div>
            <div class="key-stat-value green">${daysLeft ?? '—'}</div>
          </div>
        </div>
        ${ak.type === 'unlimited' ? '' : `
          <div class="progress-wrap">
            <div class="progress-info"><span>Daily usage</span><span>${pct}%</span></div>
            <div class="progress-bar">
              <div class="progress-fill ${pct >= 90 ? 'danger' : pct >= 70 ? 'warn' : ''}" style="width:${pct}%"></div>
            </div>
          </div>`}
        <div class="info-list" style="margin-top:14px">
          <div class="info-row"><span>Created</span><span>${escapeHtml(fmtDate(ak.created_at))}</span></div>
          <div class="info-row"><span>Expires</span><span>${escapeHtml(fmtDate(ak.expires_at))}</span></div>
        </div>
      `);
      document.querySelectorAll('#apiKeyDetail .copy-btn').forEach(attachCopy);
      const card = document.querySelector('#apiKeyCard');
      if (card) card.style.display = 'block';
      const title = document.querySelector('#apiKeyCard h3');
      if (title) title.textContent = 'API Key';
    } else {
      const card = document.querySelector('#apiKeyCard');
      if (card) card.style.display = 'none';
    }

    // ==================== LIKE KEY CARD (Like Client) ====================
    if (lk && isLikeClient) {
      const card = document.querySelector('#apiKeyCard');
      if (card) card.style.display = 'block';

      const title = document.querySelector('#apiKeyCard h3');
      if (title) title.textContent = 'Like Key';

      const statusCls = lk.status === 'active' ? 'active' : 'danger';
      setText('#apiKeyStatus', lk.status || 'active');
      const statusEl = document.querySelector('#apiKeyStatus');
      if (statusEl) statusEl.className = 'mini-badge pink';

      const daysLeft = daysBetween(lk.expires_at);

      setHTML('#apiKeyDetail', `
        <div class="key-display pink">
          <span>${escapeHtml(lk.key)}</span>
          <button class="copy-btn" data-copy="${escapeHtml(lk.key)}">Copy</button>
        </div>
        <div class="key-stats">
          <div class="key-stat">
            <div class="key-stat-label">Per UID / Day</div>
            <div class="key-stat-value pink">${lk.per_uid_per_day}</div>
          </div>
          <div class="key-stat">
            <div class="key-stat-label">Days Left</div>
            <div class="key-stat-value green">${daysLeft ?? '—'}</div>
          </div>
        </div>
        <div class="info-list" style="margin-top:14px">
          <div class="info-row"><span>Created</span><span>${escapeHtml(fmtDate(lk.created_at))}</span></div>
          <div class="info-row"><span>Expires</span><span>${escapeHtml(fmtDate(lk.expires_at))}</span></div>
        </div>
      `);
      document.querySelectorAll('#apiKeyDetail .copy-btn').forEach(attachCopy);
    }

    // ==================== USE LIKE / BOOST / AUTO CARDS ====================
    if (state.boostJobs.length) {
      const el = document.querySelector('#useBoostCard');
      if (el) el.style.display = 'block';
      setText('#boostJobCount', state.boostJobs.length);
      renderBoostJobsList();
    } else {
      const el = document.querySelector('#useBoostCard');
      if (el) el.style.display = 'none';
    }

    if (state.autoJobs.length) {
      const el = document.querySelector('#useAutoCard');
      if (el) el.style.display = 'block';
      setText('#autoJobCount', state.autoJobs.length);
      renderAutoJobsList();
    } else {
      const el = document.querySelector('#useAutoCard');
      if (el) el.style.display = 'none';
    }

    checkLikeActivity();
  }

  async function checkLikeActivity() {
    try {
      const { ok, data } = await api('/client/logs?action=like&limit=10');
      if (ok && data.logs && data.logs.length) {
        $('#useLikeCard').style.display = 'block';
        
        // Update Use Like card head badge
        const cardHead = document.querySelector('#useLikeCard .key-card-head');
        if (cardHead) {
          cardHead.querySelectorAll('.mini-badge, .badge-group').forEach(el => el.remove());
          const successCount = data.logs.filter(l => l.status === 1).length;
          const badgeGroup = document.createElement('div');
          badgeGroup.className = 'badge-group';
          badgeGroup.innerHTML = `<span class="mini-badge pink">${data.logs.length} RECENT</span>`;
          cardHead.appendChild(badgeGroup);
        }

        // History list
        const rows = data.logs.map(l => {
          const isSuccess = l.status === 1;
          return `
            <div class="like-history-row">
              <div class="lh-main">
                <strong>${escapeHtml(l.uid || '—')}</strong>
                <span>${escapeHtml(l.region || '—')} · ${escapeHtml(fmtDate(l.timestamp, true))}</span>
              </div>
              <div class="lh-meta">
                <span class="lh-added ${isSuccess ? 'ok' : 'warn'}">+${l.added ?? 0}</span>
                <span class="mini-badge ${isSuccess ? 'active' : 'inactive'}">${isSuccess ? 'OK' : 'FAIL'}</span>
              </div>
            </div>`;
        }).join('');
        $('#useLikeDetail').innerHTML = `<div class="jobs-list">${rows}</div>`;
      } else {
        $('#useLikeCard').style.display = 'none';
      }
    } catch {}
  }

  function renderBoostJobsList() {
    const successTotal = state.boostJobs.reduce((s, j) => s + (j.success_count || 0), 0);
    const failTotal = state.boostJobs.reduce((s, j) => s + (j.fail_count || 0), 0);
    const activeCount = state.boostJobs.filter(j => j.status === 'active').length;

    // Update card head badges
    const badgeRow = `
      <span class="mini-badge ${activeCount > 0 ? 'active' : 'inactive'}">${activeCount} ACTIVE</span>
      <span class="mini-badge cyan">✓ ${successTotal}</span>
      <span class="mini-badge danger">✗ ${failTotal}</span>
    `;
    const cardHead = document.querySelector('#useBoostCard .key-card-head');
    if (cardHead) {
      // Remove old badges
      cardHead.querySelectorAll('.mini-badge, .badge-group').forEach(el => el.remove());
      // Add new badge group
      const badgeGroup = document.createElement('div');
      badgeGroup.className = 'badge-group';
      badgeGroup.innerHTML = badgeRow;
      cardHead.appendChild(badgeGroup);
    }

    const rows = state.boostJobs.slice(0, 10).map(j => {
      const isPending = j.status === 'pending';
      const start = j.start_likes ?? '—';
      const target = j.target_likes ?? '—';
      const add = j.add_likes || 0;
      const current = j.current_likes ?? j.start_likes ?? null;
      const done = (current != null && j.start_likes != null)
        ? (current - j.start_likes) : 0;
      const pct = add > 0 ? Math.min(100, Math.round((done / add) * 100)) : 0;
      
      const statusCls = j.status === 'active' ? 'active'
                      : j.status === 'completed' ? 'cyan'
                      : j.status === 'pending' ? 'warn'
                      : j.status === 'terminated' ? 'danger'
                      : 'inactive';

      const progressText = isPending 
        ? '⏳ Initializing…' 
        : `${pct}%`;
      const subline = isPending
        ? `${escapeHtml(j.nickname || '—')} · +${add} · pending`
        : `${escapeHtml(j.nickname || '—')} · ${start} → ${target} (+${add}) · ${pct}%`;

      return `
        <div class="job-row">
          <div class="job-main">
            <strong>${escapeHtml(j.uid)}</strong>
            <span>${subline}</span>
          </div>
          <div class="job-meta">
            <span class="mini-badge ${statusCls}">${escapeHtml(j.status)}</span>
            <button class="job-del" data-job-type="boost" data-job-uid="${escapeHtml(j.uid)}" title="Delete">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
              </svg>
            </button>
          </div>
        </div>`;
    }).join('');
    
    $('#useBoostDetail').innerHTML = `<div class="jobs-list">${rows}</div>`;
    bindJobDeleteButtons();
  }

  function renderAutoJobsList() {
    const successTotal = state.autoJobs.reduce((s, j) => s + (j.success_count || 0), 0);
    const failTotal = state.autoJobs.reduce((s, j) => s + (j.fail_count || 0), 0);
    const activeCount = state.autoJobs.filter(j => j.status === 'active').length;

    const badgeRow = `
      <span class="mini-badge ${activeCount > 0 ? 'active' : 'inactive'}">${activeCount} ACTIVE</span>
      <span class="mini-badge cyan">✓ ${successTotal}</span>
      <span class="mini-badge danger">✗ ${failTotal}</span>
    `;
    const cardHead = document.querySelector('#useAutoCard .key-card-head');
    if (cardHead) {
      cardHead.querySelectorAll('.mini-badge, .badge-group').forEach(el => el.remove());
      const badgeGroup = document.createElement('div');
      badgeGroup.className = 'badge-group';
      badgeGroup.innerHTML = badgeRow;
      cardHead.appendChild(badgeGroup);
    }

    const rows = state.autoJobs.slice(0, 5).map(j => {
      const statusCls = j.status === 'active' ? 'active'
                      : j.status === 'terminated' ? 'danger'
                      : j.status === 'expired' ? 'warn'
                      : 'inactive';
      return `
        <div class="job-row">
          <div class="job-main">
            <strong>${escapeHtml(j.uid)}</strong>
            <span>${escapeHtml(j.nickname || '—')} · ${j.duration_days}d</span>
          </div>
          <div class="job-meta">
            <span class="mini-badge ${statusCls}">${escapeHtml(j.status)}</span>
            <span class="job-pct">${escapeHtml(fmtDate(j.expires_at, true))}</span>
            <button class="job-del" data-job-type="auto" data-job-uid="${escapeHtml(j.uid)}" title="Delete">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                <path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/>
              </svg>
            </button>
          </div>
        </div>`;
    }).join('');

    $('#useAutoDetail').innerHTML = `<div class="jobs-list">${rows}</div>`;
    bindJobDeleteButtons();
  }

  function bindJobDeleteButtons() {
    document.querySelectorAll('.job-del').forEach(btn => {
      btn.addEventListener('click', async (e) => {
        e.stopPropagation();
        const type = btn.dataset.jobType;
        const uid = btn.dataset.jobUid;
        if (!await confirmModal('Delete Job', `Delete ${type} job for UID ${uid}?`)) return;

        showLoader('Deleting…');
        // Owner admin route (delete via admin endpoint? No — clients need own endpoint)
        const r = await api(`/client/job/${type}/${encodeURIComponent(uid)}`, {
          method: 'DELETE',
        });
        hideLoader();

        if (r.ok) {
          toast('Job deleted', uid, 'ok');
          await loadMe();
        } else {
          toast('Failed', r.data.error || '', 'err');
        }
      });
    });
  }

  // ============================================================
  // RENDER CREDIT USE (API clients only)
  // ============================================================
  function renderCreditUse() {
    const ak = state.apiKey;
    if (!ak) return;

    // 🔥 Update credit badge with real remaining
    const badge = document.getElementById('creditUseBadge');
    if (badge) {
      if (ak.type === 'unlimited') {
        badge.textContent = '∞ CREDITS';
      } else {
        const remaining = Math.max(0, (ak.credits_per_day || 0) - (ak.used_today || 0));
        badge.textContent = `${remaining}/${ak.credits_per_day || 0} CREDITS`;
      }
    }

    // Key region lock
    const keyRegion = ak.region || 'ALL';

    // Autofill keys (all 3 forms)
    $('#clKey').value = ak.key;
    $('#cbKey').value = ak.key;
    $('#caKey').value = ak.key;

    // Apply region lock to all 3 forms
    applyRegionLock('cl', keyRegion);
    applyRegionLock('cb', keyRegion);
    applyRegionLock('ca', keyRegion);
  }

  function applyRegionLock(prefix, keyRegion) {
    const regionInput = document.getElementById(prefix + 'Region');
    const lockIcon = document.getElementById(prefix + 'RegionLock');
    if (!regionInput || !lockIcon) return;

    if (keyRegion === 'ALL') {
      regionInput.disabled = false;
      regionInput.placeholder = 'AG / IND / NX';
      if (['AG','IND','NX'].includes(regionInput.value)) {
        regionInput.value = '';
      }
      lockIcon.style.display = 'none';
    } else {
      regionInput.disabled = true;
      regionInput.value = keyRegion;
      lockIcon.style.display = 'block';
    }
  }

  // ============================================================
  // CREDIT USE — Like form
  // ============================================================
const clForm = $('#creditLikeForm');
if (clForm) {
  clForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const uid = $('#clUid').value.trim();
    const region = ($('#clRegion').value || '').toUpperCase().trim();

    if (!uid || !/^\d{5,15}$/.test(uid)) return toast('Invalid UID', '', 'warn');
    if (!region) return toast('Missing region', '', 'warn');

    showLoader('Sending like…');
    const r = await api('/client/like', {
      method: 'POST',
      body: JSON.stringify({ uid, region }),
    });
    hideLoader();

    const d = r.data || {};

    // 🔥 Error handling FIRST
    if (!r.ok || d.error) {
      const msg = friendlyError(d.error);                    // ✅ d defined here
      $('#clResponse').innerHTML = `
        <div class="response-panel">
          <div class="resp-status error">
            <div class="resp-status-icon">❌</div>
            <div class="resp-status-text">
              <strong>Failed</strong>
              <span>${escapeHtml(msg)}</span>
            </div>
          </div>
        </div>`;
      toast('Failed', msg, 'err', 6000);
      return;
    }

      $('#clResponse').innerHTML = `
        <div class="response-panel">
          <div class="resp-status ${isSuccess ? 'ok' : 'warn'}">
            <div class="resp-status-icon">${isSuccess ? '✅' : '⚠️'}</div>
            <div class="resp-status-text">
              <strong>${isSuccess ? 'Success' : 'No Change'}</strong>
              <span>${isSuccess ? `+${d.added} likes delivered` : 'Target may have hit daily cap'}</span>
            </div>
          </div>
          
          <div class="resp-grid">
            <div class="resp-item">
              <div class="resp-key">Nickname</div>
              <div class="resp-val">${escapeHtml(d.nickname || '—')}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Region</div>
              <div class="resp-val">${escapeHtml(d.region || '—')}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Player UID</div>
              <div class="resp-val mono">${escapeHtml(d.uid || uid)}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Before</div>
              <div class="resp-val mono">${d.before ?? '—'}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">After</div>
              <div class="resp-val mono">${d.after ?? '—'}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Added</div>
              <div class="resp-val mono green">+${d.added ?? 0}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Tokens Used</div>
              <div class="resp-val mono">${d.tokens_used ?? 0}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Credits Remaining</div>
              <div class="resp-val mono cyan">${remaining != null ? `${remaining}/${limit}` : 'unlimited'}</div>
            </div>
          </div>
        </div>`;
      toast('Success', `+${d.added ?? 0} likes`, 'ok', 4000);
      setTimeout(loadMe, 800);
    });
  }

  // ============================================================
  // CREDIT USE — Boost form
  // ============================================================
  const cbForm = $('#creditBoostForm');
  if (cbForm) {
    cbForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const uid = $('#cbUid').value.trim();
      const region = ($('#cbRegion').value || '').toUpperCase().trim();
      const addLikes = Number($('#cbAddLikes').value);    // 🔥 renamed

      if (!uid || !/^\d{5,15}$/.test(uid)) return toast('Invalid UID', '', 'warn');
      if (!region) return toast('Missing region', '', 'warn');
      if (!addLikes || addLikes <= 0) return toast('Invalid amount', '', 'warn');

      if (!await confirmModal('Create Boost Job', `Add ${addLikes} likes to UID ${uid}?`)) return;

      showLoader('Creating boost job…');
      const r = await api('/client/boost/create', {
        method: 'POST',
        body: JSON.stringify({ uid, region, add_likes: addLikes }),   // 🔥 renamed
      });
      hideLoader();

      const d = r.data || {};
      if (!r.ok || d.error) {
        // error handling...
        return;
      }

      const isActive = d.status === 'active';
      const statusCls = isActive ? 'ok' : 'warn';
      const statusIcon = isActive ? '✅' : '⏳';
      const statusLabel = isActive ? 'Auto Job Active' : 'Auto Job Pending';
      const statusDesc = isActive
        ? `Start: ${d.start_likes} likes`
        : 'Initializing via scheduler (max 15 min)';

      $('#caResponse').innerHTML = `
        <div class="response-panel">
          <div class="resp-status ${statusCls}">
            <div class="resp-status-icon">${statusIcon}</div>
            <div class="resp-status-text">
              <strong>${statusLabel}</strong>
              <span>${statusDesc}</span>
            </div>
          </div>
          <div class="resp-grid">
            <div class="resp-item">
              <div class="resp-key">UID</div>
              <div class="resp-val mono">${escapeHtml(uid)}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Region</div>
              <div class="resp-val">${escapeHtml(region)}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Duration</div>
              <div class="resp-val">${days} days</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Start Likes</div>
              <div class="resp-val mono">${d.start_likes ?? '—'}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Expires</div>
              <div class="resp-val mono">${escapeHtml(fmtDate(d.expires_at))}</div>
            </div>
            <div class="resp-item">
              <div class="resp-key">Status</div>
              <div class="resp-val mono ${isActive ? 'green' : 'amber'}">
                ${isActive ? 'ACTIVE' : 'PENDING'}
              </div>
            </div>
          </div>
        </div>`;

      if (isActive) {
        toast('Boost Job Active', `${d.start_likes} → ${d.target_likes}`, 'ok', 5000);
      } else {
        toast('Boost Job Pending', 'Init via scheduler (max 15 min)', 'warn', 5000);
      }
      cbForm.reset();
      await loadMe();
    });
  }
  // ============================================================
  // CREDIT USE — Auto form
  // ============================================================
  const caForm = $('#creditAutoForm');
  if (caForm) {
    caForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const uid = $('#caUid').value.trim();
      const region = ($('#caRegion').value || '').toUpperCase().trim();
      const days = Number($('#caDuration').value);

      if (!uid || !/^\d{5,15}$/.test(uid)) return toast('Invalid UID', '', 'warn');
      if (!region) return toast('Missing region', '', 'warn');
      if (!days || days <= 0) return toast('Invalid duration', '', 'warn');

      if (!await confirmModal('Create Auto Job', `${days} day auto-like for UID ${uid}?`)) return;

      showLoader('Creating auto job…');
      const r = await api('/client/auto/create', {
        method: 'POST',
        body: JSON.stringify({ uid, region, duration_days: days }),
      });
      hideLoader();

      const d = r.data || {};
      if (!r.ok || d.error) {
        let msg = d.error || 'Failed';
        if (d.error === 'duration_exceeds_key') {
          msg = `Duration exceeds key expiry. Max allowed: ${d.max_days} days.`;
        }
        $('#caResponse').innerHTML = `<div class="response-box error">
❌ ${escapeHtml(msg)}
        </div>`;
        toast('Failed', msg, 'err', 6000);
        return;
      }

      $('#caResponse').innerHTML = `<div class="response-box">
✅ Auto job created
────────────────────────
UID: ${escapeHtml(uid)}
Region: ${escapeHtml(region)}
Duration: ${days} days
Expires: ${escapeHtml(fmtDate(d.expires_at))}
────────────────────────
Runs daily at 00:00 UTC
      </div>`;

      toast('Auto job created', `UID ${uid}`, 'ok', 4000);
      caForm.reset();
      await loadMe();
    });
  }

  // ============================================================
  // ACTIVITY
  // ============================================================
  async function loadActivity() {
    const { ok, data } = await api('/client/logs?limit=100');
    if (!ok) return toast('Failed', data.error || '', 'err');

    const logs = data.logs || [];
    if (!logs.length) {
      $('#activityList').innerHTML = '<div class="empty-state">No activity yet</div>';
      return;
    }

    $('#activityList').innerHTML = logs.map(l => {
      const action = l.action || '';
      let cls = 'other';
      if (action === 'like') cls = 'like';
      else if (action === 'login' || action === 'logout') cls = 'login';
      else if (action.startsWith('boost')) cls = 'boost';
      else if (action.startsWith('auto')) cls = 'auto';
      else if (action.startsWith('key')) cls = 'key';

      const body = [
        l.uid ? `· ${escapeHtml(l.uid)}` : '',
        l.added !== undefined && l.added !== null ? `· +${l.added}` : '',
        l.reason ? `· ${escapeHtml(l.reason)}` : '',
        l.error ? `· ${escapeHtml(l.error)}` : '',
      ].filter(Boolean).join(' ');

      return `
        <div class="log-item">
          <span class="log-time">${escapeHtml(fmtDate(l.timestamp))}</span>
          <span class="log-body">${body || '—'}</span>
          <span class="log-action ${cls}">${escapeHtml(action)}</span>
        </div>`;
    }).join('');
  }

  // ============================================================
  // ACCOUNT
  // ============================================================
  function renderAccount() {
    const u = state.user || {};
    const key = state.apiKey || state.likeKey;

    $('#accName').textContent = u.name || '—';
    $('#accRole').textContent = u.role || '—';
    $('#accStatus').textContent = u.status || 'active';
    $('#accCreated').textContent = key ? fmtDate(key.created_at) : '—';
    // $('#accHost').textContent = window.location.host;
  }

  // ============================================================
  // LOGOUT / REFRESH
  // ============================================================
  async function doLogout() {
    if (!await confirmModal('Logout', 'End your session?')) return;
    await api('/auth/logout', { method: 'POST' });
    location.href = '/';
  }
  $('#logoutBtn').addEventListener('click', doLogout);
  $('#logoutBtn2').addEventListener('click', doLogout);

  $('#refreshBtn').addEventListener('click', async () => {
    showLoader('Refreshing…');
    await loadMe();
    hideLoader();
    toast('Refreshed', '', 'ok', 2000);
  });
  $('#refreshActivity').addEventListener('click', loadActivity);

  // ============================================================
  // THEME PICKER
  // ============================================================
  (function initThemePicker() {
    const grid = $('#themeGrid');
    if (!grid || !window.FFThemes) return;

    const themes = window.FFThemes.list;
    const current = window.FFThemes.current;

    grid.innerHTML = Object.entries(themes).map(([key, t]) => `
      <div class="theme-card ${key === current ? 'active' : ''}" data-theme="${key}">
        <div class="theme-icon">${t.icon}</div>
        <div class="theme-name">${escapeHtml(t.name)}</div>
      </div>
    `).join('');

    grid.querySelectorAll('.theme-card').forEach(card => {
      card.addEventListener('click', () => {
        const theme = card.dataset.theme;
        window.FFThemes.apply(theme);
        const label = $('#currentThemeLabel');
        if (label) label.textContent = theme;
        toast('Theme Applied', themes[theme].name, 'ok', 2000);
      });
    });

    const label = $('#currentThemeLabel');
    if (label) label.textContent = current;
  })();
  // ============================================================
  // BOOT
  // ============================================================
  (async () => {
    showLoader('Loading your account…');

    const [ok] = await Promise.all([
      loadMe(),
      new Promise(r => Realtime.ensureMinLoad(r)),
    ]);

    hideLoader();
    if (!ok) return;

    setView('dashboard');

    // 🔥 START REALTIME
    Realtime.start();
    Realtime.attachTabClear('.nav-item, [data-goto-credit]');

    // 🔥 Live updates
    Realtime.on('user:update', (user) => {
      if (!user) return;
      state.user = user;
      $('#userName').textContent = user.name;
      $('#userRole').textContent = (user.role || 'user').toUpperCase();
      $('#userAvatar').textContent = (user.name || '?').charAt(0).toUpperCase();
    });

    // 🔥 Live poll credits every 5s when dashboard/keys active
    Realtime.poll('client-me', '/client/me', 5000, (data) => {
      state.apiKey = data.api_key;
      state.likeKey = data.like_key;
      state.likeUsage = data.like_usage || [];
      renderDashboardStats();
      if (state.view === 'keys') renderKeys();
    });

    // 🔥 Validation
    const clUid = document.querySelector('#clUid');
    if (clUid) Realtime.attachValidation(clUid, Realtime.validators.uid);

    const cbUid = document.querySelector('#cbUid');
    if (cbUid) Realtime.attachValidation(cbUid, Realtime.validators.uid);

    const caUid = document.querySelector('#caUid');
    if (caUid) Realtime.attachValidation(caUid, Realtime.validators.uid);

    const useKeyUid = document.querySelector('#useKeyUid');
    if (useKeyUid) Realtime.attachValidation(useKeyUid, Realtime.validators.uid);

    const cbAddLikes = document.querySelector('#cbAddLikes');
    if (cbAddLikes) Realtime.attachValidation(cbAddLikes, Realtime.validators.number('Amount'));

    const caDuration = document.querySelector('#caDuration');
    if (caDuration) Realtime.attachValidation(caDuration, Realtime.validators.number('Duration'));

    const clRegion = document.querySelector('#clRegion');
    if (clRegion && !clRegion.disabled) {
      Realtime.attachValidation(clRegion, Realtime.validators.region);
    }

    console.log('%c🔥 FF LIKE API — Client Portal', 'color:#22d3ee;font-size:14px;font-weight:800');
    console.log(`%cClient type: ${state.clientType}`, 'color:#8b9ab8;font-size:11px');
    console.log('%c⚡ Real-time sync active', 'color:#22c55e;font-size:11px;font-weight:700');
  })();

})();