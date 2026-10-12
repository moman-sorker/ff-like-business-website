/* ============================================================
   FF LIKE API — Admin Panel
   ============================================================ */
(() => {
  'use strict';

  const $  = (s) => document.querySelector(s);
  const $$ = (s) => Array.from(document.querySelectorAll(s));

  const state = {
    user: null,
    view: 'dashboard',
    refreshInterval: null,
  };
  // ============================================================
  // SESSION INVALID HANDLER
  // ============================================================
  window.addEventListener('DOMContentLoaded', () => {
    if (window.Realtime) {
      Realtime.on('session:invalid', ({ reason }) => {
        console.warn('[admin] session invalid:', reason);
        // Realtime.js handles the redirect itself
      });
    }
  });
  // ============================================================
  // HELPERS
  // ============================================================
  function escapeHtml(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
    }[c]));
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    try {
      const d = new Date(iso);
      return d.toLocaleString('en-GB', {
        day: '2-digit', month: 'short', year: '2-digit',
        hour: '2-digit', minute: '2-digit'
      });
    } catch { return iso; }
  }

  // ============================================================
  // CLIPBOARD HELPER — HTTP + HTTPS safe
  // ============================================================
  function copyToClipboard(text) {
    if (navigator.clipboard && typeof navigator.clipboard.writeText === 'function') {
      return navigator.clipboard.writeText(text)
        .then(() => true)
        .catch(() => legacyCopy(text));
    }
    return Promise.resolve(legacyCopy(text));
  }

  function legacyCopy(text) {
    try {
      const ta = document.createElement('textarea');
      ta.value = text;
      ta.style.position = 'fixed';
      ta.style.top = '-9999px';
      ta.style.opacity = '0';
      document.body.appendChild(ta);
      ta.focus();
      ta.select();
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      return ok;
    } catch (e) {
      console.error('[copy] failed:', e);
      return false;
    }
  }

  // ============================================================
  // TOASTS
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

  // ============================================================
  // LOADER
  // ============================================================
  function showLoader(text = 'Processing…') {
    $('#loaderText').textContent = text;
    $('#loader').classList.add('show');
  }
  function hideLoader() { $('#loader').classList.remove('show'); }

  // ============================================================
  // CONFIRM MODAL
  // ============================================================
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

  // ============================================================
  // API WRAPPER
  // ============================================================
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
    return { ok: res.ok, status: res.status, data };
  }

  // ============================================================
  // NAVIGATION
  // ============================================================
  const TITLES = {
    dashboard: ['Dashboard', 'System overview'],
    like:      ['Send Likes', 'Owner direct like sender'],
    logs:      ['Activity Logs', 'Real-time event stream'],
    users:     ['Users', 'Manage accounts & roles'],
    apikeys:   ['API Keys', 'Subscription API key management'],
    likekeys:  ['Like Keys', 'Subscription Like key management'],
    boost:     ['Boost Like', 'Milestone-based boost jobs'],
    auto:      ['Auto Like', 'Duration-based auto jobs'],
    settings:  ['Settings', 'Bot & system configuration'],
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

    // load data
    switch (name) {
      case 'dashboard': loadDashboard(); break;
      case 'like': loadOwnerLikeView(); break;
      case 'users':     loadUsers();     break;
      case 'apikeys':   loadApiKeys();   break;
      case 'likekeys':  loadLikeKeys();  break;
      case 'boost':     loadBoost();     break;
      case 'auto':      loadAuto();      break;
      case 'logs':      loadLogs();      break;
      case 'settings':  loadBots();      break;
    }

    closeSidebar();
  }

  $$('.nav-item').forEach(n => {
    n.addEventListener('click', () => setView(n.dataset.view));
  });
  $$('[data-goto]').forEach(b => {
    b.addEventListener('click', () => setView(b.dataset.goto));
  });

  // ============================================================
  // SIDEBAR TOGGLE
  // ============================================================
  function closeSidebar() {
    $('#sidebar').classList.remove('open');
    $('#sidebarOverlay').classList.remove('show');
  }
  $('#hamburger').addEventListener('click', () => {
    $('#sidebar').classList.toggle('open');
    $('#sidebarOverlay').classList.toggle('show');
  });
  $('#sidebarOverlay').addEventListener('click', closeSidebar);

  // ============================================================
  // LOAD: AUTH / ME
  // ============================================================
  async function loadMe() {
      try {
        const { ok, data } = await api('/auth/me');
        if (!ok) {
          location.href = '/';
          return false;
        }

        const u = data.user || {};
        state.user = u;

        // 🔥 Robust defaults — never leaves as "—"
        $('#userName').textContent = u.name || 'unknown';
        $('#userRole').textContent = (u.role || 'user').toUpperCase();
        $('#userAvatar').textContent = (u.name || '?').charAt(0).toUpperCase();
        $('#infoRole').textContent = u.role || '—';

        console.log('[loadMe] user set:', u);
        return true;

      } catch (e) {
        console.error('[loadMe] failed:', e);
        location.href = '/';
        return false;
      }
  }

  // ============================================================
  // LOAD: DASHBOARD
  // ============================================================
  async function loadDashboard() {
    const { ok, data } = await api('/admin/stats');
    if (!ok) return toast('Failed', data.error || 'Could not load stats', 'err');

    $('#statAccounts').textContent = data.accounts ?? '—';

    const ak = data.api_keys || {};
    $('#statApiKeys').textContent = ak.total ?? '—';
    $('#statApiKeysSub').textContent = `${ak.bound || 0} bound · ${ak.credits || 0} credits · ${ak.unlimited || 0} unlimited`;

    const lk = data.like_keys || {};
    $('#statLikeKeys').textContent = lk.total ?? '—';
    $('#statLikeKeysSub').textContent = `${lk.bound || 0} bound · ${lk.unbound || 0} unbound`;

    const a = data.activity || {};
    $('#statLikesToday').textContent = a.likes_today ?? '—';
    $('#statLikesSub').textContent = `${a.success_today || 0} success · ${a.total_logs || 0} total logs`;

    $('#statBoost').textContent = data.boost_active ?? '—';
    $('#statAuto').textContent  = data.auto_active ?? '—';

    // Scheduler
    const s = await api('/admin/scheduler/status');
    if (s.ok) {
      const jobs = (s.data.jobs || []).map(j => `
        <div class="info-row">
          <span>${escapeHtml(j.id)}</span>
          <span>${escapeHtml(fmtDate(j.next_run))}</span>
        </div>`).join('');
      $('#schedulerBox').innerHTML = `
        <div class="info-list">
          <div class="info-row"><span>Status</span><span>${s.data.running ? '✅ Running' : '❌ Stopped'}</span></div>
          <div class="info-row"><span>Timezone</span><span>${escapeHtml(s.data.timezone || 'UTC')}</span></div>
          ${jobs}
        </div>`;
    } else {
      $('#schedulerBox').innerHTML = `<div class="empty-state">Scheduler unavailable</div>`;
    }
  }
  async function loadOwnerLikeView() {
      const { ok, data } = await api('/admin/owner-key-preview');
      if (ok) {
        $('#ownerLikeKey').value = data.key || '—';

        // 🔥 Dynamic hint
        const hintRow = document.querySelector('#view-like .hint-row');
        if (hintRow) {
          if (data.is_owner) {
            hintRow.textContent = '💡 Owner key from .env — no credits deducted';
          } else {
            hintRow.textContent = '💡 Your assigned key — credits deducted per API call';
          }
        }

        // 🔥 Update page title
        const pageTitle = $('#pageTitle');
        if (pageTitle) {
          pageTitle.textContent = data.is_owner
            ? 'Send Likes (Owner Direct)'
            : 'Send Likes (Admin)';
        }
      } else {
        $('#ownerLikeKey').value = '—';
      }
  }

  // ============================================================
  // ADMIN KEY REFRESH — generate random API key
  // ============================================================
  const adminKeyRefreshBtn = $('#adminKeyRefresh');
  if (adminKeyRefreshBtn) {
    adminKeyRefreshBtn.addEventListener('click', async () => {
      adminKeyRefreshBtn.disabled = true;
      adminKeyRefreshBtn.classList.add('spinning');

      const r = await api('/admin/keys/api/generate', {
        method: 'POST',
        body: JSON.stringify({
          credits_per_day: null,
          duration_days: 30,
          region: 'ALL',
          admin_key: true,                  // 🔥 FF-AD prefix
        }),
      });

      adminKeyRefreshBtn.disabled = false;
      adminKeyRefreshBtn.classList.remove('spinning');

      if (r.ok) {
        $('#newAdminKey').value = r.data.key;
        toast('Key generated', 'Fill rest and click Create Admin', 'ok', 3000);
      } else {
        toast('Failed', r.data.error || 'Could not generate key', 'err');
      }
    });
  }

  // ============================================================
  // OWNER DIRECT LIKE
  // ============================================================
  const ownerLikeForm = $('#ownerLikeForm');
  const errMap = {
    invalid_account_or_server: 'All tokens exhausted or player not found. Try again in a moment.',
    uid_daily_limit_reached: '⚠️ This UID already received max likes today. Try again after 24h reset (00:00 UTC).',
    no_tokens: 'No tokens available. Server refreshing — try again soon.',
    encrypt_failed: 'Request encryption failed. Please retry.',
    after_failed: 'Likes sent but verification failed. Check game.',
    no_key_assigned: 'No key assigned. Contact admin.',
    region_not_allowed: 'Your key does not allow this region.',
    daily_limit_reached: 'Daily credit limit reached. Resets at 12 AM UTC.',
    expired: 'Your key has expired. Contact admin.',
  };

  if (ownerLikeForm) {
    ownerLikeForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const uid = $('#ownerLikeUid').value.trim();
      const region = $('#ownerLikeRegion').value;
      if (!uid) return toast('Missing UID', '', 'warn');

      showLoader('Sending likes…');
      const r = await api('/admin/like', {
        method: 'POST',
        body: JSON.stringify({ uid, region }),
      });
      hideLoader();

      // 🔥 FIX: Check error field, not just HTTP status
      const d = r.data || {};
      const hasError = !r.ok || d.error;

      if (!hasError) {
        const d = r.data;
        const isSuccess = d.status === 1;
        
        $('#ownerLikeResult').innerHTML = `
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
                <div class="resp-val mono">${escapeHtml(d.uid || '—')}</div>
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
                <div class="resp-key">Tokens Deleted</div>
                <div class="resp-val mono">${d.tokens_deleted ?? 0}</div>
              </div>
            </div>
          </div>`;
        toast('Success', `+${d.added ?? 0} likes delivered`, 'ok');
      } else {
        // 🔥 Show real error
        const err = d.error || 'Unknown error';
        const errMap = {
          invalid_account_or_server: 'All available tokens are exhausted or invalid for this region. Please try again later or use a different region.',
          no_tokens: 'No tokens available for this region. Token manager will refresh soon.',
          encrypt_failed: 'Request encryption failed. Please retry.',
          after_failed: 'Likes may have been sent, but the result could not be fetched.',
        };
        const msg = errMap[err] || err;

        $('#ownerLikeResult').innerHTML = `
          <div class="empty-state" style="color:var(--red);padding:24px;text-align:center">
            ❌ ${escapeHtml(msg)}
          </div>`;

        toast('Failed', msg, 'err', 6000);
      }
    });
  }

  // ============================================================
  // BROADCAST MESSAGE
  // ============================================================
  const broadcastBtn = $('#broadcastSendBtn');
  if (broadcastBtn) {
    broadcastBtn.addEventListener('click', async () => {
      const msg = $('#broadcastMessage').value.trim();
      if (!msg) return toast('Empty message', 'Type something first', 'warn');
      if (msg.length > 2000) return toast('Too long', 'Max 2000 characters', 'warn');

      if (!await confirmModal('Broadcast', `Send this to ALL Telegram + Discord channels?`)) return;

      showLoader('Sending broadcast…');
      const r = await api('/admin/bots/broadcast', {
        method: 'POST',
        body: JSON.stringify({ message: msg }),
      });
      hideLoader();

      if (r.ok) {
        const res = r.data;
        toast('Broadcast sent',
              `Telegram: ${res.telegram ? '✅' : '❌'} · Discord: ${res.discord ? '✅' : '❌'}`,
              'ok', 5000);
        $('#broadcastMessage').value = '';
      } else {
        toast('Failed', r.data.error || '', 'err');
      }
    });
  }

  // ============================================================
  // LOAD: USERS
  // ============================================================
    async function loadUsers() {
    const isOwner = state.user?.role === 'owner';

    // Show / hide create form
    if ($('#createAdminPanel')) {
        $('#createAdminPanel').style.display = isOwner ? 'block' : 'none';
    }
    if ($('#adminInfoPanel')) {
        $('#adminInfoPanel').style.display = isOwner ? 'none' : 'block';
    }

    const { ok, data } = await api('/admin/users');
    if (!ok) return toast('Failed', data.error || '', 'err');

    const users = data.users || [];
    $('#userCount').textContent = users.length;

    if (!users.length) {
        $('#usersTable').innerHTML = '<div class="empty-state">No users yet</div>';
        return;
    }

    const me = state.user || {};

    const rows = users.map(u => {
        // delete permission
        let canDelete = false;
        if (u.role === 'user') canDelete = true;
        else if (u.role === 'admin' && me.role === 'owner') canDelete = true;

        // status toggle permission
        let canToggle = false;
        if (u.role === 'user') canToggle = true;
        else if (u.role === 'admin' && me.role === 'owner') canToggle = true;
    const apiKeyCell = u.assigned_api_key
      ? `<div class="key-cell"><span>${escapeHtml(u.assigned_api_key)}</span>
          <button class="mini-copy" data-copy="${escapeHtml(u.assigned_api_key)}" title="Copy">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <rect x="9" y="9" width="13" height="13" rx="2"/>
              <path d="M5 15V5a2 2 0 0 1 2-2h10"/>
            </svg>
          </button></div>`
      : '—';

    const likeKeyCell = u.assigned_like_key
      ? `<div class="key-cell"><span>${escapeHtml(u.assigned_like_key)}</span>
          <button class="mini-copy" data-copy="${escapeHtml(u.assigned_like_key)}" title="Copy">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2">
              <rect x="9" y="9" width="13" height="13" rx="2"/>
              <path d="M5 15V5a2 2 0 0 1 2-2h10"/>
            </svg>
          </button></div>`
      : '—';
        return `
        <tr>
            <td class="txt">${escapeHtml(u.name)}</td>
            <td><span class="mini-badge ${
            u.role === 'owner' ? 'pink' : u.role === 'admin' ? 'violet' : 'cyan'
            }">${escapeHtml(u.role)}</span></td>
            <td><span class="mini-badge ${u.status === 'active' ? 'active' : 'danger'}">${escapeHtml(u.status || 'active')}</span></td>
            <td class="mono-sm">${apiKeyCell}</td>
            <td class="mono-sm">${likeKeyCell}</td>
            <td>${escapeHtml(fmtDate(u.created_at))}</td>
            <td>
            <div class="row-actions">
                ${canToggle ? `
                <button class="action-btn ${u.status === 'active' ? 'warn' : 'ok'}"
                        data-action="toggle-user" data-name="${escapeHtml(u.name)}" data-status="${escapeHtml(u.status || 'active')}"
                        title="${u.status === 'active' ? 'Suspend' : 'Activate'}">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">${
                    u.status === 'active'
                        ? '<path d="M18.36 6.64a9 9 0 1 1-12.73 0"/>'
                        : '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="M22 4L12 14.01l-3-3"/>'
                    }</svg>
                </button>` : ''}
                ${canDelete ? `
                <button class="action-btn danger" data-action="delete-user" data-name="${escapeHtml(u.name)}" title="Delete">
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
                </button>` : ''}
            </div>
            </td>
        </tr>`;
    }).join('');

    $('#usersTable').innerHTML = `
        <table>
        <thead><tr>
            <th>Name</th><th>Role</th><th>Status</th>
            <th>API Key</th><th>Like Key</th><th>Created</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
        </table>`;
    $$('#usersTable .mini-copy').forEach(b => {
      b.addEventListener('click', (e) => {
        e.stopPropagation();
        copyToClipboard(b.dataset.copy).then((ok) => {
          if (ok) toast('Copied', b.dataset.copy, 'ok', 2000);
          else toast('Copy failed', 'Select manually', 'warn');
        });
      });
    });
    // Bind actions (same as before)
    $$('[data-action="delete-user"]').forEach(b => b.addEventListener('click', async () => {
        const name = b.dataset.name;
        if (!await confirmModal('Delete User', `Delete "${name}"? This cannot be undone.`)) return;
        const r = await api(`/admin/users/${encodeURIComponent(name)}`, { method: 'DELETE' });
        if (r.ok) { toast('User deleted', name, 'ok'); loadUsers(); }
        else toast('Failed', r.data.error || '', 'err');
    }));
    $$('[data-action="toggle-user"]').forEach(b => b.addEventListener('click', async () => {
        const name = b.dataset.name;
        const newStatus = b.dataset.status === 'active' ? 'suspended' : 'active';
        const r = await api(`/admin/users/${encodeURIComponent(name)}/status`, {
        method: 'POST',
        body: JSON.stringify({ status: newStatus }),
        });
        if (r.ok) { toast('Status updated', `${name} → ${newStatus}`, 'ok'); loadUsers(); }
        else toast('Failed', r.data.error || '', 'err');
    }));
  }

  // ============================================================
  // LOAD: API KEYS
  // ============================================================
  async function loadApiKeys() {
    const { ok, data } = await api('/admin/keys/api');
    if (!ok) return toast('Failed', data.error || '', 'err');

    const keys = data.keys || [];
    $('#apiKeysCount').textContent = keys.length;

    if (!keys.length) {
      $('#apiKeysTable').innerHTML = '<div class="empty-state">No API keys yet</div>';
      return;
    }
    
    const rows = keys.map(k => {
    const type = k.type === 'unlimited'
        ? '<span class="mini-badge violet">unlimited</span>'
        : `<span class="mini-badge cyan">${k.credits_per_day}/day</span>`;
    const used = k.type === 'unlimited'
        ? '—'
        : `${k.used_today || 0}/${k.credits_per_day || 0}`;
    const bound = k.assigned_to
        ? `<span class="mini-badge active">${escapeHtml(k.assigned_to)}</span>`
        : '<span class="mini-badge inactive">unbound</span>';

    // 🔥 region badge
    const region = k.region || 'ALL';
    const regionCls = region === 'ALL' ? 'cyan' : 'pink';
    const regionBadge = `<span class="mini-badge ${regionCls}">${escapeHtml(region)}</span>`;

    return `
        <tr>
        <td class="mono-sm txt">${escapeHtml(k.key)}</td>
        <td>${type}</td>
        <td>${regionBadge}</td>
        <td>${used}</td>
        <td>${bound}</td>
        <td>${escapeHtml(fmtDate(k.expires_at))}</td>
        <td>
            <div class="row-actions">
            <button class="action-btn" data-action="copy" data-copy="${escapeHtml(k.key)}" title="Copy">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>
            </button>
            <button class="action-btn danger" data-action="delete-apikey" data-key="${escapeHtml(k.key)}" title="Delete">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
            </button>
            </div>
        </td>
        </tr>`;
    }).join('');

    $('#apiKeysTable').innerHTML = `
    <table>
        <thead><tr>
        <th>Key</th><th>Type</th><th>Region</th><th>Used</th><th>Bound</th><th>Expires</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
    </table>`;

    $$('[data-action="copy"]').forEach(b => b.addEventListener('click', () => {
      copyToClipboard(b.dataset.copy).then((ok) => {
        if (ok) toast('Copied', b.dataset.copy, 'ok', 2000);
        else toast('Copy failed', 'Select manually', 'warn');
      });
    }));
    $$('[data-action="delete-apikey"]').forEach(b => b.addEventListener('click', async () => {
      const k = b.dataset.key;
      if (!await confirmModal('Delete API Key', `Delete ${k}?`)) return;
      const r = await api(`/admin/keys/api/${encodeURIComponent(k)}`, { method: 'DELETE' });
      if (r.ok) { toast('Deleted', k, 'ok'); loadApiKeys(); }
      else toast('Failed', r.data.error || '', 'err');
    }));
  }

  // ============================================================
  // LOAD: LIKE KEYS
  // ============================================================
  async function loadLikeKeys() {
    const { ok, data } = await api('/admin/keys/like');
    if (!ok) return toast('Failed', data.error || '', 'err');

    const keys = data.keys || [];
    $('#likeKeysCount').textContent = keys.length;

    if (!keys.length) {
      $('#likeKeysTable').innerHTML = '<div class="empty-state">No Like keys yet</div>';
      return;
    }

    const rows = keys.map(k => {
      const bound = k.assigned_to ? `<span class="mini-badge active">${escapeHtml(k.assigned_to)}</span>` : '<span class="mini-badge inactive">unbound</span>';
      return `
        <tr>
          <td class="mono-sm txt">${escapeHtml(k.key)}</td>
          <td><span class="mini-badge cyan">${k.per_uid_per_day}/UID/day</span></td>
          <td>${bound}</td>
          <td>${escapeHtml(fmtDate(k.expires_at))}</td>
          <td>
            <div class="row-actions">
              <button class="action-btn" data-action="copy" data-copy="${escapeHtml(k.key)}" title="Copy">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>
              </button>
              <button class="action-btn danger" data-action="delete-likekey" data-key="${escapeHtml(k.key)}" title="Delete">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');

    $('#likeKeysTable').innerHTML = `
      <table>
        <thead><tr>
          <th>Key</th><th>Limit</th><th>Bound</th><th>Expires</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;

    $$('[data-action="copy"]').forEach(b => b.addEventListener('click', () => {
      copyToClipboard(b.dataset.copy).then((ok) => {
        if (ok) toast('Copied', b.dataset.copy, 'ok', 2000);
        else toast('Copy failed', 'Select manually', 'warn');
      });
    }));
    $$('[data-action="delete-likekey"]').forEach(b => b.addEventListener('click', async () => {
      const k = b.dataset.key;
      if (!await confirmModal('Delete Like Key', `Delete ${k}?`)) return;
      const r = await api(`/admin/keys/like/${encodeURIComponent(k)}`, { method: 'DELETE' });
      if (r.ok) { toast('Deleted', k, 'ok'); loadLikeKeys(); }
      else toast('Failed', r.data.error || '', 'err');
    }));
  }

  // ============================================================
  // LOAD: BOOST
  // ============================================================
  async function loadBoost() {
    const { ok, data } = await api('/admin/boost');
    if (!ok) return toast('Failed', data.error || '', 'err');

    const jobs = data.jobs || [];
    $('#boostCount').textContent = jobs.length;

    if (!jobs.length) {
      $('#boostTable').innerHTML = '<div class="empty-state">No boost jobs yet</div>';
      return;
    }

const rows = jobs.map(j => {
      const start = j.start_likes ?? '—';
      const add = j.add_likes || 0;
      const target = j.target_likes ?? '—';
      const current = j.current_likes ?? j.start_likes ?? '—';
      
      // jodi pending — show "..." for progress
      const done = (j.start_likes != null && j.current_likes != null) 
        ? (j.current_likes - j.start_likes) : 0;
      const pct = add > 0 ? Math.min(100, Math.round((done / add) * 100)) : 0;
      
      const statusBadge = j.status === 'active' ? 'active'
                        : j.status === 'completed' ? 'cyan'
                        : j.status === 'pending' ? 'warn'
                        : j.status === 'terminated' ? 'danger'
                        : j.status === 'paused' ? 'warn' : 'inactive';
      return `
        <tr>
          <td class="txt">${escapeHtml(j.uid)}</td>
          <td>${escapeHtml(j.nickname || '—')}</td>
          <td>${escapeHtml(j.region || '—')}</td>
          <td>${start}</td>
          <td style="color:var(--cyan)">+${add}</td>
          <td>${target}</td>
          <td>${j.status === 'pending' ? '<span style="color:var(--faint)">…</span>' : pct + '%'}</td>
          <td><span class="mini-badge ${statusBadge}">${escapeHtml(j.status)}</span></td>
          <td>
            <div class="row-actions">
              <button class="action-btn ${j.status === 'active' ? 'warn' : 'ok'}"
                      data-action="toggle-boost" data-uid="${escapeHtml(j.uid)}" data-status="${escapeHtml(j.status)}" title="Pause/Resume">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">${
                  j.status === 'active'
                    ? '<path d="M6 4h4v16H6zM14 4h4v16h-4z"/>'
                    : '<path d="M5 3l14 9-14 9V3z"/>'
                }</svg>
              </button>
              <button class="action-btn danger" data-action="delete-boost" data-uid="${escapeHtml(j.uid)}" title="Delete">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');


    $('#boostTable').innerHTML = `
      <table>
        <thead>
          <tr>
            <th>UID</th>
            <th>Nickname</th>
            <th>Region</th>
            <th>Start</th>
            <th>Add</th>
            <th>Target</th>
            <th>Progress</th>
            <th>Status</th>
            <th></th>
          </tr>
        </thead>
        <tbody>${rows}</tbody>
      </table>`;

    $$('[data-action="delete-boost"]').forEach(b => b.addEventListener('click', async () => {
      const uid = b.dataset.uid;
      if (!await confirmModal('Delete Boost Job', `Delete job for UID ${uid}?`)) return;
      const r = await api(`/admin/boost/${encodeURIComponent(uid)}`, { method: 'DELETE' });
      if (r.ok) { toast('Deleted', uid, 'ok'); loadBoost(); }
      else toast('Failed', r.data.error || '', 'err');
    }));
    $$('[data-action="toggle-boost"]').forEach(b => b.addEventListener('click', async () => {
      const uid = b.dataset.uid;
      const cur = b.dataset.status;
      const path = cur === 'active' ? 'pause' : 'resume';
      const r = await api(`/admin/boost/${encodeURIComponent(uid)}/${path}`, { method: 'POST' });
      if (r.ok) { toast('Updated', `${uid} → ${path}d`, 'ok'); loadBoost(); }
      else toast('Failed', r.data.error || '', 'err');
    }));
  }

  // ============================================================
  // LOAD: AUTO
  // ============================================================
  async function loadAuto() {
    const { ok, data } = await api('/admin/auto');
    if (!ok) return toast('Failed', data.error || '', 'err');

    const jobs = data.jobs || [];
    $('#autoCount').textContent = jobs.length;

    if (!jobs.length) {
      $('#autoTable').innerHTML = '<div class="empty-state">No auto jobs yet</div>';
      return;
    }

    const rows = jobs.map(j => {
      const statusBadge = j.status === 'active' ? 'active'
                        : j.status === 'completed' ? 'cyan'
                        : j.status === 'pending' ? 'warn'
                        : j.status === 'terminated' ? 'danger'
                        : j.status === 'paused' ? 'warn' : 'inactive';
      const start = j.start_likes ?? '—';
      const perDay = j.per_day || 200;
      const expires = fmtDate(j.expires_at);
      return `
        <tr>
          <td class="txt">${escapeHtml(j.uid)}</td>
          <td>${escapeHtml(j.nickname || '—')}</td>
          <td>${escapeHtml(j.region || '—')}</td>
          <td>${start}</td>
          <td style="color:var(--cyan)">+${perDay}</td>
          <td>${escapeHtml(expires)}</td>
          <td>${j.run_count || 0}</td>
          <td><span class="mini-badge ${statusBadge}">${escapeHtml(j.status)}</span></td>
          <td>
            <div class="row-actions">
              <button class="action-btn ${j.status === 'active' ? 'warn' : 'ok'}"
                      data-action="toggle-auto" data-uid="${escapeHtml(j.uid)}" data-status="${escapeHtml(j.status)}" title="Pause/Resume">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">${
                  j.status === 'active'
                    ? '<path d="M6 4h4v16H6zM14 4h4v16h-4z"/>'
                    : '<path d="M5 3l14 9-14 9V3z"/>'
                }</svg>
              </button>
              <button class="action-btn danger" data-action="delete-auto" data-uid="${escapeHtml(j.uid)}" title="Delete">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round"><path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/></svg>
              </button>
            </div>
          </td>
        </tr>`;
    }).join('');

    $('#autoTable').innerHTML = `
      <table>
        <thead><tr>
          <th>UID</th><th>Nickname</th><th>Region</th>
          <th>Start</th><th>Per Day</th><th>Expires</th>
          <th>Runs</th><th>Status</th><th></th>
        </tr></thead>
        <tbody>${rows}</tbody>
      </table>`;

    $$('[data-action="delete-auto"]').forEach(b => b.addEventListener('click', async () => {
      const uid = b.dataset.uid;
      if (!await confirmModal('Delete Auto Job', `Delete job for UID ${uid}?`)) return;
      const r = await api(`/admin/auto/${encodeURIComponent(uid)}`, { method: 'DELETE' });
      if (r.ok) { toast('Deleted', uid, 'ok'); loadAuto(); }
      else toast('Failed', r.data.error || '', 'err');
    }));
    $$('[data-action="toggle-auto"]').forEach(b => b.addEventListener('click', async () => {
      const uid = b.dataset.uid;
      const cur = b.dataset.status;
      const path = cur === 'active' ? 'pause' : 'resume';
      const r = await api(`/admin/auto/${encodeURIComponent(uid)}/${path}`, { method: 'POST' });
      if (r.ok) { toast('Updated', `${uid} → ${path}d`, 'ok'); loadAuto(); }
      else toast('Failed', r.data.error || '', 'err');
    }));
  }

  // ============================================================
  // LOAD: LOGS
  // ============================================================
  async function loadLogs() {
    const filter = $('#logFilter').value;
    const qs = filter ? `?action=${encodeURIComponent(filter)}&limit=100` : '?limit=100';
    const { ok, data } = await api('/admin/logs' + qs);
    if (!ok) return toast('Failed', data.error || '', 'err');

    const logs = data.logs || [];
    if (!logs.length) {
      $('#logsList').innerHTML = '<div class="empty-state">No activity logs</div>';
      return;
    }

    const items = logs.map(l => {
      let cls = 'other';
      const a = l.action || '';
      if (a === 'like') cls = 'like';
      else if (a === 'login' || a === 'logout') cls = 'login';
      else if (a.startsWith('boost')) cls = 'boost';
      else if (a.startsWith('auto')) cls = 'auto';
      else if (a.startsWith('key')) cls = 'key';

      const body = [
        l.user ? `<span class="log-user">${escapeHtml(l.user)}</span>` : '',
        l.uid ? `· ${escapeHtml(l.uid)}` : '',
        l.added !== undefined && l.added !== null ? `· +${l.added}` : '',
        l.reason ? `· ${escapeHtml(l.reason)}` : '',
        l.error ? `· ${escapeHtml(l.error)}` : '',
      ].filter(Boolean).join(' ');

      return `
        <div class="log-item">
          <span class="log-time">${escapeHtml(fmtDate(l.timestamp))}</span>
          <span class="log-body">${body || '—'}</span>
          <span class="log-action ${cls}">${escapeHtml(a)}</span>
        </div>`;
    }).join('');

    $('#logsList').innerHTML = items;
  }

  // ============================================================
  // LOAD: SETTINGS / BOTS
  // ============================================================
  async function loadBots() {
    const { ok, data } = await api('/admin/bots/settings');
    if (!ok) return toast('Failed', data.error || '', 'err');

    const s = data.settings || {};
    const rows = Object.entries(s).map(([k, v]) => `
      <div class="info-row">
        <span>${escapeHtml(k)}</span>
        <span>${escapeHtml(v || '(empty)')}</span>
      </div>`).join('');

    $('#botSettingsList').innerHTML = rows
      ? `<div class="info-list">${rows}</div>`
      : '<div class="empty-state">No settings</div>';
  }

// ============================================================
// CREATE ADMIN (owner only)
// ============================================================
const adminForm = $('#adminCreateForm');
if (adminForm) {
  adminForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = $('#newAdminName').value.trim();
    const password = $('#newAdminPass').value;
    const key = $('#newAdminKey').value.trim();
    if (!name || !password) return toast('Missing fields', '', 'warn');

    showLoader('Creating admin…');
    const r = await api('/admin/admins/create', {
      method: 'POST',
      body: JSON.stringify({ name, password, key }),
    });
    hideLoader();

    if (r.ok) {
      const msg = r.data.key
        ? `Admin "${name}" created with key assigned`
        : `Admin "${name}" created — give them a key from Keys panel`;
      toast('Admin created', msg, 'ok', 6500);
      adminForm.reset();
      loadUsers();
    } else {
      toast('Failed', r.data.error || '', 'err');
    }
  });
}
  
  $('#apiKeyForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const c = $('#apiCredits').value.trim();
    const d = $('#apiDuration').value.trim();
    const region = $('#apiRegion').value;
    if (!d) return toast('Missing duration', '', 'warn');

    showLoader('Generating API key…');
    const r = await api('/admin/keys/api/generate', {
        method: 'POST',
        body: JSON.stringify({
        credits_per_day: c === '' ? null : Number(c),
        duration_days: Number(d),
        region: region,                     // 🔥 NEW
        }),
    });
    hideLoader();
    if (r.ok) {
      toast('API key generated', `${r.data.key}  ·  region=${r.data.region}`, 'ok', 6500);
      copyToClipboard(r.data.key).then((ok) => {
        if (ok) toast('Key copied', r.data.key, 'info', 2000);
      });
      $('#apiKeyForm').reset();
      $('#apiDuration').value = 30;
      $('#apiRegion').value = 'ALL';
      setTimeout(() => loadApiKeys(), 300);
    } else toast('Failed', r.data.error || '', 'err');
  });

  $('#likeKeyForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const p = $('#likePerUid').value.trim();
    const d = $('#likeDuration').value.trim();

    showLoader('Generating Like key…');
    const r = await api('/admin/keys/like/generate', {
      method: 'POST',
      body: JSON.stringify({
        per_uid_per_day: Number(p),
        duration_days: Number(d),
      }),
    });
    hideLoader();

    if (r.ok) {
      toast('Like key generated', r.data.key, 'ok', 6000);
      copyToClipboard(r.data.key).then((ok) => {
        if (ok) toast('Key copied', r.data.key, 'info', 2000);
      });
      $('#likeKeyForm').reset();
      $('#likePerUid').value = 5;
      $('#likeDuration').value = 30;
      setTimeout(() => loadLikeKeys(), 300);
    } else toast('Failed', r.data.error || '', 'err');
  });

  $('#boostForm').addEventListener('submit', async (e) => {
      e.preventDefault();
      const body = {
        uid: $('#boostUid').value.trim(),
        region: $('#boostRegion').value,
        add_likes: Number($('#boostAddLikes').value),    // 🔥 renamed
        per_day: 200,
      };
      if (!body.uid || !body.add_likes) return toast('Missing fields', '', 'warn');

      showLoader('Creating boost job…');
      const r = await api('/admin/boost/create', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      hideLoader();

      if (r.ok) {
        const d = r.data;
        if (d.status === 'active') {
          toast('Boost Job Active',
                `${d.start_likes} → ${d.target_likes} (+${d.add_likes})`,
                'ok', 6000);
        } else {
          toast('Boost Job Pending',
                'Initializing via scheduler (max 15 min)',
                'warn', 6000);
        }
        $('#boostForm').reset();
        loadBoost();
      } else {
        const d = r.data || {};
        const msg = d.message || d.error || 'Failed';
        toast('Failed', msg, 'err', 6000);
      }
  });

  $('#autoForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    const body = {
      uid: $('#autoUid').value.trim(),
      region: $('#autoRegion').value,
      per_day: 200,
      duration_days: Number($('#autoDuration').value),
    };
    if (!body.uid || !body.duration_days) return toast('Missing fields', '', 'warn');

    showLoader('Creating auto job…');
    const r = await api('/admin/auto/create', {
      method: 'POST',
      body: JSON.stringify(body),
    });
    hideLoader();

    if (r.ok) {
      toast('Auto job created', `UID ${body.uid}`, 'ok');
      $('#autoForm').reset();
      $('#autoDuration').value = 30;
      loadAuto();
    } else toast('Failed', r.data.error || '', 'err');
  });

  // ============================================================
  // REFRESH BUTTONS — Safe binding
  // ============================================================
  function safeBind(selector, handler) {
    const el = document.querySelector(selector);
    if (el) {
      el.addEventListener(handler.type || 'click', handler.fn || handler);
    } else {
      console.warn(`[admin.js] Element not found: ${selector}`);
    }
  }

  safeBind('#refreshBtn',        () => setView(state.view));
  safeBind('#refreshUsers',      loadUsers);
  safeBind('#refreshApiKeys',    loadApiKeys);
  safeBind('#refreshLikeKeys',   loadLikeKeys);
  safeBind('#refreshBoost',      loadBoost);
  safeBind('#refreshAuto',       loadAuto);
  safeBind('#refreshLogs',       loadLogs);
  safeBind('#refreshBots',       loadBots);
  safeBind('#logFilter',         { type: 'change', fn: loadLogs });

  safeBind('#logoutBtn',         async () => {
    if (!await confirmModal('Logout', 'End your session?')) return;
    await api('/auth/logout', { method: 'POST' });
    location.href = '/';
  });

  // ============================================================
  // LOGOUT
  // ============================================================

  
  // ============================================================
  // THEME PICKER
  // ============================================================
  (function initThemePicker() {
    const grid = document.getElementById('themeGrid');
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
        const label = document.getElementById('currentThemeLabel');
        if (label) label.textContent = theme;
        toast('Theme Applied', themes[theme].name, 'ok', 2000);
      });
    });
    const label = document.getElementById('currentThemeLabel');
    if (label) label.textContent = current;
  })();
  
  // ============================================================
  // BOOT
  // ============================================================
  (async () => {
    // Start loading
    showLoader('Loading admin panel…');

    // Load user + min load time in parallel
    const [ok] = await Promise.all([
      loadMe(),
      new Promise(r => Realtime.ensureMinLoad(r)),
    ]);

    hideLoader();
    if (!ok) return;

    setView('dashboard');

    // 🔥 START REALTIME
    Realtime.start();

    // 🔥 Auto-clear inputs when switching tabs
    Realtime.attachTabClear('.nav-item, [data-goto]');

    // 🔥 Live update: when user data changes, update sidebar
    Realtime.on('user:update', (user) => {
      if (!user) return;
      state.user = user;
      $('#userName').textContent = user.name;
      $('#userRole').textContent = (user.role || 'user').toUpperCase();
      $('#userAvatar').textContent = (user.name || '?').charAt(0).toUpperCase();
    });

    // 🔥 Live poll: dashboard stats every 5s when on dashboard
    Realtime.on('view:change', ({ to }) => {
      if (to === 'view-dashboard' || to === 'view-logs') {
        // Already handled by setView, but ensure poll continues
      }
    });

    // 🔥 Validation examples — attach to key forms
    const uidInput = document.querySelector('#boostUid');
    if (uidInput) Realtime.attachValidation(uidInput, Realtime.validators.uid);

    const autoUidInput = document.querySelector('#autoUid');
    if (autoUidInput) Realtime.attachValidation(autoUidInput, Realtime.validators.uid);

    const likeUidInput = document.querySelector('#ownerLikeUid');
    if (likeUidInput) Realtime.attachValidation(likeUidInput, Realtime.validators.uid);

    const newAdminNameInput = document.querySelector('#newAdminName');
    if (newAdminNameInput) Realtime.attachValidation(newAdminNameInput, Realtime.validators.required('Username'));

    const newAdminPassInput = document.querySelector('#newAdminPass');
    if (newAdminPassInput) Realtime.attachValidation(newAdminPassInput, Realtime.validators.password);

    const boostTargetInput = document.querySelector('#boostAddLikes');
    if (boostTargetInput) Realtime.attachValidation(boostTargetInput, Realtime.validators.number('Amount'));

    const autoDurationInput = document.querySelector('#autoDuration');
    if (autoDurationInput) Realtime.attachValidation(autoDurationInput, Realtime.validators.number('Duration'));

    console.log('%c🔥 FF LIKE API — Admin Terminal', 'color:#22d3ee;font-size:14px;font-weight:800');
    console.log('%c⚡ Real-time sync active', 'color:#22c55e;font-size:11px;font-weight:700');
  })();

})();