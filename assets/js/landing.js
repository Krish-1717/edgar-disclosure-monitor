/* landing.js - scroll-pinned cinematic hero + section reveals. Pure ASCII. */
(function () {
  'use strict';

  var root = document.documentElement;
  root.classList.add('has-js');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');

  var story = document.getElementById('story');
  var canvas = document.getElementById('story-canvas');
  var ctx = canvas.getContext('2d');
  var scenes = Array.prototype.slice.call(document.querySelectorAll('.scene'));
  var dots = Array.prototype.slice.call(document.querySelectorAll('.story-progress i'));
  var layerMid = document.querySelector('.layer-mid');
  var layerBg = document.querySelector('.layer-bg');
  var glowA = document.querySelector('.glow-a');
  var glowB = document.querySelector('.glow-b');
  var glowC = document.querySelector('.glow-c');
  var fragDiff = document.querySelector('.frag-diff');
  var fragScore = document.querySelector('.frag-score');
  var fragAgents = document.querySelector('.frag-agents');
  var hint = document.querySelector('.scroll-hint');

  /* ---------------- helpers ---------------- */
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function smooth(e0, e1, x) { var t = clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function win(p, a, b, c, d) { return smooth(a, b, p) * (1 - smooth(c, d, p)); }
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }

  /* ---------------- particle field ---------------- */
  var COLORS = ['165,173,255', '94,234,212', '227,192,138', '196,161,255', '255,154,174', '125,211,252'];
  var W = 0, H = 0, DPR = 1, parts = [], links = [], bridges = [], K = 6, sprite;
  var mobile = false;

  function makeSprite() {
    sprite = document.createElement('canvas');
    sprite.width = sprite.height = 64;
    var g = sprite.getContext('2d');
    var grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grd.addColorStop(0, 'rgba(255,255,255,0.9)');
    grd.addColorStop(0.25, 'rgba(255,255,255,0.35)');
    grd.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grd;
    g.fillRect(0, 0, 64, 64);
  }

  function build() {
    var r = rng(1717);
    mobile = W < 720;
    var N = mobile ? 130 : 240;
    parts = [];
    var cx = mobile ? W * 0.5 : W * 0.66;
    var cy = mobile ? H * 0.58 : H * 0.5;
    var ring = Math.min(W, H) * (mobile ? 0.30 : 0.28);
    var centers = [];
    for (var k = 0; k < K; k++) {
      var a = k / K * Math.PI * 2 - Math.PI / 2;
      centers.push({ x: cx + Math.cos(a) * ring * (k % 2 ? 1 : 0.82), y: cy + Math.sin(a) * ring * 0.86 });
    }
    for (var i = 0; i < N; i++) {
      var c = i % K;
      var hub = i < K;
      var ang = r() * Math.PI * 2;
      var rad = hub ? 0 : Math.pow(r(), 0.6) * (mobile ? 46 : 70);
      var hexA = Math.round(ang / (Math.PI / 3)) * (Math.PI / 3);
      var hexR = hub ? 0 : (Math.round(rad / 18) + 1) * (mobile ? 10 : 15);
      parts.push({
        c: c, hub: hub,
        ax: r() * W, ay: r() * H,                              // A: scattered dust
        lane: r(), u: r(), spd: 0.4 + r() * 0.9,               // B: streaming lanes
        cx: centers[c].x + Math.cos(ang) * rad, cy: centers[c].y + Math.sin(ang) * rad,          // C: clusters
        dx: centers[c].x + Math.cos(hexA + (i % 3) * 0.35) * hexR, dy: centers[c].y + Math.sin(hexA + (i % 3) * 0.35) * hexR, // D: hive
        size: hub ? 3.6 : 0.9 + r() * 1.5,
        ph: r() * Math.PI * 2,
        x: 0, y: 0
      });
    }
    links = [];
    for (var j = K; j < N; j++) {
      links.push([j, parts[j].c]);                        // to hub
      if (j + K < N && r() < 0.55) links.push([j, j + K]); // neighbor
    }
    bridges = [];
    for (var h = 0; h < K; h++) {
      bridges.push([h, (h + 1) % K]);
      if (h < K / 2) bridges.push([h, h + K / 2]);
    }
  }

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 1.5);
    W = canvas.clientWidth || window.innerWidth;
    H = canvas.clientHeight || window.innerHeight;
    canvas.width = Math.round(W * DPR);
    canvas.height = Math.round(H * DPR);
    build();
  }

  function draw(p, time) {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    var mAB = smooth(0.14, 0.36, p);
    var mBC = smooth(0.40, 0.60, p);
    var mCD = smooth(0.64, 0.84, p);
    var linkAmt = mBC * 0.35 + mCD * 0.65;
    var zoom = 1 + mCD * 0.08 + p * 0.04;
    var t = time * 0.001;
    var zx = mobile ? W * 0.5 : W * 0.66, zy = H * 0.5;

    ctx.save();
    ctx.translate(zx, zy); ctx.scale(zoom, zoom); ctx.translate(-zx, -zy);

    for (var i = 0; i < parts.length; i++) {
      var q = parts[i];
      var driftX = Math.sin(t * 0.3 + q.ph) * 6, driftY = Math.cos(t * 0.25 + q.ph) * 6;
      var ax = q.ax + driftX, ay = q.ay + driftY;
      var u = (q.u + t * 0.02 * q.spd) % 1;
      var bx = lerp(-0.05 * W, W * (mobile ? 0.5 : 0.66), u);
      var laneY = H * (0.18 + q.lane * 0.64);
      var by = lerp(laneY, H * 0.5, Math.pow(u, 2.2) * 0.85) + Math.sin(u * 9 + q.ph) * 8;
      var x = lerp(ax, bx, mAB), y = lerp(ay, by, mAB);
      x = lerp(x, q.cx + driftX * 0.5, mBC); y = lerp(y, q.cy + driftY * 0.5, mBC);
      x = lerp(x, q.dx + driftX * 0.2, mCD); y = lerp(y, q.dy + driftY * 0.2, mCD);
      q.x = x; q.y = y;
    }

    if (linkAmt > 0.01) {
      ctx.lineWidth = 0.6;
      for (var l = 0; l < links.length; l++) {
        var a = parts[links[l][0]], b = parts[links[l][1]];
        ctx.strokeStyle = 'rgba(' + COLORS[a.c] + ',' + (0.16 * linkAmt).toFixed(3) + ')';
        ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
      }
    }
    if (mCD > 0.01) {
      ctx.lineWidth = 1;
      for (var bI = 0; bI < bridges.length; bI++) {
        var h1 = parts[bridges[bI][0]], h2 = parts[bridges[bI][1]];
        var pulse = 0.5 + 0.5 * Math.sin(t * 1.2 + bI);
        ctx.strokeStyle = 'rgba(227,192,138,' + (0.10 + 0.18 * pulse) * mCD + ')';
        ctx.setLineDash([3, 5]);
        ctx.beginPath(); ctx.moveTo(h1.x, h1.y); ctx.lineTo(h2.x, h2.y); ctx.stroke();
        ctx.setLineDash([]);
        var f = (t * 0.25 + bI * 0.17) % 1;
        var px = lerp(h1.x, h2.x, f), py = lerp(h1.y, h2.y, f);
        ctx.globalAlpha = mCD * 0.9 * Math.sin(f * Math.PI);
        ctx.drawImage(sprite, px - 10, py - 10, 20, 20);
        ctx.globalAlpha = 1;
      }
    }

    ctx.globalCompositeOperation = 'lighter';
    for (var n = 0; n < parts.length; n++) {
      var s = parts[n];
      var tw = 0.55 + 0.45 * Math.sin(t * 1.5 + s.ph);
      var col = COLORS[s.c];
      var alpha = (0.35 + 0.45 * tw) * (0.55 + 0.45 * (mBC + mCD) / 2 + 0.2);
      ctx.fillStyle = 'rgba(' + col + ',' + Math.min(alpha, 1).toFixed(3) + ')';
      var sz = s.size * (1 + mCD * (s.hub ? 0.8 : 0.3));
      ctx.beginPath(); ctx.arc(s.x, s.y, sz, 0, Math.PI * 2); ctx.fill();
      if (s.hub && mBC > 0.05) {
        ctx.globalAlpha = 0.5 * (mBC * 0.5 + mCD * 0.5);
        var gs = 44 + mCD * 30;
        ctx.drawImage(sprite, s.x - gs / 2, s.y - gs / 2, gs, gs);
        ctx.globalAlpha = 1;
      }
    }
    ctx.globalCompositeOperation = 'source-over';
    ctx.restore();
  }

  /* ---------------- DOM layers ---------------- */
  var lastScene = -1;
  function layout(p) {
    var segs = scenes.length;
    var active = clamp(Math.floor(p * segs), 0, segs - 1);
    for (var i = 0; i < segs; i++) {
      var c = (i + 0.5) / segs;
      var d = (p - c) * segs;               // -1..1 around this scene
      if (i === 0 && d < 0) d = 0;
      if (i === segs - 1 && d > 0) d = 0;
      var o = 1 - smooth(0.28, 0.5, Math.abs(d));
      var el = scenes[i];
      el.style.opacity = o.toFixed(3);
      el.style.transform = 'translate3d(0,calc(-50% + ' + (-d * 60).toFixed(1) + 'px),0) scale(' + (1 - Math.abs(d) * 0.03).toFixed(4) + ')';
    }
    if (active !== lastScene) {
      scenes.forEach(function (s, k) { s.classList.toggle('is-active', k === active); });
      dots.forEach(function (dd, k) { dd.classList.toggle('on', k === active); });
      lastScene = active;
    }
    if (layerMid) layerMid.style.transform = 'translate3d(0,' + ((0.5 - p) * 140).toFixed(1) + 'px,0)';
    if (layerBg) layerBg.style.transform = 'translate3d(0,' + ((0.5 - p) * 40).toFixed(1) + 'px,0)';
    glowA.style.transform = 'translate3d(' + (-p * 12).toFixed(2) + 'vw,' + (p * 8).toFixed(2) + 'vh,0) scale(' + (1 + p * 0.45).toFixed(3) + ')';
    glowA.style.opacity = (1 - p * 0.35).toFixed(3);
    glowB.style.opacity = win(p, 0.25, 0.5, 0.8, 1.01).toFixed(3);
    glowB.style.transform = 'scale(' + (0.8 + p * 0.4).toFixed(3) + ')';
    glowC.style.opacity = smooth(0.6, 0.95, p).toFixed(3);
    glowC.style.transform = 'scale(' + (0.9 + p * 0.3).toFixed(3) + ')';
    if (fragDiff) {
      fragDiff.style.opacity = win(p, 0.30, 0.42, 0.66, 0.76).toFixed(3);
      fragDiff.style.transform = 'translate3d(0,' + ((0.5 - p) * 60).toFixed(1) + 'px,0)';
      fragScore.style.opacity = win(p, 0.50, 0.60, 0.74, 0.84).toFixed(3);
      fragScore.style.transform = 'translate3d(0,' + ((0.6 - p) * 120).toFixed(1) + 'px,0)';
      fragAgents.style.opacity = win(p, 0.52, 0.64, 0.92, 1.01).toFixed(3);
      fragAgents.style.transform = 'translate3d(0,' + ((0.7 - p) * 90).toFixed(1) + 'px,0)';
    }
    if (hint) hint.style.opacity = (1 - smooth(0.0, 0.06, p)).toFixed(3);
  }

  /* ---------------- loop ---------------- */
  var target = 0, current = 0, running = false, visible = true, rafId = 0;
  function readScroll() {
    var rect = story.getBoundingClientRect();
    var total = story.offsetHeight - window.innerHeight;
    target = total > 0 ? clamp(-rect.top / total, 0, 1) : 0;
  }
  function frame(time) {
    rafId = 0;
    current += (target - current) * 0.075;
    if (Math.abs(target - current) < 0.0004) current = target;
    layout(current);
    draw(current, time);
    if (visible) rafId = requestAnimationFrame(frame); else running = false;
  }
  function start() { if (!running) { running = true; rafId = requestAnimationFrame(frame); } }

  function initLive() {
    story.classList.add('live');
    makeSprite();
    resize();
    readScroll();
    current = target;
    window.addEventListener('scroll', readScroll, { passive: true });
    var rT;
    window.addEventListener('resize', function () { clearTimeout(rT); rT = setTimeout(function () { resize(); readScroll(); }, 120); });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) start();
      }).observe(story);
    }
    start();
  }

  function initStatic() {
    story.classList.remove('live');
    makeSprite();
    resize();
    draw(1, 0);
    scenes.forEach(function (s) { s.style.opacity = ''; s.style.transform = ''; s.removeAttribute('aria-hidden'); });
    window.addEventListener('resize', function () { resize(); draw(1, 0); });
  }

  if (reduce.matches) initStatic(); else initLive();

  /* ---------------- section reveals ---------------- */
  var reveals = document.querySelectorAll('.reveal');
  if (reduce.matches || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(reveals, function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -10% 0px', threshold: 0.12 });
    Array.prototype.forEach.call(reveals, function (el) { io.observe(el); });
  }
})();
