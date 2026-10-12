/* ============================================================
   FF LIKE API — Theme System (10 animated themes)
   ============================================================ */
(function () {
  'use strict';

  const STORAGE_KEY = 'fflike_theme';
  const DEFAULT_THEME = 'matrix';

  const canvas = document.getElementById('matrix');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, cols, drops = [];
  let rafId = null;
  let currentCleanup = null;

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
    cols = Math.floor(W / 14);
    drops = Array.from({ length: cols }, () => Math.random() * -50);
  }
  window.addEventListener('resize', resize);
  resize();

  function resetCanvas() {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = '#05070d';
    ctx.fillRect(0, 0, W, H);
    cols = Math.floor(W / 14);
    drops = Array.from({ length: cols }, () => Math.random() * -50);
  }

  // ============================================================
  // 1. MATRIX RAIN
  // ============================================================
  function themeMatrix() {
    const CHARS = '01アイウエオカキクケコサシスセソFFLIKEAPI<>/\\[]{}#$%&*+=-·□';
    const FONT = 14;
    const COLORS = ['#22d3ee', '#8b5cf6', '#ec4899'];
    let running = true;

    function step() {
      if (!running) return;
      ctx.fillStyle = 'rgba(5,7,13,0.09)';
      ctx.fillRect(0, 0, W, H);
      ctx.font = `${FONT}px 'JetBrains Mono', monospace`;
      for (let i = 0; i < drops.length; i++) {
        const ch = CHARS[Math.floor(Math.random() * CHARS.length)];
        const y = drops[i] * FONT;
        const c = COLORS[i % COLORS.length];
        ctx.fillStyle = c;
        ctx.shadowColor = c;
        ctx.shadowBlur = 6;
        ctx.fillText(ch, i * FONT, y);
        ctx.shadowBlur = 0;
        if (y > H && Math.random() > 0.975) drops[i] = 0;
        drops[i]++;
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 2. FLAME
  // ============================================================
  function themeFlame() {
    const particles = [];
    let running = true;

    function spawn() {
      particles.push({
        x: Math.random() * W,
        y: H + 20,
        r: 8 + Math.random() * 22,
        vy: -1 - Math.random() * 2.2,
        vx: (Math.random() - 0.5) * 0.6,
        life: 1,
        hue: 8 + Math.random() * 45,
      });
    }

    function step() {
      if (!running) return;
      ctx.fillStyle = 'rgba(5,7,13,0.15)';
      ctx.fillRect(0, 0, W, H);
      if (Math.random() < 0.7) spawn();

      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx; p.y += p.vy;
        p.life -= 0.008;
        p.r *= 0.994;
        if (p.life <= 0 || p.y < -50) { particles.splice(i, 1); continue; }

        const g = ctx.createRadialGradient(p.x, p.y, 0, p.x, p.y, p.r);
        g.addColorStop(0, `hsla(${p.hue}, 100%, 60%, ${p.life * 0.7})`);
        g.addColorStop(1, `hsla(${p.hue}, 100%, 30%, 0)`);
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 3. WATER — sine waves
  // ============================================================
  function themeWater() {
    let t = 0;
    let running = true;

    function step() {
      if (!running) return;
      ctx.fillStyle = 'rgba(5,7,13,0.08)';
      ctx.fillRect(0, 0, W, H);

      for (let layer = 0; layer < 5; layer++) {
        const y0 = H * 0.5 + layer * 30;
        const amp = 30 + layer * 12;
        const freq = 0.008 + layer * 0.003;
        const speed = 1 + layer * 0.3;

        ctx.beginPath();
        ctx.moveTo(0, H);
        for (let x = 0; x <= W; x += 8) {
          const y = y0 + Math.sin(x * freq + t * speed) * amp
                       + Math.sin(x * freq * 2 + t * speed * 1.5) * amp * 0.4;
          ctx.lineTo(x, y);
        }
        ctx.lineTo(W, H);
        ctx.closePath();
        const hue = 190 + layer * 8;
        ctx.fillStyle = `hsla(${hue}, 80%, 50%, 0.10)`;
        ctx.strokeStyle = `hsla(${hue}, 80%, 60%, 0.35)`;
        ctx.lineWidth = 1.5;
        ctx.fill();
        ctx.stroke();
      }
      t += 0.02;
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 4. MIST — drifting clouds
  // ============================================================
  function themeMist() {
    const blobs = Array.from({ length: 20 }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      r: 80 + Math.random() * 200,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      alpha: 0.03 + Math.random() * 0.05,
    }));
    let running = true;

    function step() {
      if (!running) return;
      ctx.fillStyle = '#05070d';
      ctx.fillRect(0, 0, W, H);

      for (const b of blobs) {
        b.x += b.vx; b.y += b.vy;
        if (b.x < -b.r) b.x = W + b.r;
        if (b.x > W + b.r) b.x = -b.r;
        if (b.y < -b.r) b.y = H + b.r;
        if (b.y > H + b.r) b.y = -b.r;

        const g = ctx.createRadialGradient(b.x, b.y, 0, b.x, b.y, b.r);
        g.addColorStop(0, `rgba(180,200,255,${b.alpha})`);
        g.addColorStop(1, 'rgba(180,200,255,0)');
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
        ctx.fill();
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 5. WIND — horizontal streaks
  // ============================================================
  function themeWind() {
    const streaks = Array.from({ length: 60 }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      len: 40 + Math.random() * 120,
      vx: 3 + Math.random() * 5,
      alpha: 0.05 + Math.random() * 0.15,
      width: 0.5 + Math.random() * 1.5,
    }));
    let running = true;

    function step() {
      if (!running) return;
      ctx.fillStyle = 'rgba(5,7,13,0.15)';
      ctx.fillRect(0, 0, W, H);

      for (const s of streaks) {
        s.x += s.vx;
        if (s.x > W + s.len) { s.x = -s.len; s.y = Math.random() * H; }
        ctx.strokeStyle = `rgba(180,220,255,${s.alpha})`;
        ctx.lineWidth = s.width;
        ctx.beginPath();
        ctx.moveTo(s.x - s.len, s.y);
        ctx.lineTo(s.x, s.y);
        ctx.stroke();
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 6. STONE — falling rocks
  // ============================================================
  function themeStone() {
    const rocks = Array.from({ length: 30 }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      r: 2 + Math.random() * 6,
      vy: 0.5 + Math.random() * 2,
      vx: (Math.random() - 0.5) * 0.4,
      rot: Math.random() * Math.PI * 2,
      vr: (Math.random() - 0.5) * 0.02,
      alpha: 0.3 + Math.random() * 0.4,
      sides: 5 + Math.floor(Math.random() * 3),
      pts: [],
    }));
    // Precompute polygon offsets
    for (const r of rocks) {
      for (let i = 0; i < r.sides; i++) {
        r.pts.push({ a: (i / r.sides) * Math.PI * 2, k: 0.75 + Math.random() * 0.35 });
      }
    }
    let running = true;

    function step() {
      if (!running) return;
      ctx.fillStyle = '#05070d';
      ctx.fillRect(0, 0, W, H);

      for (const r of rocks) {
        r.y += r.vy; r.x += r.vx; r.rot += r.vr;
        if (r.y > H + 20) { r.y = -20; r.x = Math.random() * W; }

        ctx.save();
        ctx.translate(r.x, r.y);
        ctx.rotate(r.rot);
        ctx.fillStyle = `rgba(140,150,170,${r.alpha})`;
        ctx.beginPath();
        for (const p of r.pts) {
          ctx.lineTo(Math.cos(p.a) * r.r * p.k, Math.sin(p.a) * r.r * p.k);
        }
        ctx.closePath();
        ctx.fill();
        ctx.restore();
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 7. INSECT — crawling bugs
  // ============================================================
  function themeInsect() {
    const bugs = Array.from({ length: 25 }, () => ({
      x: Math.random() * W, y: Math.random() * H,
      angle: Math.random() * Math.PI * 2,
      speed: 0.5 + Math.random() * 1.5,
      size: 2 + Math.random() * 2,
      alpha: 0.4 + Math.random() * 0.4,
    }));
    let running = true;

    function step() {
      if (!running) return;
      ctx.fillStyle = 'rgba(5,7,13,0.12)';
      ctx.fillRect(0, 0, W, H);

      for (const b of bugs) {
        b.angle += (Math.random() - 0.5) * 0.3;
        b.x += Math.cos(b.angle) * b.speed;
        b.y += Math.sin(b.angle) * b.speed;
        if (b.x < 0 || b.x > W) { b.angle = Math.PI - b.angle; b.x = Math.max(0, Math.min(W, b.x)); }
        if (b.y < 0 || b.y > H) { b.angle = -b.angle; b.y = Math.max(0, Math.min(H, b.y)); }

        ctx.strokeStyle = `rgba(150,255,120,${b.alpha * 0.5})`;
        ctx.lineWidth = 0.6;
        for (let i = -1; i <= 1; i += 2) {
          ctx.beginPath();
          ctx.moveTo(b.x, b.y);
          ctx.lineTo(b.x + Math.cos(b.angle + i * 0.7) * 6,
                     b.y + Math.sin(b.angle + i * 0.7) * 6);
          ctx.stroke();
        }
        ctx.fillStyle = `rgba(150,255,120,${b.alpha})`;
        ctx.beginPath();
        ctx.arc(b.x, b.y, b.size, 0, Math.PI * 2);
        ctx.fill();
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 8. SOUND — audio waveform bars
  // ============================================================
  function themeSound() {
    const bars = 60;
    const heights = new Array(bars).fill(0);
    let running = true;
    let t = 0;

    function step() {
      if (!running) return;
      ctx.fillStyle = 'rgba(5,7,13,0.15)';
      ctx.fillRect(0, 0, W, H);

      t += 0.05;
      const barW = W / bars;

      for (let i = 0; i < bars; i++) {
        const target = Math.abs(Math.sin(t + i * 0.15) * Math.cos(t * 0.5 + i * 0.05)) * 0.6
                     + Math.random() * 0.2;
        heights[i] += (target - heights[i]) * 0.15;

        const h = heights[i] * H * 0.75;
        const x = i * barW + barW * 0.15;
        const grad = ctx.createLinearGradient(0, H, 0, H - h);
        grad.addColorStop(0, 'rgba(139,92,246,0.45)');
        grad.addColorStop(1, 'rgba(34,211,238,0.65)');
        ctx.fillStyle = grad;
        ctx.fillRect(x, H - h, barW * 0.7, h);
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 9. LOVE — floating hearts
  // ============================================================
  function themeLove() {
    const hearts = [];
    let running = true;

    function spawnHeart() {
      hearts.push({
        x: Math.random() * W, y: H + 20,
        size: 6 + Math.random() * 12,
        vy: -0.5 - Math.random() * 1.5,
        vx: (Math.random() - 0.5) * 0.5,
        sway: Math.random() * Math.PI * 2,
        alpha: 0.4 + Math.random() * 0.4,
      });
    }

    function drawHeart(x, y, size, alpha) {
      ctx.save();
      ctx.translate(x, y);
      ctx.scale(size / 10, size / 10);
      ctx.fillStyle = `rgba(255,90,150,${alpha})`;
      ctx.shadowColor = 'rgba(255,90,150,0.9)';
      ctx.shadowBlur = 8;
      ctx.beginPath();
      ctx.moveTo(0, 3);
      ctx.bezierCurveTo(-6, -3, -10, 2, 0, 9);
      ctx.bezierCurveTo(10, 2, 6, -3, 0, 3);
      ctx.closePath();
      ctx.fill();
      ctx.restore();
    }

    function step() {
      if (!running) return;
      ctx.fillStyle = 'rgba(5,7,13,0.12)';
      ctx.fillRect(0, 0, W, H);

      if (Math.random() < 0.2) spawnHeart();

      for (let i = hearts.length - 1; i >= 0; i--) {
        const h = hearts[i];
        h.sway += 0.03;
        h.x += h.vx + Math.sin(h.sway) * 0.4;
        h.y += h.vy;
        h.alpha *= 0.998;
        if (h.y < -30 || h.alpha < 0.05) { hearts.splice(i, 1); continue; }
        drawHeart(h.x, h.y, h.size, h.alpha);
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // 10. SERPENT — snake curves
  // ============================================================
  function themeSerpent() {
    const snakes = [];
    for (let i = 0; i < 4; i++) {
      snakes.push({
        x: Math.random() * W, y: Math.random() * H,
        angle: Math.random() * Math.PI * 2,
        length: 60, trail: [],
        speed: 1.2 + Math.random() * 0.8,
        hue: 100 + Math.random() * 60,
        wiggle: 0,
      });
    }
    let running = true;

    function step() {
      if (!running) return;
      ctx.fillStyle = 'rgba(5,7,13,0.10)';
      ctx.fillRect(0, 0, W, H);

      for (const s of snakes) {
        s.wiggle += 0.15;
        s.angle += Math.sin(s.wiggle) * 0.08;
        s.x += Math.cos(s.angle) * s.speed;
        s.y += Math.sin(s.angle) * s.speed;
        if (s.x < -50) s.x = W + 50;
        if (s.x > W + 50) s.x = -50;
        if (s.y < -50) s.y = H + 50;
        if (s.y > H + 50) s.y = -50;

        s.trail.push({ x: s.x, y: s.y });
        if (s.trail.length > s.length) s.trail.shift();

        for (let i = 0; i < s.trail.length; i++) {
          const p = s.trail[i];
          const a = (i / s.trail.length) * 0.5;
          ctx.fillStyle = `hsla(${s.hue}, 80%, 60%, ${a})`;
          ctx.beginPath();
          ctx.arc(p.x, p.y, 3 + (i / s.trail.length) * 3, 0, Math.PI * 2);
          ctx.fill();
        }
      }
      rafId = requestAnimationFrame(step);
    }
    step();
    return () => { running = false; };
  }

  // ============================================================
  // THEME REGISTRY
  // ============================================================
  const THEMES = {
    matrix:  { name: 'Matrix Rain',  icon: '🟢', fn: themeMatrix },
    flame:   { name: 'Flame',        icon: '🔥', fn: themeFlame },
    water:   { name: 'Water',        icon: '💧', fn: themeWater },
    mist:    { name: 'Mist',         icon: '🌫️', fn: themeMist },
    wind:    { name: 'Wind',         icon: '💨', fn: themeWind },
    stone:   { name: 'Stone',        icon: '🪨', fn: themeStone },
    insect:  { name: 'Insect',       icon: '🦗', fn: themeInsect },
    sound:   { name: 'Sound',        icon: '🎵', fn: themeSound },
    love:    { name: 'Love',         icon: '💖', fn: themeLove },
    serpent: { name: 'Serpent',      icon: '🐍', fn: themeSerpent },
  };

  // ============================================================
  // MANAGER
  // ============================================================
  function applyTheme(name) {
    if (!THEMES[name]) name = DEFAULT_THEME;
    if (currentCleanup) { try { currentCleanup(); } catch {} }
    if (rafId) cancelAnimationFrame(rafId);
    resetCanvas();
    currentCleanup = THEMES[name].fn();
    localStorage.setItem(STORAGE_KEY, name);
    window.__currentTheme = name;

    // Highlight active theme card
    document.querySelectorAll('.theme-card').forEach(el => {
      el.classList.toggle('active', el.dataset.theme === name);
    });
  }

  window.FFThemes = {
    list: THEMES,
    apply: applyTheme,
    get current() { return window.__currentTheme || DEFAULT_THEME; },
    init() {
      const saved = localStorage.getItem(STORAGE_KEY) || DEFAULT_THEME;
      applyTheme(saved);
    },
  };

  // Auto-init
  window.FFThemes.init();
})();