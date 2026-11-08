// O FILME — explicativo em traço de caneta. Coordenadas desenhadas em 1920x1080.
(function () {
  const U = globalThis.U, G = globalThis.G, S = globalThis.SCORE, Studio = globalThis.Studio;
  const { T, ev } = S;
  const { clamp, lerp, ease } = U;
  const INK = '#1B1A19', RED = '#C4302B', BLUE = '#6FA8DC';
  const hh = (a, b = 0) => U.hash(a, b);
  const mix = (c1, c2, k) => { const p = (c) => [1, 3, 5].map((i) => parseInt(c.slice(i, i + 2), 16)); const a = p(c1), b = p(c2); return '#' + a.map((v, i) => Math.round(lerp(v, b[i], k)).toString(16).padStart(2, '0')).join(''); };
  const HATCH = { color: 'rgba(27,26,25,0.32)', gap: 7 };
  const appear = (t, t0, d = 0.35) => ease.outBack(clamp((t - t0) / d), 1.6);

  const lab = (ctx, s, x, y, size = 46, o = {}) => G.text(ctx, s, x, y, { size, fam: 'Patrick Hand', weight: 400, color: INK, ...o });
  function arrow(ctx, x0, y0, x1, y1, p = 1, seed = 3) {
    const x = lerp(x0, x1, p), y = lerp(y0, y1, p), a = Math.atan2(y1 - y0, x1 - x0);
    const mx = (x0 + x) / 2 + (y1 - y0) * 0.12, my = (y0 + y) / 2 - (x1 - x0) * 0.12;
    G.line(ctx, [[x0, y0], [mx, my], [x, y]], { lw: 4, seed, step: 14 });
    if (p > 0.9) G.line(ctx, [[x - 26 * Math.cos(a - 0.45), y - 26 * Math.sin(a - 0.45)], [x, y], [x - 26 * Math.cos(a + 0.45), y - 26 * Math.sin(a + 0.45)]], { lw: 4, seed: seed + 1 });
  }
  function drops(ctx, x, y, t, n = 3, seed = 1, r = 1) {
    for (let i = 0; i < n; i++) { const u = ((t * 0.8 + hh(seed, i)) % 1); const dx = (i - (n - 1) / 2) * 34 * r, dy = u * 46 * r; ctx.save(); ctx.globalAlpha = 1 - u * u; G.ellipse(ctx, x + dx, y + dy, 7 * r, 10 * r, { fill: '#BFE0F7', lw: 2.5, seed: seed + i, second: false }); ctx.restore(); }
  }
  function spiral(ctx, x, y, r, t, seed = 1, rot = 0) {
    const pts = []; for (let i = 0; i < 26; i++) { const a = i * 0.55 + rot, rr = r * (i / 25); pts.push([x + Math.cos(a) * rr, y + Math.sin(a) * rr]); }
    G.line(ctx, pts, { lw: 3.5, seed, step: 100 });
  }

  // ---------- cabeça e rosto ----------
  function face(ctx, R, exp, t, seed) {
    const eye = (sd, big) => {
      const ex = sd * R * 0.36, ey = -R * 0.1, er = R * (big ? 0.27 : 0.23);
      if (exp === 'faint') { G.line(ctx, [[ex - er, ey], [ex + er, ey + 4]], { lw: 4, seed: seed + sd }); return; }
      if (exp === 'happy') { G.line(ctx, [[ex - er, ey + 6], [ex, ey - er * 0.7], [ex + er, ey + 6]], { lw: 4.5, seed: seed + sd }); return; }
      G.ellipse(ctx, ex, ey, er, er, { fill: '#FFFFFF', lw: 4, seed: seed + sd });
      if (exp === 'dizzy') { spiral(ctx, ex, ey, er * 0.9, t, seed + sd, t * 6 * sd); return; }
      const pr = exp === 'scared' ? 3.5 : 5.5, ox = exp === 'worried' ? sd * 0 + 3 : 0, oy = exp === 'scared' ? -2 : 3;
      G.ellipse(ctx, ex + ox, ey + oy, pr, pr, { fill: INK, lw: 1, seed: seed + 9 + sd, second: false });
    };
    eye(-1, exp === 'scared'); eye(1, exp === 'scared');
    if (exp === 'worried' || exp === 'scared') for (const sd of [-1, 1]) G.line(ctx, [[sd * R * 0.62, -R * 0.36 - (exp === 'scared' ? 8 : 0)], [sd * R * 0.14, -R * 0.55 - (exp === 'scared' ? 10 : 0)]], { lw: 4, seed: seed + 20 + sd });
    if (exp === 'dizzy') for (const sd of [-1, 1]) G.line(ctx, [[sd * R * 0.62, -R * 0.4], [sd * R * 0.15, -R * 0.5]], { lw: 4, seed: seed + 25 + sd });
    const my = R * 0.42;
    if (exp === 'scared') G.ellipse(ctx, 0, my, R * 0.17, R * 0.22, { fill: '#7A2A28', lw: 4, seed: seed + 30 });
    else if (exp === 'worried' || exp === 'dizzy') G.line(ctx, [[-R * 0.3, my + 4], [-R * 0.1, my - 6], [R * 0.1, my + 6], [R * 0.3, my - 3]], { lw: 4, seed: seed + 31 });
    else if (exp === 'faint') G.ellipse(ctx, 0, my, R * 0.11, R * 0.08, { fill: '#7A2A28', lw: 3.5, seed: seed + 32 });
    else if (exp === 'happy') G.line(ctx, [[-R * 0.34, my - 6], [0, my + 12], [R * 0.34, my - 6]], { lw: 4.5, seed: seed + 33 });
    else G.line(ctx, [[-R * 0.25, my], [0, my + 8], [R * 0.25, my]], { lw: 4, seed: seed + 34 });
  }

  // ---------- pessoas: Tonico (touca azul, bigode) e Nina (coque, óculos) ----------
  const ARMS = {
    down: [[[-80, -250], [-84, -180]], [[80, -250], [84, -180]]],
    hold: [[[-80, -250], [-84, -180]], [[70, -230], [36, -135]]],
    phone: [[[-80, -250], [-84, -180]], [[88, -290], [50, -392]]],
    umb: [[[-80, -250], [-84, -180]], [[96, -330], [74, -450]]],
    head: [[[-80, -250], [-84, -180]], [[100, -360], [52, -470]]],
    out: [[[-100, -290], [-150, -300]], [[100, -290], [150, -300]]],
    chest: [[[-80, -250], [-84, -180]], [[60, -250], [20, -285]]],
    press: [[[-60, -240], [60, -120]], [[10, -240], [70, -118]]],
  };
  function person(ctx, o) {
    const { x, y, s = 1, kind = 'tonico', exp = 'calm', arms = 'down', pale = 0, t = 0, sweat = 0, lie = 0, shake = 0 } = o;
    const R = 66, skin = mix('#F6D3AE', '#D3DFEA', pale);
    ctx.save(); ctx.translate(x + (shake ? U.noise1(t * 30, 4) * shake : 0), y); ctx.scale(s, s);
    if (lie) { ctx.translate(0, -62 * lie); ctx.rotate((-Math.PI / 2) * lie); }
    const sd = o.seed || (kind === 'nina' ? 200 : 100);
    // pernas
    const pant = kind === 'nina' ? skin : '#3B4A6B';
    G.limb(ctx, [[-26, -176], [-28, -90], [-30, -22]], { color: pant, lw: 34, seed: sd + 1 });
    G.limb(ctx, [[26, -176], [28, -90], [30, -22]], { color: pant, lw: 34, seed: sd + 2 });
    G.ellipse(ctx, -34, -6, 30, 14, { fill: '#F4F4F2', lw: 4, seed: sd + 3 }); G.ellipse(ctx, 34, -6, 30, 14, { fill: '#F4F4F2', lw: 4, seed: sd + 4 });
    // tronco
    if (kind === 'nina') G.poly(ctx, [[-52, -342], [52, -342], [92, -150], [-92, -150]], { fill: '#E8B04C', lw: 5, seed: sd + 5, hatch: HATCH });
    else G.rrect(ctx, -58, -345, 116, 185, 30, { fill: mix('#7FB1DE', '#C9D8E6', pale), lw: 5, seed: sd + 5, hatch: HATCH });
    // braços
    const A = ARMS[arms] || ARMS.down;
    A.forEach(([el, ha], i) => { const sx = i ? 58 : -58; G.limb(ctx, [[sx, -318], el, ha], { color: skin, lw: 26, seed: sd + 6 + i }); G.ellipse(ctx, ha[0], ha[1], 16, 16, { fill: skin, lw: 4, seed: sd + 8 + i }); });
    if (arms === 'hold') { G.rrect(ctx, 14, -168, 52, 66, 9, { fill: '#EDEDED', lw: 4, seed: sd + 12, hatch: HATCH }); G.ellipse(ctx, 40, -135, 14, 17, { fill: RED, lw: 2, seed: sd + 13, second: false }); }
    if (arms === 'phone') G.rrect(ctx, 38, -420, 24, 40, 5, { fill: '#2A2A2A', lw: 3.5, seed: sd + 14 });
    if (arms === 'umb') { ctx.save(); ctx.translate(74, -450); G.line(ctx, [[0, 0], [0, 120]], { lw: 5, seed: sd + 15 }); ctx.restore(); }
    // pescoço + cabeça
    G.rrect(ctx, -16, -372, 32, 36, 8, { fill: skin, lw: 4, seed: sd + 16 });
    ctx.save(); ctx.translate(0, -440);
    G.ellipse(ctx, 0, 0, R, R, { fill: skin, lw: 5.5, seed: sd + 17 });
    if (kind === 'tonico') {
      G.shape(ctx, Array.from({ length: 15 }, (_, i) => { const a = Math.PI + (i / 14) * Math.PI; return [Math.cos(a) * (R + 6), Math.sin(a) * (R * 0.8) - R * 0.28]; }), { fill: '#2F5D9E', lw: 5, seed: sd + 18, hatch: HATCH });
      G.ellipse(ctx, 0, -R * 1.1, 17, 17, { fill: '#F4F4F2', lw: 4, seed: sd + 19 });
      G.shape(ctx, [[-R * 0.38, R * 0.3], [0, R * 0.22], [R * 0.38, R * 0.3], [R * 0.3, R * 0.4], [0, R * 0.3], [-R * 0.3, R * 0.4]], { fill: INK, lw: 2, seed: sd + 20 });
    } else {
      G.shape(ctx, Array.from({ length: 15 }, (_, i) => { const a = Math.PI + (i / 14) * Math.PI; return [Math.cos(a) * (R + 4), Math.sin(a) * (R * 0.95) - R * 0.1]; }), { fill: '#3A2A25', lw: 5, seed: sd + 18, hatch: { color: 'rgba(255,255,255,0.15)', gap: 8 } });
      G.ellipse(ctx, -R * 0.55, -R * 1.05, 28, 28, { fill: '#3A2A25', lw: 5, seed: sd + 19 });
    }
    face(ctx, R, exp, t, sd + 40);
    if (kind === 'nina') for (const q of [-1, 1]) G.ellipse(ctx, q * R * 0.36, -R * 0.1, R * 0.3, R * 0.3, { fill: null, lw: 3.5, seed: sd + 50 + q, second: false });
    ctx.restore();
    if (sweat) drops(ctx, 0, -500, t, 3, sd, 1.2 * sweat);
    ctx.restore();
  }

  // ---------- órgãos com rosto ----------
  function heart(ctx, x, y, s, pulse, exp, t) {
    const pts = []; for (let i = 0; i < 40; i++) { const a = (i / 40) * Math.PI * 2; pts.push([16 * Math.pow(Math.sin(a), 3), -(13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a))]); }
    ctx.save(); ctx.translate(x, y); ctx.scale(s * (1 + 0.16 * pulse), s * (1 + 0.16 * pulse));
    G.shape(ctx, pts.map(([a, b]) => [a * 9, b * 9]), { fill: '#D8403A', lw: 6, seed: 300, hatch: { color: 'rgba(27,26,25,0.4)', gap: 8 } });
    G.line(ctx, [[-40, -135], [-20, -165], [-6, -150]], { lw: 5, seed: 301 }); G.line(ctx, [[20, -140], [36, -170], [58, -158]], { lw: 5, seed: 302 });
    ctx.translate(0, -30); face(ctx, 64, exp, t, 310); ctx.restore();
  }
  function brain(ctx, x, y, s, t, dark, exp) {
    const pts = []; for (let i = 0; i < 48; i++) { const a = (i / 48) * Math.PI * 2; const r = 1 + 0.07 * Math.sin(a * 9) + 0.03 * Math.sin(a * 5); pts.push([Math.cos(a) * 190 * r, Math.sin(a) * 140 * r]); }
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    G.shape(ctx, pts, { fill: mix('#EFEFEF', '#7E7E7E', dark * 0.7), lw: 6, seed: 400, hatch: { color: 'rgba(27,26,25,0.35)', gap: 8 } });
    for (const [a, b, c, d] of [[-120, -60, -40, -80], [30, -90, 110, -50], [-100, 40, -30, 70], [50, 60, 130, 30]]) G.line(ctx, [[a, b], [(a + c) / 2, (b + d) / 2 - 22], [c, d]], { lw: 3.5, seed: 401 + a, step: 18 });
    // rabiscos escuros crescendo pelo lado direito
    const n = Math.floor(dark * 90);
    for (let i = 0; i < n; i++) { const px = lerp(190, -60, hh(i, 1) * (0.4 + 0.6 * dark)) * 0.95, py = (hh(i, 2) - 0.5) * 230 * Math.sqrt(Math.max(0, 1 - Math.pow(px / 190, 2))); G.line(ctx, [[px, py], [px - 30 + hh(i, 3) * 20, py + 16], [px + 6, py + 30]], { lw: 3.2, seed: 500 + i, step: 100, color: INK }); }
    ctx.save(); ctx.translate(-55, 5); face(ctx, 78, exp, t, 420); ctx.restore();
    ctx.restore();
  }
  function bag(ctx, x, y, level, t, label) {
    const w = 170, h = 330;
    ctx.save(); ctx.translate(x, y);
    G.line(ctx, [[w / 2, -60], [w / 2, 0]], { lw: 5, seed: 600 }); G.rrect(ctx, w / 2 - 30, -78, 60, 26, 8, { fill: '#DDD', lw: 4, seed: 601 });
    ctx.save(); ctx.beginPath(); ctx.roundRect(0, 0, w, h, 34); ctx.clip();
    const top = h * (1 - level); ctx.fillStyle = RED; ctx.beginPath(); ctx.moveTo(0, top);
    for (let i = 0; i <= 20; i++) ctx.lineTo((i / 20) * w, top + Math.sin(i * 0.9 + t * 3) * 4); ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.fill();
    ctx.restore();
    G.rrect(ctx, 0, 0, w, h, 34, { fill: null, lw: 6, seed: 602, hatch: null });
    for (let i = 1; i < 5; i++) G.line(ctx, [[w - 38, h * i / 5], [w - 6, h * i / 5]], { lw: 3, seed: 610 + i });
    lab(ctx, label, w / 2, h + 70, 62, { align: 'center', color: RED });
    lab(ctx, 'SANGUE NO CORPO', w / 2, h + 112, 30, { align: 'center' });
    ctx.restore();
  }
  const bagLevel = (t) => (t < T(3) ? 1 : t < T(6) ? lerp(1, 0.85, ease.inOutQuad(clamp((t - T(3) - 1.2) / 5))) : t < T(9) ? lerp(0.85, 0.7, ease.inOutQuad(clamp((t - T(6) - 0.8) / 5))) : t < T(12) ? lerp(0.7, 0.58, ease.inOutQuad(clamp((t - T(9) - 0.8) / 5))) : lerp(0.58, 0.4, ease.inOutQuad(clamp((t - T(12)) / 8))));
  function pulseAt(t) { let p = 0; for (const b of S.beats) { if (b.t > t) break; const a = t - b.t; if (a < 0.5) p = Math.max(p, b.a * (Math.exp(-a * 11) + 0.55 * Math.exp(-Math.pow(a - 0.19, 2) * 600))); } return p; }
  function banner(ctx, t, t0, n, sub, pct) {
    const p = appear(t, t0 + 0.1);
    ctx.save(); ctx.globalAlpha = clamp(p); ctx.translate(0, (1 - clamp(p)) * -20);
    lab(ctx, 'ESTÁGIO ' + n, 90, 130, 92); G.line(ctx, [[90, 150], [420, 146], [640, 152]], { lw: 6, seed: 700 + n });
    lab(ctx, sub, 90, 210, 44, { color: '#555' });
    lab(ctx, pct, 90, 270, 54, { color: RED });
    ctx.restore();
  }
  const tag = (ctx, t, t0, s, x, y, tx, ty, size = 44, seed = 5, align = 'left') => {
    const p = clamp((t - t0) / 0.5); if (p <= 0) return;
    const ls = s.split('\n');
    ctx.save(); ctx.globalAlpha = p; ls.forEach((l, i) => lab(ctx, l, x, y + i * size * 1.05, size, { align })); ctx.restore();
    if (tx !== undefined) arrow(ctx, x, y + 12 + (ls.length - 1) * size * 1.05, tx, ty, ease.inOutQuad(clamp((t - t0 - 0.2) / 0.5)), seed);
  };

  // ---------- cenas ----------
  function rua(ctx, t) {
    // rua em perspectiva, como um desenho de caneta
    for (let k = 0; k < 9; k++) { const y0 = 30 + k * 108, y1 = lerp(y0, 470, 0.62); G.line(ctx, [[0, y0], [920, y1]], { lw: 3, seed: 800 + k, step: 60, alpha: 0.7 }); }
    G.line(ctx, [[0, 30], [920, 330], [920, 560], [0, 1000]], { lw: 5, seed: 810, step: 60 });
    for (let i = 0; i < 40; i++) { const a = hh(i, 5), b = hh(i, 6); const x = a * 880, y = lerp(40 + 8 * 108 * b, 400, a * 0.5) ; G.line(ctx, [[x, y], [x + 40, y - 18], [x + 18, y + 22]], { lw: 2.5, seed: 820 + i, step: 100, alpha: 0.5 }); }
    G.line(ctx, [[0, 1000], [920, 560], [1920, 560]], { lw: 5, seed: 811 });
    G.line(ctx, [[0, 1080], [1000, 700], [1920, 700]], { lw: 5, seed: 812 });
    // poste com luz azul
    const gl = ctx.createRadialGradient(1640, 230, 10, 1640, 400, 460); gl.addColorStop(0, 'rgba(120,170,230,0.55)'); gl.addColorStop(1, 'rgba(120,170,230,0)');
    ctx.fillStyle = gl; ctx.fillRect(1100, 0, 820, 900);
    G.rrect(ctx, 1840, 200, 16, 700, 4, { fill: '#999', lw: 5, seed: 830 }); G.shape(ctx, [[1860, 200], [1700, 190], [1650, 225], [1860, 232]], { fill: '#FFF', lw: 5, seed: 831 });
    // relógio redondo: 23:10
    G.ellipse(ctx, 1700, 100, 62, 62, { fill: INK, lw: 5, seed: 840 });
    lab(ctx, '23:10', 1700, 112, 40, { color: '#FFF', align: 'center' });
    lab(ctx, 'RUA DA NOITE', 1380, 60, 38, { align: 'center' });
    // poças e chuva
    for (const [px, py, pw] of [[1000, 860, 220], [1560, 940, 260], [1300, 1010, 200]]) G.ellipse(ctx, px, py, pw, pw * 0.1, { fill: '#BCD9F2', lw: 3, seed: px, hatch: null });
    ctx.save(); ctx.strokeStyle = 'rgba(100,150,210,0.7)'; ctx.lineWidth = 3;
    for (let i = 0; i < 90; i++) { const x = (hh(i, 1) * 2100 - 100 + t * 60) % 2000, y = (hh(i, 2) * 1100 + t * 900) % 1100; ctx.beginPath(); ctx.moveTo(x, y); ctx.lineTo(x - 8, y + 30); ctx.stroke(); }
    ctx.restore();
    // personagens
    const a = appear(t, 0.6, 0.6);
    ctx.save(); ctx.globalAlpha = clamp(a);
    person(ctx, { x: 1380, y: 900, s: 1.08, kind: 'tonico', exp: t < 4.5 ? 'calm' : 'worried', arms: 'hold', t, seed: 100 });
    person(ctx, { x: 1640, y: 930, s: 1.08, kind: 'nina', exp: 'scared', arms: 'umb', t, seed: 200 });
    // guarda-chuva sobre os dois
    G.shape(ctx, Array.from({ length: 17 }, (_, i) => { const a2 = Math.PI + (i / 16) * Math.PI; return [1560 + Math.cos(a2) * 230, 380 + Math.sin(a2) * 130]; }), { fill: '#7C8FB4', lw: 6, seed: 850, hatch: HATCH });
    ctx.restore();
    if (t > 3.8) { ctx.save(); ctx.globalAlpha = clamp((t - 3.8) / 0.5); G.rrect(ctx, 650, 590, 560, 130, 14, { fill: '#FFF', lw: 4, seed: 860 }); lab(ctx, 'um corte fundo na perna...', 930, 650, 48, { align: 'center' }); lab(ctx, 'e muito sangue perdido.', 930, 702, 48, { align: 'center', color: RED }); ctx.restore(); }
    if (t < 3) { ctx.save(); ctx.globalAlpha = clamp((t - 0.4) / 0.5) * (1 - clamp((t - 2.9) / 0.1)); ctx.restore(); }
    // título
    const tt = clamp((t - 0.3) / 0.6) * (1 - clamp((t - 3.4) / 0.5));
    if (tt > 0) { ctx.save(); ctx.globalAlpha = tt; ctx.fillStyle = 'rgba(250,250,247,0.9)'; ctx.fillRect(60, 80, 820, 230); lab(ctx, 'O QUE O CORPO SENTE', 100, 190, 84); lab(ctx, 'QUANDO PERDE MUITO SANGUE', 100, 280, 64, { color: RED }); ctx.restore(); }
  }
  function est1(ctx, t, t0) {
    banner(ctx, t, t0, 1, 'o corpo compensa', 'perda de até 15%');
    bag(ctx, 1560, 330, bagLevel(t), t, '−15%');
    heart(ctx, 1000, 640, 1.9, pulseAt(t), 'worried', t);
    person(ctx, { x: 420, y: 960, s: 1.3, kind: 'tonico', exp: 'calm', arms: 'chest', t });
    tag(ctx, t, t0 + 2.2, 'BATIMENTO\nACELERADO!', 1250, 380, 1170, 540, 52);
    tag(ctx, t, t0 + 5, 'quase nenhum\nsintoma', 140, 520, 290, 660, 44, 7);
  }
  function est2(ctx, t, t0) {
    banner(ctx, t, t0, 2, 'o corpo manda sangue só para o essencial', 'perda de 15% a 30%');
    bag(ctx, 1600, 330, bagLevel(t), t, '−30%');
    heart(ctx, 1100, 760, 1.5, pulseAt(t), 'scared', t);
    person(ctx, { x: 520, y: 1000, s: 1.4, kind: 'tonico', exp: 'worried', arms: 'chest', pale: clamp((t - t0) / 6) * 0.9, sweat: 1, shake: 3, t });
    tag(ctx, t, t0 + 1.6, 'PELE FRIA\nE PÁLIDA', 130, 470, 340, 700, 46, 5);
    tag(ctx, t, t0 + 3.4, 'SEDE', 880, 470, 840, 580, 54, 8, 'center');
    tag(ctx, t, t0 + 4.8, 'CORAÇÃO\nNO LIMITE!', 1210, 420, 1150, 590, 46, 9, 'center');
  }
  function est3(ctx, t, t0) {
    banner(ctx, t, t0, 3, 'o cérebro começa a falhar', 'perda de 30% a 40%');
    bag(ctx, 1600, 330, bagLevel(t), t, '−40%');
    for (let i = 0; i < 3; i++) spiral(ctx, 430 + i * 130 - (i % 2) * 40, 330 + (i % 2) * 40, 34 + i * 6, t, 900 + i, t * 3 + i);
    brain(ctx, 740, 690, 1.35, t, clamp((t - t0) / 8) * 0.35, 'scared');
    lab(ctx, 'O', 1080, 290, 70); lab(ctx, '2', 1120, 308, 40);
    const x = appear(t, t0 + 1.8); ctx.save(); ctx.globalAlpha = clamp(x); G.line(ctx, [[1055, 230], [1150, 320]], { lw: 8, seed: 905, color: BLUE }); G.line(ctx, [[1150, 230], [1055, 320]], { lw: 8, seed: 906, color: BLUE }); ctx.restore();
    tag(ctx, t, t0 + 2.2, 'FALTA DE OXIGÊNIO\nNO CÉREBRO', 1000, 400, 880, 560, 44, 6);
    person(ctx, { x: 1340, y: 1030, s: 0.8, kind: 'tonico', exp: 'dizzy', arms: 'head', pale: 0.9, sweat: 1, shake: 3, t });
    tag(ctx, t, t0 + 5, 'TONTURA E\nCONFUSÃO', 1340, 500, undefined, undefined, 44, 3, 'center');
  }
  function est4(ctx, t, t0) {
    banner(ctx, t, t0, 4, 'o corpo desliga o que não é vital', 'perda de mais de 40%');
    bag(ctx, 1600, 330, bagLevel(t), t, '>40%');
    brain(ctx, 700, 690, 1.5, t, clamp(0.35 + (t - t0) / 7.5 * 0.65), 'faint');
    const icons = [['VISÃO', 330], ['FALA', 480], ['EQUILÍBRIO', 630]];
    icons.forEach(([nm, y], i) => {
      const p = appear(t, t0 + 1.2 + i * 1.3); if (p <= 0) return;
      ctx.save(); ctx.globalAlpha = clamp(p); ctx.translate(1180, y);
      G.rrect(ctx, 0, 0, 120, 120, 22, { fill: '#555', lw: 5, seed: 950 + i, hatch: { color: 'rgba(255,255,255,0.18)', gap: 8 } });
      if (i === 0) { G.ellipse(ctx, 60, 60, 38, 22, { fill: '#FFF', lw: 4, seed: 960 }); G.ellipse(ctx, 60, 60, 11, 11, { fill: INK, lw: 2, seed: 961 }); }
      if (i === 1) { G.rrect(ctx, 22, 28, 78, 52, 14, { fill: '#FFF', lw: 4, seed: 962 }); G.line(ctx, [[40, 82], [34, 100], [56, 82]], { lw: 4, seed: 963 }); }
      if (i === 2) { G.limb(ctx, [[60, 20], [56, 62], [76, 100]], { color: '#FFF', lw: 16, seed: 964 }); }
      G.line(ctx, [[0, 0], [120, 120]], { lw: 7, seed: 965, color: BLUE }); G.line(ctx, [[120, 0], [0, 120]], { lw: 7, seed: 966, color: BLUE });
      lab(ctx, nm, 150, 76, 46);
      ctx.restore();
    });
    const lie = ease.inOutQuad(clamp((t - t0 - 0.3) / 1.4));
    person(ctx, { x: 1560, y: 1050, s: 0.62, kind: 'tonico', exp: lie > 0.3 ? 'faint' : 'dizzy', arms: 'down', pale: 1, lie, t });
    tag(ctx, t, t0 + 4.4, 'PERDA DE CONSCIÊNCIA', 1400, 930, undefined, undefined, 42, 4, 'center');
  }
  function ajuda(ctx, t, t0) {
    const p = appear(t, t0 + 0.3);
    lab(ctx, 'MAS DÁ PARA AGIR!', 960, 140, 96, { align: 'center', color: '#2E7D4F' });
    G.line(ctx, [[540, 170], [960, 164], [1380, 172]], { lw: 6, seed: 970, color: '#2E7D4F' });
    heart(ctx, 1640, 380, 0.85, pulseAt2(t), 'happy', t);
    const steps = [['1', 'LIGUE 192', 'SAMU — peça ajuda já'], ['2', 'PRESSIONE FIRME', 'com um pano limpo, sem parar'], ['3', 'NÃO TIRE O PANO', 'ponha outro por cima e deite a pessoa']];
    steps.forEach(([n, a, b], i) => {
      const q = appear(t, t0 + 1.2 + i * 2.3); if (q <= 0) return;
      ctx.save(); ctx.globalAlpha = clamp(q); ctx.translate(120, 280 + i * 190);
      G.ellipse(ctx, 50, 50, 50, 50, { fill: '#2E7D4F', lw: 5, seed: 980 + i });
      lab(ctx, n, 50, 76, 76, { color: '#FFF', align: 'center' });
      lab(ctx, a, 140, 54, 66); lab(ctx, b, 140, 108, 42, { color: '#555' });
      ctx.restore();
    });
    // Nina pressiona o ferimento de Tonico deitado
    person(ctx, { x: 1780, y: 1050, s: 0.9, kind: 'tonico', exp: 'calm', arms: 'down', pale: 0.4, lie: 1, t });
    person(ctx, { x: 1450, y: 1040, s: 0.95, kind: 'nina', exp: 'worried', arms: 'press', t });
    // telefone
    const ring = Math.sin(t * 22) * (t > t0 + 1.2 && t < t0 + 3.4 ? 4 : 0);
    ctx.save(); ctx.translate(1000, 300); ctx.rotate(ring * Math.PI / 180); G.rrect(ctx, 0, 0, 110, 190, 18, { fill: '#2A2A2A', lw: 5, seed: 990 }); lab(ctx, '192', 55, 110, 46, { color: '#FFF', align: 'center' }); ctx.restore();
  }
  function pulseAt2(t) { let p = 0; for (const b of S.calm) { if (b.t > t) break; const a = t - b.t; if (a < 0.5) p = Math.max(p, Math.exp(-a * 11) + 0.55 * Math.exp(-Math.pow(a - 0.19, 2) * 600)); } return p * 0.8; }
  function fim(ctx, t) {
    ctx.save(); ctx.fillStyle = 'rgba(250,250,247,1)'; ctx.fillRect(0, 0, 1920, 1080); ctx.restore();
    lab(ctx, 'SANGRAMENTO GRAVE', 960, 460, 120, { align: 'center' });
    lab(ctx, 'É EMERGÊNCIA.', 960, 590, 120, { align: 'center', color: RED });
    lab(ctx, 'LIGUE 192', 960, 740, 90, { align: 'center', color: '#2E7D4F' });
    lab(ctx, 'prévia de 1 minuto · conteúdo educativo', 960, 860, 38, { align: 'center', color: '#666' });
  }

  Studio.film({
    draw(ctx, t) {
      ctx.save(); ctx.scale(G.W / 1920, G.H / 1080);
      ctx.fillStyle = '#FAFAF7'; ctx.fillRect(0, 0, 1920, 1080);
      const sc = S.S;
      if (t < sc.e1[0]) rua(ctx, t);
      else if (t < sc.e2[0]) est1(ctx, t, sc.e1[0]);
      else if (t < sc.e3[0]) est2(ctx, t, sc.e2[0]);
      else if (t < sc.e4[0]) est3(ctx, t, sc.e3[0]);
      else if (t < ev.cut) est4(ctx, t, sc.e4[0]);
      else if (t < sc.fim[0]) ajuda(ctx, t, sc.ajuda[0]);
      else { ajuda(ctx, sc.fim[0] - 0.01, sc.ajuda[0]); fim(ctx, t); }
      // viradas de página (branco) no início das etapas
      for (const k of ['e1', 'e2', 'e3', 'e4']) { const u = (t - sc[k][0]) / 0.35; if (u >= 0 && u < 1) { ctx.fillStyle = `rgba(250,250,247,${1 - u})`; ctx.fillRect(0, 0, 1920, 1080); } }
      ctx.restore();
      // etapa 4 escurece até o preto; depois um clarão branco no corte (sincronizado com o som)
      if (t >= ev.dark && t < ev.cut) { ctx.fillStyle = `rgba(0,0,0,${ease.inQuad(clamp((t - ev.dark) / (ev.cut - ev.dark - 0.05)))})`; ctx.fillRect(0, 0, G.W, G.H); }
      const fl = t >= ev.cut ? Math.exp(-(t - ev.cut) * 7) : 0; if (fl > 0.02) { ctx.fillStyle = `rgba(255,255,255,${fl})`; ctx.fillRect(0, 0, G.W, G.H); }
      if (t < 0.3) { ctx.fillStyle = `rgba(250,250,247,${1 - t / 0.3})`; ctx.fillRect(0, 0, G.W, G.H); }
    },
    post: { paper: 0.25, vignette: 0.2, grain: 0.07 },
  });
})();
