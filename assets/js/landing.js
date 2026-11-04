/*
 * landing.js - deep-space scrollytelling hero (galaxy + interactive Earth + filing arcs + hive),
 * ORACLE crawler section, coverage explorer and reveals. Pure ASCII (see CLAUDE.md).
 * Land mask: Natural Earth 110m land (public domain), rasterized to 240x120, base64 bitmask.
 */
(function () {
  'use strict';

  var root = document.documentElement;
  root.classList.add('has-js');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var F = window.EDM_FILINGS;

  /* ---------------- helpers ---------------- */
  function $(id) { return document.getElementById(id); }
  function clamp(v, a, b) { return v < a ? a : v > b ? b : v; }
  function smooth(e0, e1, x) { var t = clamp((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t); }
  function lerp(a, b, t) { return a + (b - a) * t; }
  function win(p, a, b, c, d) { return smooth(a, b, p) * (1 - smooth(c, d, p)); }
  function rng(seed) { return function () { seed |= 0; seed = seed + 0x6D2B79F5 | 0; var t = Math.imul(seed ^ seed >>> 15, 1 | seed); t = t + Math.imul(t ^ t >>> 7, 61 | t) ^ t; return ((t ^ t >>> 14) >>> 0) / 4294967296; }; }
  function esc(s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  var DEG = Math.PI / 180;

  /* =====================================================================
   * GALAXY (drawn once; spun by a CSS transform animation)
   * ===================================================================== */
  function drawGalaxy() {
    var c = $('galaxy'); if (!c) return;
    var g = c.getContext('2d'), S = c.width, cx = S / 2, cy = S / 2, r = rng(42);
    g.clearRect(0, 0, S, S);
    var core = g.createRadialGradient(cx, cy, 0, cx, cy, S * 0.22);
    core.addColorStop(0, 'rgba(255,236,210,0.85)');
    core.addColorStop(0.18, 'rgba(250,210,180,0.35)');
    core.addColorStop(0.5, 'rgba(160,140,255,0.12)');
    core.addColorStop(1, 'rgba(120,120,255,0)');
    g.fillStyle = core; g.fillRect(0, 0, S, S);
    g.globalCompositeOperation = 'lighter';
    var arms = 2, N = 14000;
    for (var i = 0; i < N; i++) {
      var arm = i % arms, t = Math.pow(r(), 0.7);
      var rad = 30 + t * S * 0.46;
      var ang = arm * Math.PI + Math.log(rad / 30) * 2.25 + (r() - 0.5) * (0.55 - t * 0.25);
      var spread = (r() - 0.5) * (18 + t * 70);
      var x = cx + Math.cos(ang) * rad + Math.cos(ang + Math.PI / 2) * spread;
      var y = cy + Math.sin(ang) * rad + Math.sin(ang + Math.PI / 2) * spread;
      var hue = t < 0.25 ? '255,225,200' : (r() < 0.12 ? '249,168,212' : (r() < 0.5 ? '168,180,255' : '196,170,255'));
      var a = (0.15 + r() * 0.55) * (1 - t * 0.55);
      var sz = r() < 0.03 ? 1.8 : 0.5 + r() * 0.9;
      g.fillStyle = 'rgba(' + hue + ',' + a.toFixed(3) + ')';
      g.fillRect(x, y, sz, sz);
    }
    // soft nebula knots along the arms
    for (var k = 0; k < 70; k++) {
      var t2 = 0.15 + r() * 0.8, rad2 = 30 + t2 * S * 0.46, arm2 = k % 2;
      var ang2 = arm2 * Math.PI + Math.log(rad2 / 30) * 2.25;
      var x2 = cx + Math.cos(ang2) * rad2, y2 = cy + Math.sin(ang2) * rad2, s2 = 20 + r() * 60;
      var neb = g.createRadialGradient(x2, y2, 0, x2, y2, s2);
      var col = r() < 0.4 ? '249,168,212' : (r() < 0.5 ? '103,232,249' : '183,148,255');
      neb.addColorStop(0, 'rgba(' + col + ',0.10)'); neb.addColorStop(1, 'rgba(' + col + ',0)');
      g.fillStyle = neb; g.fillRect(x2 - s2, y2 - s2, s2 * 2, s2 * 2);
    }
    g.globalCompositeOperation = 'source-over';
  }

  /* =====================================================================
   * STARFIELDS (two depths, drawn on resize, parallax via transform)
   * ===================================================================== */
  function drawStars(id, count, maxSize, seed) {
    var c = $(id); if (!c) return;
    var dpr = Math.min(window.devicePixelRatio || 1, 1.5);
    var w = c.clientWidth || innerWidth, h = c.clientHeight || innerHeight;
    c.width = Math.round(w * dpr * 1.1); c.height = Math.round(h * dpr * 1.1);
    var g = c.getContext('2d'), r = rng(seed);
    g.setTransform(dpr, 0, 0, dpr, 0, 0);
    for (var i = 0; i < count; i++) {
      var x = r() * w * 1.1, y = r() * h * 1.1, s = r() * maxSize + 0.3;
      var tint = r() < 0.15 ? '255,228,196' : r() < 0.3 ? '190,200,255' : '255,255,255';
      g.fillStyle = 'rgba(' + tint + ',' + (0.25 + r() * 0.7).toFixed(2) + ')';
      g.beginPath(); g.arc(x, y, s, 0, Math.PI * 2); g.fill();
      if (s > maxSize * 0.85) { g.fillStyle = 'rgba(' + tint + ',0.08)'; g.beginPath(); g.arc(x, y, s * 4, 0, Math.PI * 2); g.fill(); }
    }
  }

  /* =====================================================================
   * EARTH: dot-matrix globe from the land mask
   * ===================================================================== */
  var LAND = 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAID+fwD//wcAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAP////////8AAAAAAAAAAMAAAAAAAAAAAAAAAAAAgP///////z8AwP8H4AcAAPAHAAAAAAAAAAAAAABw/v///////w8AgP8AAAAAAMB/AAAAAAAAAAAAAID34Pcf/////w8AAP4BAAAwAAD8BwAAAAAAAAAAAMD/+/8H/v///wcAAAAAAOA/APz/HwD4HwAAAAAAAPB34/8PAP7//w8AAAAAAHgA4P///xzwDQAAAAAAAPD///8/APj//wcAAAAAADzA/////3/wDwAAA+AXAPD/5/f/B/z//wMAAAAHAHzw/////////wOAAPj/7///////D/j//wMAAPD/AQD////////////+A//////////zH/D/PwAAAP7/9///////////////P//////////zf/D/A2sAAP7////////////////////////////5P+D/gH8AAH//////////////////8Pz////////3H+AfAH8A4P//////////////////QP7//////w//H8APAAAA+M//////////////////AP///////wPwE4APAAAA+N////////////////0HAP8//f///wP4PwAAAAAw+I///////////////3wCAOAH8P///w/wfwAAAABw8Mf///////////8fAB8AAPADgP///3/w/wAAAAB44Mf///////////8PgB8AABwAgP///////wMAAAD84P//////////////gB8AAAAAgP7////7/wcAAAD++///////////////gAcAAAAAAP3//////w8AAAD+////////////////AAMAAAAAAPz//////w4AAADw////////////////AAAAAAAAAPD/////fx8AAADw////////////////AQAAAAAAAOD/////vx8AAADg//////H////////fAAAAAAAAAOD//////wEAAACA////f/D////////fAAAAAAAAAOD/////PwAAAACc///Pfvj////////HAQAAAAAAAPD/////AwAAAAD+//vHfPD////////jAwAAAAAAAOD/////AwAAAAD+Z////+D//////3/gAAAAAAAAAOD///9/AAAAAAD+Yf7///D//////39gAAAAAAAAAOD///9/AAAAAAD+Ie////D//////zkwAAAAAAAAAMD///8/AAAAAAD8/8b8//H//////3M4AAAAAAAAAID///8/AAAAAAD4/4Dj//////////A/AAAAAAAAAID///8PAAAAAAD8/wCA/////////9EHAAAAAAAAAAD+//8HAAAAAAD+/+fT/////////8MBAAAAAAAAAAD8//8DAAAAAAD+/////////////8MAAAAAAAAAAAD8/58HAAAAAAD//////////////wMAAAAAAAAAAAD4/wAXAAAAAID///////3//////wMAAAAAAAAAAADw/wAeAAAAAMD///9//////////wAAAAAAAAAAAADgfwAeAAAAAOD//////7///////wMAAAAAAAAAAADAf4AfAAAAAOD//////v/w////fwEAAAAAAOAAAAAA/vA/AAAAAPD//////f/A////HwEAAAAAAIABAAAA/nj4AwAAAPD//////X/A/+f/BwAAAAAAAAABAAAA/D/4HwAAAOD/////+38A/8F/AwMAAAAAAAAAAAAA+D8wGQAAAPD/////+z8A/4D/AAMAAAAAAAAAAAAAwP8BAAAAAPD/////9wcAfsD/gQMAAAAAAAAAAAAAAPwBAAAAAPD//////wMAPgD+AQcAAAAAAAAAAAAAAPABAwAAAPD//////wYAPgD+AQ8AAAAAAAAAAAAAAMDh7wAAAOD//////wcAPAD2gQ4AAAAAAAAAAAAAAMDv/wAAAMD//////wMAPADmwB4AAAAAAAAAAAAAAAD//wEAAID//////wMAeABGQB4AAAAAAAAAAAAAAAD0/wsAAID//////wEAYAAcYB4AAAAAAAAAAAAAAADw/z8AAAD++f///wEAIIAd8AgAAAAAAAAAAAAAAADw/z8AAAAE+P///wAAAAAf+AAAAAAAAAAAAAAAAAD4/38AAAAAwP///wAAAAA+figAAAAAAAAAAAAAAAD8/38AAAAAwP//PwAAAAA+/z8AAAAAAAAAAAAAAAD8//8BAAAA4P//HwAAAAA8/6cDAAAAAAAAAAAAAAD8//8/AAAAwP//DwAAAAB4vuN/MAAAAAAAAAAAAAD+//9/AAAAgP//BwAAAABwvPv/cQAAAAAAAAAAAAD+////AQAAgP//BwAAAADggAf+vwAAAAAAAAAAAAD+////AQAAAP//BwAAAADADwDynwMAAAAAAAAAAAD4////AQAAAP//BwAAAAAA/xv4Bw4AAAAAAAAAAAD4////AQAAAP//BwAAAAAA4A3AHBwAAAAAAAAAAADw////AAAAAP7/BwAAAAAAAIDHEBgAAAAAAAAAAADw//9/AAAAAP//DwMAAAAAAMDPAAAAAAAAAAAAAADg//9/AAAAAP//jwMAAAAAAPjHAYAAAQAAAAAAAADg//9/AAAAgP//5wMAAAAAAPzPAYCAAQAAAAAAAAAA//8/AAAAgP//5wMAAAAAAP7/A4DAAAAAAAAAAAAA/v8/AAAAgP//4QEAAAAAAP//BwDAAAAAAAAAAAAA/v8/AAAAAP//4AEAAAAA4P//D2AAAAAAAAAAAAAA/v8fAAAAAP7/8AAAAAAA+P//H+AAAAAAAAAAAAAA/v8fAAAAAP7/8AAAAAAA+P//HwAAAAAAAAAAAAAA/v8DAAAAAP7/4AAAAAAA+P//PwAAAAAAAAAAAAAA//8AAAAAAP4/QAAAAAAA+P//fwAAAAAAAAAAAAAA//8AAAAAAPw/AAAAAAAA8P//fwAAAAAAAAAAAAAA//8AAAAAAPw/AAAAAAAA8P//fwAAAAAAAAAAAAAA/38AAAAAAPgfAAAAAAAA8P//fwAAAAAAAAAAAAAA/z8AAAAAAPgPAAAAAAAA4H//PwAAAAAAAAAAAAAA/x8AAAAAAPAHAAAAAAAA8Af+PwAIAAAAAAAAAACA/w8AAAAAACAAAAAAAAAA4AD8HwAYAAAAAAAAAADA/wcAAAAAAAAAAAAAAAAAAADgHwA4AAAAAAAAAADA/wMAAAAAAAAAAAAAAAAAAADgDwDwAAAAAAAAAADAfwAAAAAAAAAAAAAAAAAAAAAAAgB4AAAAAAAAAADAfwAAAAAAAAAAAAAAAAAAAAAABwA8AAAAAAAAAADAPwAAAAAAAAAAAAAAAAAAAAAABwAOAAAAAAAAAADAHwAAAAAAAAAAAAAAAAAAAAAAAgAPAAAAAAAAAADAHwAAAAAAAAAAAAAAAAAAAAAAAIADAAAAAAAAAADgHwAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAADgHwAAAAAAAAAAAADgAAAAAAAAAAAAAAAAAAAAAADgBwAAAAAAAAAAAABgAAAAAAAAAAAAAAAAAAAAAADghwMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAADABwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACAHwAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAABAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAgAMAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA8AAAAAAAAAAAADgAAAAwCAAEAAAAAAAAAAAAAAAAfAAAAAAAAAAAAP8EwP//////AwAAAAAAAAAAAAAAPgAAAAAAAADA+P9/8P///////wAAAAAAAAAAAAAAfwAAAAAAcH////9//////////w8AAAAAAAAA+ADgfwAAAAD///////////////////8HAAAAAFgB/P/U/wAAAOD///////////////////8HAAAA+P///P///wAAAPD///////////////////8BAADA////////PwAA4P///////////////////z8AAMD/////////AQAB/v///////////////////z8AAPz///////9/AMAP//////////////////////8AABDg////////+fkP/v///////////////////w8AAID///////////H//////////////////////z8AQAD+//////////////////////////////////8B////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////';
  var MW = 240, MH = 120, mask = null;
  function isLand(lat, lon) {
    if (!mask) { var bin = atob(LAND); mask = new Uint8Array(bin.length); for (var i = 0; i < bin.length; i++) mask[i] = bin.charCodeAt(i); }
    var x = Math.floor((lon + 180) / 360 * MW) % MW, y = clamp(Math.floor((90 - lat) / 180 * MH), 0, MH - 1);
    var idx = y * MW + x;
    return (mask[idx >> 3] >> (idx & 7)) & 1;
  }
  var dots = [];
  function buildDots(n) {
    dots = [];
    var golden = Math.PI * (3 - Math.sqrt(5));
    for (var i = 0; i < n; i++) {
      var yy = 1 - (i / (n - 1)) * 2, lat = Math.asin(yy) / DEG, lon = ((i * golden) / DEG) % 360 - 180;
      if (isLand(lat, lon)) dots.push({ sl: Math.sin(lat * DEG), cl: Math.cos(lat * DEG), lon: lon * DEG });
    }
  }
  // SEC filers' headquarters (approximate) and the SEC in Washington, DC
  var SEC = { lat: 38.90, lon: -77.04 };
  var CITIES = [
    [37.37, -121.97, 'NVDA'], [37.32, -122.03, 'AAPL'], [47.67, -122.12, 'MSFT'], [37.42, -122.08, 'GOOGL'],
    [47.61, -122.33, 'AMZN'], [30.27, -97.74, 'TSLA'], [40.71, -74.0, 'JPM'], [35.23, -80.84, 'BAC'],
    [39.77, -86.16, 'LLY'], [30.08, -95.42, 'XOM'], [45.49, -122.80, 'NKE'], [41.26, -95.94, 'BRKB'],
    [44.91, -93.50, 'UNH'], [37.24, -121.96, 'NFLX'], [24.80, 120.97, 'TSM'], [51.42, 5.40, 'ASML'],
    [51.50, -0.12, '20-F'], [35.68, 139.69, '6-K'], [48.86, 2.35, '20-F'], [-23.55, -46.63, '6-K'],
    [19.08, 72.88, '20-F'], [31.23, 121.47, '6-K'], [43.65, -79.38, '40-F'], [-33.87, 151.21, '6-K'], [47.37, 8.54, '20-F']
  ];
  function toVec(lat, lon) { var a = lat * DEG, b = lon * DEG; return [Math.cos(a) * Math.cos(b), Math.cos(a) * Math.sin(b), Math.sin(a)]; }
  function arcPoints(a, b, n) {
    var A = toVec(a.lat, a.lon), B = toVec(b.lat, b.lon);
    var d = Math.acos(clamp(A[0] * B[0] + A[1] * B[1] + A[2] * B[2], -1, 1)), out = [];
    for (var i = 0; i <= n; i++) {
      var t = i / n, s1 = Math.sin((1 - t) * d) / Math.sin(d), s2 = Math.sin(t * d) / Math.sin(d);
      var x = s1 * A[0] + s2 * B[0], y = s1 * A[1] + s2 * B[1], z = s1 * A[2] + s2 * B[2];
      out.push({ sl: z, cl: Math.sqrt(x * x + y * y), lon: Math.atan2(y, x), h: Math.sin(Math.PI * t) * (0.08 + d * 0.12) });
    }
    return out;
  }
  var arcs = CITIES.map(function (c, i) { return { pts: arcPoints({ lat: c[0], lon: c[1] }, SEC, 40), off: i * 0.137, label: c[2] }; });

  /* =====================================================================
   * STORY CANVAS: globe + arcs + hive particles
   * ===================================================================== */
  var story = $('story'), canvas = $('story-canvas'), ctx = canvas.getContext('2d');
  var W = 0, H = 0, DPR = 1, mobile = false;
  var rot = -100 * DEG, tilt = 22 * DEG, vel = 0.0009, dragging = false, lastX = 0, lastY = 0, idleSpin = 0.0009;
  var parts = [], links = [], bridges = [], K = 6, sprite;
  var COLORS = ['168,180,255', '103,232,249', '245,201,122', '183,148,255', '249,168,212', '125,211,252'];

  function makeSprite() {
    sprite = document.createElement('canvas'); sprite.width = sprite.height = 64;
    var g = sprite.getContext('2d'), grd = g.createRadialGradient(32, 32, 0, 32, 32, 32);
    grd.addColorStop(0, 'rgba(255,255,255,0.9)'); grd.addColorStop(0.25, 'rgba(255,255,255,0.35)'); grd.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
  }

  function buildHive() {
    var r = rng(1717), N = mobile ? 110 : 200;
    parts = [];
    for (var i = 0; i < N; i++) {
      var c = i % K, hub = i < K, ang = r() * Math.PI * 2;
      var rad = hub ? 0 : Math.pow(r(), 0.6);
      var hexA = Math.round(ang / (Math.PI / 3)) * (Math.PI / 3);
      parts.push({ c: c, hub: hub, ang: ang, rad: rad, hexA: hexA + (i % 3) * 0.35, hexR: hub ? 0 : (Math.round(rad * 4) + 1) / 5,
        slat: (r() - 0.5) * 2, slon: r() * Math.PI * 2, size: hub ? 3.4 : 0.9 + r() * 1.4, ph: r() * Math.PI * 2, x: 0, y: 0 });
    }
    links = [];
    for (var j = K; j < N; j++) { links.push([j, parts[j].c]); if (j + K < N && r() < 0.55) links.push([j, j + K]); }
    bridges = [];
    for (var h = 0; h < K; h++) { bridges.push([h, (h + 1) % K]); if (h < K / 2) bridges.push([h, h + K / 2]); }
  }

  function resize() {
    DPR = Math.min(window.devicePixelRatio || 1, 1.5);
    W = canvas.clientWidth || innerWidth; H = canvas.clientHeight || innerHeight;
    canvas.width = Math.round(W * DPR); canvas.height = Math.round(H * DPR);
    var wasMobile = mobile; mobile = W < 760;
    if (!dots.length || wasMobile !== mobile) buildDots(mobile ? 14000 : 26000);
    buildHive();
    drawStars('stars-far', mobile ? 260 : 520, 0.9, 7);
    drawStars('stars-near', mobile ? 60 : 120, 1.6, 11);
  }

  function globeLayout(p) {
    var m = Math.min(W, H), a = smooth(0.18, 0.36, p), b = smooth(0.42, 0.6, p), c = smooth(0.66, 0.84, p);
    if (mobile) {
      return { cx: W * 0.5, cy: lerp(H * 0.30, H * 0.34, c), R: lerp(lerp(Math.min(W * 0.40, H * 0.24), Math.min(W * 0.36, H * 0.22), b), Math.min(W, H) * 0.12, c) };
    }
    var cx = lerp(lerp(lerp(W * 0.72, W * 0.70, a), W * 0.74, b), W * 0.67, c);
    var R = lerp(lerp(lerp(Math.min(m * 0.40, W * 0.21), Math.min(m * 0.38, W * 0.2), a), m * 0.30, b), m * 0.15, c);
    return { cx: cx, cy: H * 0.52, R: R };
  }

  function project(pt, L, sinT, cosT, h) {
    var dl = pt.lon - rot, cd = Math.cos(dl);
    var x = pt.cl * Math.sin(dl), y = cosT * pt.sl - sinT * pt.cl * cd, z = sinT * pt.sl + cosT * pt.cl * cd;
    var k = L.R * (1 + (h || 0));
    return { X: L.cx + k * x, Y: L.cy - k * y, z: z, x: x, y: y, k: k };
  }

  function draw(p, time) {
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
    ctx.clearRect(0, 0, W, H);
    var t = time * 0.001, L = globeLayout(p), sinT = Math.sin(tilt), cosT = Math.cos(tilt);
    var R = L.R;

    // atmosphere + ocean
    var atm = ctx.createRadialGradient(L.cx, L.cy, R * 0.92, L.cx, L.cy, R * 1.35);
    atm.addColorStop(0, 'rgba(123,135,255,0.32)'); atm.addColorStop(0.35, 'rgba(103,232,249,0.08)'); atm.addColorStop(1, 'rgba(103,232,249,0)');
    ctx.fillStyle = atm; ctx.beginPath(); ctx.arc(L.cx, L.cy, R * 1.35, 0, Math.PI * 2); ctx.fill();
    var ocean = ctx.createRadialGradient(L.cx - R * 0.35, L.cy - R * 0.4, R * 0.1, L.cx, L.cy, R);
    ocean.addColorStop(0, '#16205a'); ocean.addColorStop(0.6, '#0a0f33'); ocean.addColorStop(1, '#05071c');
    ctx.fillStyle = ocean; ctx.beginPath(); ctx.arc(L.cx, L.cy, R, 0, Math.PI * 2); ctx.fill();

    // land dots with day/night shading (light from upper-left-front)
    var lx = -0.55, ly = 0.45, lz = 0.70, ds = Math.max(1.2, R / 190);
    for (var i = 0; i < dots.length; i++) {
      var q = project(dots[i], L, sinT, cosT);
      if (q.z <= 0) continue;
      var light = Math.max(0, q.x * lx + q.y * ly + q.z * lz);
      var a = (0.28 + 0.72 * light) * (0.45 + 0.55 * q.z);
      ctx.fillStyle = light > 0.25 ? 'rgba(205,214,255,' + a.toFixed(3) + ')' : 'rgba(130,140,230,' + (a * 0.85).toFixed(3) + ')';
      ctx.fillRect(q.X - ds / 2, q.Y - ds / 2, ds, ds);
    }
    // rim light
    ctx.strokeStyle = 'rgba(168,180,255,0.35)'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(L.cx, L.cy, R, 0, Math.PI * 2); ctx.stroke();

    // filing arcs from HQs to the SEC
    var arcAmt = 0.35 + 0.65 * win(p, 0.16, 0.30, 0.62, 0.74);
    ctx.globalCompositeOperation = 'lighter';
    for (var k = 0; k < arcs.length; k++) {
      var arc = arcs[k], pts = arc.pts, phase = (t * 0.22 + arc.off) % 1.6;
      if (phase > 1) continue;
      var head = Math.floor(phase * pts.length), tail = Math.max(0, head - 14);
      ctx.beginPath(); var started = false;
      for (var j = tail; j <= Math.min(head, pts.length - 1); j++) {
        var pr = project(pts[j], L, sinT, cosT, pts[j].h);
        var vis = pr.z > 0 || (pr.x * pr.x + pr.y * pr.y) * (1 + pts[j].h) * (1 + pts[j].h) > 1;
        if (!vis) { started = false; continue; }
        if (!started) { ctx.moveTo(pr.X, pr.Y); started = true; } else ctx.lineTo(pr.X, pr.Y);
      }
      ctx.strokeStyle = 'rgba(245,201,122,' + (0.55 * arcAmt).toFixed(3) + ')'; ctx.lineWidth = 1.2; ctx.stroke();
      var hp = pts[Math.min(head, pts.length - 1)], hq = project(hp, L, sinT, cosT, hp.h);
      if (hq.z > 0 || (hq.x * hq.x + hq.y * hq.y) > 1) { ctx.globalAlpha = arcAmt; ctx.drawImage(sprite, hq.X - 7, hq.Y - 7, 14, 14); ctx.globalAlpha = 1; }
    }
    // city lights and the SEC beacon
    for (var c = 0; c < CITIES.length; c++) {
      var cq = project({ sl: Math.sin(CITIES[c][0] * DEG), cl: Math.cos(CITIES[c][0] * DEG), lon: CITIES[c][1] * DEG }, L, sinT, cosT);
      if (cq.z <= 0.05) continue;
      var pulse = (t * 0.6 + c * 0.31) % 1;
      ctx.strokeStyle = 'rgba(103,232,249,' + ((1 - pulse) * 0.5 * cq.z).toFixed(3) + ')';
      ctx.beginPath(); ctx.arc(cq.X, cq.Y, 2 + pulse * 10, 0, Math.PI * 2); ctx.stroke();
      ctx.globalAlpha = cq.z; ctx.drawImage(sprite, cq.X - 5, cq.Y - 5, 10, 10); ctx.globalAlpha = 1;
    }
    var sq = project({ sl: Math.sin(SEC.lat * DEG), cl: Math.cos(SEC.lat * DEG), lon: SEC.lon * DEG }, L, sinT, cosT);
    if (sq.z > 0) {
      var gs = 30 + Math.sin(t * 2) * 6;
      ctx.globalAlpha = 0.9 * sq.z; ctx.drawImage(sprite, sq.X - gs / 2, sq.Y - gs / 2, gs, gs); ctx.globalAlpha = 1;
      ctx.globalCompositeOperation = 'source-over';
      ctx.font = '500 10px "IBM Plex Mono", monospace'; ctx.fillStyle = 'rgba(245,201,122,' + (0.9 * sq.z).toFixed(2) + ')';
      ctx.fillText('SEC EDGAR', sq.X + 10, sq.Y - 8);
      ctx.globalCompositeOperation = 'lighter';
    }

    // hive: particles rise from the surface into clusters orbiting the planet
    var mH = smooth(0.62, 0.86, p), show = smooth(0.56, 0.66, p);
    if (show > 0.01) {
      var ring = Math.min(W, H) * (mobile ? 0.30 : 0.31), cr = mobile ? 34 : 56;
      for (var n = 0; n < parts.length; n++) {
        var s = parts[n];
        var su = project({ sl: s.slat, cl: Math.sqrt(1 - s.slat * s.slat), lon: s.slon }, L, sinT, cosT);
        var ca = s.c / K * Math.PI * 2 - Math.PI / 2 + t * 0.03;
        var ccx = L.cx + Math.cos(ca) * ring * (s.c % 2 ? 1 : 0.84), ccy = L.cy + Math.sin(ca) * ring * 0.8;
        var hx = ccx + Math.cos(s.hexA) * s.hexR * cr + Math.sin(t * 0.4 + s.ph) * 3;
        var hy = ccy + Math.sin(s.hexA) * s.hexR * cr + Math.cos(t * 0.35 + s.ph) * 3;
        s.x = lerp(su.X, hx, mH); s.y = lerp(su.Y, hy, mH);
      }
      ctx.lineWidth = 0.6;
      for (var l = 0; l < links.length; l++) {
        var A = parts[links[l][0]], B = parts[links[l][1]];
        ctx.strokeStyle = 'rgba(' + COLORS[A.c] + ',' + (0.22 * mH * show).toFixed(3) + ')';
        ctx.beginPath(); ctx.moveTo(A.x, A.y); ctx.lineTo(B.x, B.y); ctx.stroke();
      }
      for (var bI = 0; bI < bridges.length; bI++) {
        var h1 = parts[bridges[bI][0]], h2 = parts[bridges[bI][1]], pu = 0.5 + 0.5 * Math.sin(t * 1.2 + bI);
        ctx.setLineDash([3, 5]); ctx.strokeStyle = 'rgba(245,201,122,' + ((0.12 + 0.2 * pu) * mH).toFixed(3) + ')';
        ctx.beginPath(); ctx.moveTo(h1.x, h1.y); ctx.lineTo(h2.x, h2.y); ctx.stroke(); ctx.setLineDash([]);
        var f = (t * 0.25 + bI * 0.17) % 1;
        ctx.globalAlpha = mH * Math.sin(f * Math.PI); ctx.drawImage(sprite, lerp(h1.x, h2.x, f) - 9, lerp(h1.y, h2.y, f) - 9, 18, 18); ctx.globalAlpha = 1;
      }
      for (var m = 0; m < parts.length; m++) {
        var q2 = parts[m], tw = 0.6 + 0.4 * Math.sin(t * 1.5 + q2.ph);
        ctx.fillStyle = 'rgba(' + COLORS[q2.c] + ',' + (show * (0.45 + 0.5 * tw)).toFixed(3) + ')';
        ctx.beginPath(); ctx.arc(q2.x, q2.y, q2.size * (1 + mH * (q2.hub ? 0.9 : 0.3)), 0, Math.PI * 2); ctx.fill();
        if (q2.hub) { ctx.globalAlpha = 0.6 * mH; var g2 = 40 + mH * 30; ctx.drawImage(sprite, q2.x - g2 / 2, q2.y - g2 / 2, g2, g2); ctx.globalAlpha = 1; }
      }
    }
    ctx.globalCompositeOperation = 'source-over';
  }

  /* ---------------- interaction: drag, inertia, keyboard ---------------- */
  canvas.addEventListener('pointerdown', function (e) {
    dragging = true; lastX = e.clientX; lastY = e.clientY; vel = 0;
    canvas.classList.add('dragging');
    try { canvas.setPointerCapture(e.pointerId); } catch (err) {}
    hideDragHint();
  });
  canvas.addEventListener('pointermove', function (e) {
    if (!dragging) return;
    var dx = e.clientX - lastX, dy = e.clientY - lastY;
    lastX = e.clientX; lastY = e.clientY;
    var k = 1 / Math.max(120, globeLayout(current).R);
    rot -= dx * k; vel = -dx * k * 0.25;
    if (e.pointerType === 'mouse') tilt = clamp(tilt + dy * k, -0.35, 1.0);
    if (reduce) drawStatic();
  });
  function endDrag() { dragging = false; canvas.classList.remove('dragging'); }
  canvas.addEventListener('pointerup', endDrag);
  canvas.addEventListener('pointercancel', endDrag);
  canvas.addEventListener('keydown', function (e) {
    var used = true;
    if (e.key === 'ArrowLeft') rot += 0.25; else if (e.key === 'ArrowRight') rot -= 0.25;
    else if (e.key === 'ArrowUp') tilt = clamp(tilt + 0.12, -0.35, 1.0); else if (e.key === 'ArrowDown') tilt = clamp(tilt - 0.12, -0.35, 1.0);
    else used = false;
    if (used) { e.preventDefault(); hideDragHint(); if (reduce) drawStatic(); }
  });
  var hintHidden = false;
  function hideDragHint() { if (hintHidden) return; hintHidden = true; var h = document.querySelector('.drag-hint'); if (h) h.style.opacity = '0'; }

  /* ---------------- DOM layers ---------------- */
  var scenes = Array.prototype.slice.call(document.querySelectorAll('.scene'));
  var dotsEls = Array.prototype.slice.call(document.querySelectorAll('.story-progress i'));
  var layerMid = document.querySelector('.layer-mid'), layerBg = document.querySelector('.layer-bg');
  var starsFar = $('stars-far'), starsNear = $('stars-near'), galaxyTilt = document.querySelector('.galaxy-tilt');
  var glowA = document.querySelector('.glow-a'), glowB = document.querySelector('.glow-b'), glowC = document.querySelector('.glow-c');
  var fragDiff = document.querySelector('.frag-diff'), fragScore = document.querySelector('.frag-score'), fragAgents = document.querySelector('.frag-agents'), fragFeed = document.querySelector('.frag-feed');
  var hint = document.querySelector('.scroll-hint'), dragHint = document.querySelector('.drag-hint');
  var lastScene = -1, mx = 0, my = 0, tmx = 0, tmy = 0;
  window.addEventListener('pointermove', function (e) { if (e.pointerType !== 'mouse') return; tmx = e.clientX / innerWidth - 0.5; tmy = e.clientY / innerHeight - 0.5; }, { passive: true });

  function tf(el, x, y, s) { if (el) el.style.transform = 'translate3d(' + x.toFixed(1) + 'px,' + y.toFixed(1) + 'px,0)' + (s ? ' scale(' + s.toFixed(4) + ')' : ''); }
  function layout(p) {
    var segs = scenes.length, active = clamp(Math.floor(p * segs), 0, segs - 1);
    for (var i = 0; i < segs; i++) {
      var d = (p - (i + 0.5) / segs) * segs;
      if (i === 0 && d < 0) d = 0;
      if (i === segs - 1 && d > 0) d = 0;
      var o = 1 - smooth(0.28, 0.5, Math.abs(d));
      scenes[i].style.opacity = o.toFixed(3);
      scenes[i].style.transform = (mobile ? 'translate3d(0,' : 'translate3d(0,calc(-50% + ') + (-d * 60).toFixed(1) + 'px' + (mobile ? '' : ')') + ',0) scale(' + (1 - Math.abs(d) * 0.03).toFixed(4) + ')';
    }
    if (active !== lastScene) {
      scenes.forEach(function (s, k) { s.classList.toggle('is-active', k === active); });
      dotsEls.forEach(function (dd, k) { dd.classList.toggle('on', k === active); });
      lastScene = active;
    }
    // layered parallax: background < far stars < galaxy < near stars < mid UI < type
    tf(layerBg, mx * -10, (0.5 - p) * 30 + my * -8);
    tf(starsFar, mx * -14, (0.5 - p) * 50 + my * -10);
    tf(starsNear, mx * -30, (0.5 - p) * 140 + my * -22);
    if (galaxyTilt) galaxyTilt.style.transform = 'translate3d(' + (mx * -18 - p * 60).toFixed(1) + 'px,' + ((0.5 - p) * 70).toFixed(1) + 'px,0) rotate(-24deg) scaleY(0.46) scale(' + (1 + p * 0.35).toFixed(3) + ')';
    tf(layerMid, mx * 12, (0.5 - p) * 140 + my * 10);
    glowA.style.transform = 'translate3d(' + (-p * 12).toFixed(2) + 'vw,' + (p * 8).toFixed(2) + 'vh,0) scale(' + (1 + p * 0.45).toFixed(3) + ')';
    glowB.style.opacity = (0.5 + 0.5 * win(p, 0.2, 0.45, 0.8, 1.01)).toFixed(3);
    glowC.style.opacity = (0.4 + 0.6 * smooth(0.55, 0.9, p)).toFixed(3);
    glowC.style.transform = 'scale(' + (0.9 + p * 0.3).toFixed(3) + ')';
    if (fragDiff) {
      fragFeed.style.opacity = win(p, 0.20, 0.30, 0.44, 0.52).toFixed(3);
      tf(fragFeed, 0, (0.4 - p) * 80);
      fragDiff.style.opacity = win(p, 0.30, 0.42, 0.66, 0.76).toFixed(3);
      tf(fragDiff, 0, (0.5 - p) * 60);
      fragScore.style.opacity = win(p, 0.50, 0.60, 0.74, 0.84).toFixed(3);
      tf(fragScore, 0, (0.6 - p) * 120);
      fragAgents.style.opacity = win(p, 0.54, 0.64, 0.70, 0.78).toFixed(3);
      tf(fragAgents, 0, (0.7 - p) * 90);
    }
    if (hint) hint.style.opacity = (1 - smooth(0, 0.06, p)).toFixed(3);
    if (dragHint && !hintHidden) dragHint.style.opacity = (1 - smooth(0.1, 0.2, p)).toFixed(3);
  }

  /* ---------------- loop ---------------- */
  var target = 0, current = 0, running = false, visible = true;
  function readScroll() {
    var rect = story.getBoundingClientRect(), total = story.offsetHeight - innerHeight;
    target = total > 0 ? clamp(-rect.top / total, 0, 1) : 0;
  }
  var lastT = 0;
  function frame(time) {
    var dt = lastT ? Math.min(50, time - lastT) : 16; lastT = time;
    current += (target - current) * 0.075;
    if (Math.abs(target - current) < 0.0004) current = target;
    mx += (tmx - mx) * 0.05; my += (tmy - my) * 0.05;
    if (!dragging) { vel += (idleSpin - vel) * 0.02; rot += vel * dt / 16; }
    layout(current);
    draw(current, time);
    if (visible) requestAnimationFrame(frame); else { running = false; lastT = 0; }
  }
  function start() { if (!running) { running = true; requestAnimationFrame(frame); } }

  function initLive() {
    story.classList.add('live');
    makeSprite(); resize(); readScroll(); current = target;
    addEventListener('scroll', readScroll, { passive: true });
    var rT; addEventListener('resize', function () { clearTimeout(rT); rT = setTimeout(function () { resize(); readScroll(); }, 120); });
    if ('IntersectionObserver' in window) new IntersectionObserver(function (en) { visible = en[0].isIntersecting; if (visible) start(); }).observe(story);
    start();
  }
  function drawStatic() { draw(0.1, 0); }
  function initStatic() {
    story.classList.remove('live');
    makeSprite(); resize(); drawStatic();
    scenes.forEach(function (s) { s.style.opacity = ''; s.style.transform = ''; });
    addEventListener('resize', function () { resize(); drawStatic(); });
  }
  drawGalaxy();
  if (reduce) initStatic(); else initLive();

  /* =====================================================================
   * HERO FEED + CRAWLER CONSOLE (simulated events across the full catalog)
   * ===================================================================== */
  var TICKS = [['NVDA', '0001045810'], ['AAPL', '0000320193'], ['MSFT', '0000789019'], ['AMZN', '0001018724'], ['JPM', '0000019617'], ['NKE', '0000320187'],
    ['LLY', '0000059478'], ['XOM', '0000034088'], ['TSM', '0001046179'], ['ASML', '0000937966'], ['GS', '0000886982'], ['BRKB', '0001067983']];
  var er = rng(99);
  function pick(a) { return a[Math.floor(er() * a.length)]; }
  var secForms = F ? F.CATALOG.filter(function (f) { return f.cat !== 'other'; }) : [];
  function acc(cik) { return cik.slice(-7).replace(/^0+/, '') + '-24-' + String(100000 + Math.floor(er() * 899999)); }
  function hex(n) { var s = ''; for (var i = 0; i < n; i++) s += '0123456789abcdef'[Math.floor(er() * 16)]; return s; }

  var heroFeed = $('hero-feed');
  function heroLine() {
    if (!heroFeed || !secForms.length) return;
    var t = pick(TICKS), f = pick(secForms);
    var li = document.createElement('li');
    li.innerHTML = '<b>' + esc(t[0]) + '</b> ' + esc(f.code) + ' \u00b7 ' + (200 + Math.floor(er() * 900)) + ' KB';
    heroFeed.appendChild(li);
    while (heroFeed.children.length > 5) heroFeed.removeChild(heroFeed.firstChild);
  }
  for (var hf = 0; hf < 5; hf++) heroLine();
  if (!reduce) setInterval(function () { if (current > 0.15 && current < 0.55) heroLine(); }, 900);

  var log = $('console-log'), metrics = { disc: 0, ret: 0, dup: 0, cite: 0 };
  var AG = F ? F.AGENTS.map(function (a) { return a.name; }) : ['Financial'];
  function consoleEvent() {
    var t = pick(TICKS), f = pick(secForms), a = acc(t[1]), kind = er(), html;
    if (kind < 0.24) { metrics.disc++; html = '<span class="k k-disc">DISCOVER</span> ' + t[0] + ' ' + esc(f.code) + (er() < 0.12 ? '/A amendment' : '') + ' acc ' + a; }
    else if (kind < 0.46) { metrics.ret++; html = '<span class="k k-get">FETCH</span> ' + a + ' ' + (150 + Math.floor(er() * 900)) + ' KB sha256:' + hex(10) + '\u2026'; }
    else if (kind < 0.54) { metrics.dup++; html = '<span class="k k-dup">DEDUP</span> ' + a + ' hash seen \u00b7 skipped'; }
    else if (kind < 0.58) { html = '<span class="k k-retry">RETRY</span> HTTP 429 \u00b7 backoff ' + (1 + Math.floor(er() * 4)) + 's \u00b7 fair-access limit'; }
    else if (kind < 0.76) { html = '<span class="k k-parse">PARSE</span> ' + t[0] + ' ' + esc(f.code) + ' ' + pick(['HTML 14 sections', 'iXBRL ' + (400 + Math.floor(er() * 1500)) + ' facts', 'PDF exhibit text layer', 'XLSX financial report', 'EX-10 material contract', 'tables rebuilt + concepts normalized']); }
    else if (kind < 0.92) { html = '<span class="k k-agent">AGENT</span> ' + pick(AG) + ' \u00b7 ' + t[0] + ' ' + esc(f.code) + ' \u00b7 ' + pick(['new disclosure flagged', 'metric reconciled to XBRL', 'contradiction vs prior filing', 'no anomalies', 'linked shared director', 'cross-checked external source']); }
    else { metrics.cite++; html = '<span class="k k-cite">CITE</span> ' + t[0] + ' ' + esc(f.code) + ' \u2192 Item ' + pick(['1A', '7', '8', '2.03', '5.02']) + ' p.' + (3 + Math.floor(er() * 90)); }
    var li = document.createElement('li'); li.innerHTML = html; log.appendChild(li);
    while (log.children.length > 11) log.removeChild(log.firstChild);
    $('m-disc').textContent = metrics.disc; $('m-ret').textContent = metrics.ret; $('m-dup').textContent = metrics.dup; $('m-cite').textContent = metrics.cite;
    $('console-rate').textContent = (6 + er() * 3.8).toFixed(1) + ' req/s \u00b7 limit 10';
  }
  if (log) {
    for (var ce = 0; ce < 11; ce++) consoleEvent();
    if (!reduce && 'IntersectionObserver' in window) {
      var cTimer = 0;
      new IntersectionObserver(function (en) {
        if (en[0].isIntersecting) { if (!cTimer) cTimer = setInterval(consoleEvent, 650); }
        else { clearInterval(cTimer); cTimer = 0; }
      }).observe(log);
    }
  }

  /* ---------------- crawler subsystems (tabs) ---------------- */
  var SUBSYSTEMS = [
    { t: 'Data acquisition & crawling', p: 'Integrates directly with SEC EDGAR APIs, filing indexes and historical bulk archives.', li: [
      '<b>Monitors 50+ form types</b> including 10-K, 10-Q, 8-K, S-1, S-4, DEF 14A, Forms 3/4/5, 13D and 13G.',
      '<b>Identity resolution</b> by CIK, with ticker and historical-name mapping.',
      '<b>Detects new filings and amendments</b> automatically.',
      '<b>Retrieves</b> original filings, exhibits, attachments and XBRL data.',
      '<b>Intelligent scheduling</b>, deduplication, retries and source rate limiting.'] },
    { t: 'Document extraction & processing', p: 'Turns raw documents into structured, traceable data.', li: [
      '<b>Parses</b> HTML, Inline XBRL, PDFs, spreadsheets and supporting exhibits.',
      '<b>Extracts</b> financial statements, footnotes, risk factors, management commentary and material agreements.',
      '<b>Reconstructs</b> complex financial tables and normalizes accounting concepts.',
      '<b>Preserves</b> original documents, timestamps, source URLs and document hashes.',
      '<b>Keeps history</b>: every version, with complete document traceability.'] },
    { t: 'AI intelligence & analytics', p: 'Six specialized agents work in parallel and cross-check each other.', li: (F ? F.AGENTS : []).map(function (a) { return '<b>' + esc(a.name) + ':</b> ' + esc(a.text); }) },
    { t: 'Institutional-grade reports', p: 'Evidence-backed reports, generated automatically.', li: [
      '<b>Executive intelligence summary</b>, financial performance and historical trends.',
      '<b>Disclosure changes</b>, risk assessments and material developments.',
      '<b>Management commentary</b>, capital structure and ownership analysis.',
      '<b>Corporate transactions</b>, M&amp;A developments and forensic findings.',
      '<b>Every material finding cites</b> the filing, reporting period and supporting evidence.'] },
    { t: 'Core performance guarantees', p: 'What the production engine is held to.', li: [
      '<b>Continuous discovery</b> and automated ingestion; comprehensive historical indexing.',
      '<b>High-accuracy extraction</b> and automated historical comparisons.',
      '<b>Near-zero duplicate ingestion</b> via content hashing.',
      '<b>Source-level traceability</b> for every material finding.',
      '<b>Automated error recovery</b>, validation and strict SEC fair-access compliance.'] }
  ];
  var ssBtns = Array.prototype.slice.call(document.querySelectorAll('#subsystems [role="tab"]')), ssPanel = $('subsystem-panel');
  function showSS(i, focus) {
    ssBtns.forEach(function (b, k) { b.setAttribute('aria-selected', String(k === i)); b.tabIndex = k === i ? 0 : -1; if (k === i && focus) b.focus(); });
    ssPanel.setAttribute('aria-labelledby', 'ss-' + i);
    var s = SUBSYSTEMS[i];
    ssPanel.innerHTML = '<div class="fade"><h3>' + esc(s.t) + '</h3><p>' + esc(s.p) + '</p><ul>' + s.li.map(function (x) { return '<li><span>' + x + '</span></li>'; }).join('') + '</ul></div>';
  }
  ssBtns.forEach(function (b, i) {
    b.addEventListener('click', function () { showSS(i); });
    b.addEventListener('keydown', function (e) {
      var j = (e.key === 'ArrowDown' || e.key === 'ArrowRight') ? (i + 1) % ssBtns.length : (e.key === 'ArrowUp' || e.key === 'ArrowLeft') ? (i - 1 + ssBtns.length) % ssBtns.length : -1;
      if (j >= 0) { e.preventDefault(); showSS(j, true); }
    });
  });
  if (ssPanel) showSS(0);

  /* ---------------- coverage explorer ---------------- */
  if (F) {
    var tiersEl = $('tiers');
    tiersEl.innerHTML = [1, 2, 3].map(function (n) {
      var forms = F.CATALOG.filter(function (f) { return f.tier === n; });
      return '<div class="tier tier-' + n + '"><h3>' + F.TIERS[n].label + ' \u00b7 ' + esc(F.TIERS[n].name) + ' <span class="mono">' + esc(F.TIERS[n].note) + '</span></h3><p>' +
        forms.map(function (f) { return '<span class="tbadge t' + n + '">' + esc(f.code) + '</span>'; }).join('') + '</p></div>';
    }).join('');
    var tabsEl = $('cov-tabs'), panelEl = $('cov-panel');
    function inCat(c) { return F.CATALOG.filter(function (f) { return f.cats.indexOf(c) >= 0; }); }
    tabsEl.innerHTML = F.CAT_ORDER.map(function (c, i) {
      var C = F.CATEGORIES[c];
      return '<button type="button" role="tab" id="ct-' + c + '" aria-controls="cov-panel" aria-selected="' + (i === 0) + '" tabindex="' + (i === 0 ? 0 : -1) + '" data-c="' + c + '" style="--c:' + C.color + '"><i></i>' + esc(C.short) + ' <span class="n">' + inCat(c).length + '</span></button>';
    }).join('');
    var covBtns = Array.prototype.slice.call(tabsEl.querySelectorAll('button'));
    function showCat(c, focus) {
      covBtns.forEach(function (b) { var on = b.getAttribute('data-c') === c; b.setAttribute('aria-selected', String(on)); b.tabIndex = on ? 0 : -1; if (on && focus) b.focus(); });
      panelEl.setAttribute('aria-labelledby', 'ct-' + c);
      var C = F.CATEGORIES[c], rows = inCat(c);
      panelEl.innerHTML = '<p class="blurb">' + esc(C.blurb) + '</p><table class="cov-table"><caption class="sr-only">' + esc(C.label) + ' filings</caption><thead><tr><th scope="col">Filing</th><th scope="col">Name</th><th scope="col">What it contains</th><th scope="col">Priority</th></tr></thead><tbody>' +
        rows.map(function (f) {
          return '<tr class="t' + f.tier + '"><td class="code">' + esc(f.code) + '</td><td class="name">' + esc(f.name) + '</td><td class="desc">' + esc(f.desc) + '</td><td class="tier-cell">' +
            (f.tier ? '<span class="tbadge t' + f.tier + '">' + F.TIERS[f.tier].label + '</span>' : '<span class="tbadge">Covered</span>') + '</td></tr>';
        }).join('') + '</tbody></table>';
    }
    covBtns.forEach(function (b, i) {
      b.addEventListener('click', function () { showCat(b.getAttribute('data-c')); });
      b.addEventListener('keydown', function (e) {
        var j = e.key === 'ArrowRight' ? (i + 1) % covBtns.length : e.key === 'ArrowLeft' ? (i - 1 + covBtns.length) % covBtns.length : -1;
        if (j >= 0) { e.preventDefault(); showCat(covBtns[j].getAttribute('data-c'), true); }
      });
    });
    showCat('financial');

    $('features').innerHTML = F.FEATURES.map(function (f, i) {
      return '<li class="reveal"><span class="ico" aria-hidden="true">0' + (i + 1) + '</span><h3>' + esc(f.name) + '</h3><p>' + esc(f.text) + '</p></li>';
    }).join('');
  }

  /* ---------------- section reveals ---------------- */
  var reveals = document.querySelectorAll('.reveal');
  if (reduce || !('IntersectionObserver' in window)) {
    Array.prototype.forEach.call(reveals, function (el) { el.classList.add('in'); });
  } else {
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
    }, { rootMargin: '0px 0px -8% 0px', threshold: 0.1 });
    Array.prototype.forEach.call(reveals, function (el) { io.observe(el); });
  }
})();
