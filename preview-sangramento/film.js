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

  // ---------- ferramentas de caneta: hachura cruzada recortada na forma ----------
  function xhatch(ctx, poly, o = {}) {
    const { gap = 12, angles = [0.8, -0.8], color = INK, alpha = 0.6, lw = 1.5, seed = 1, jit = 2.2, poly2 = null } = o;
    let x0 = 1e9, y0 = 1e9, x1 = -1e9, y1 = -1e9; for (const [x, y] of poly) { x0 = Math.min(x0, x); y0 = Math.min(y0, y); x1 = Math.max(x1, x); y1 = Math.max(y1, y); }
    const cx = (x0 + x1) / 2, cy = (y0 + y1) / 2, R = Math.hypot(x1 - x0, y1 - y0) / 2 + 4;
    ctx.save(); ctx.beginPath(); poly.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.clip();
    if (poly2) { ctx.beginPath(); poly2.forEach(([x, y], i) => (i ? ctx.lineTo(x, y) : ctx.moveTo(x, y))); ctx.closePath(); ctx.clip(); }
    ctx.strokeStyle = color; ctx.globalAlpha = alpha; ctx.lineWidth = lw; ctx.lineCap = 'round';
    angles.forEach((ang, ai) => {
      const dx = Math.cos(ang), dy = Math.sin(ang), nx = -dy, ny = dx;
      let i = 0;
      for (let d = -R; d < R; d += gap, i++) {
        const j = (hh(seed + ai * 7, i, G.boil) - 0.5) * jit, j2 = (hh(seed + ai * 7 + 3, i, G.boil) - 0.5) * jit * 2;
        const sx = cx + nx * (d + j) - dx * R, sy = cy + ny * (d + j) - dy * R;
        const cut = 0.25 + hh(seed + 11, i + ai * 50) * 0.5;
        ctx.beginPath(); ctx.moveTo(sx, sy); ctx.lineTo(sx + dx * R * 2 * cut + j2, sy + dy * R * 2 * cut + j2);
        ctx.moveTo(sx + dx * R * 2 * (cut + 0.04), sy + dy * R * 2 * (cut + 0.04)); ctx.lineTo(sx + dx * R * 2, sy + dy * R * 2); ctx.stroke();
      }
    });
    ctx.restore();
  }
  const ell = (cx, cy, rx, ry, n = 36) => Array.from({ length: n }, (_, i) => { const a = (i / n) * Math.PI * 2; return [cx + Math.cos(a) * rx, cy + Math.sin(a) * ry]; });
  const sk = (ctx, pts, lw = 3, seed = 1, color = INK) => G.line(ctx, pts, { lw, seed, step: 16, amp: 1.2, color });

  // ---------- rosto: olhos tristes, pálpebras pesadas, sobrancelhas ----------
  function face(ctx, R, exp, t, seed) {
    const lid = { calm: 0.32, worried: 0.42, dizzy: 0.2, scared: 0, faint: 1, happy: 0 }[exp] ?? 0.3;
    for (const sd of [-1, 1]) {
      const ex = sd * R * 0.3, ey = -R * 0.02, er = R * (exp === 'scared' ? 0.25 : 0.21);
      if (exp === 'faint') { sk(ctx, [[ex - er, ey], [ex, ey + 7], [ex + er, ey]], 3.2, seed + sd); continue; }
      if (exp === 'happy') { sk(ctx, [[ex - er, ey + 6], [ex, ey - er * 0.8], [ex + er, ey + 6]], 3.8, seed + sd); continue; }
      G.ellipse(ctx, ex, ey, er, er * 1.08, { fill: '#FFFFFF', lw: 2.8, seed: seed + sd, second: false });
      if (exp === 'dizzy') { spiral(ctx, ex, ey, er * 0.85, t, seed + sd, t * 6 * sd); continue; }
      G.ellipse(ctx, ex - er * 0.12, ey + er * 0.38, er * 0.5, er * 0.52, { fill: INK, lw: 1, seed: seed + 9 + sd, second: false });
      G.ellipse(ctx, ex - er * 0.24, ey + er * 0.24, er * 0.14, er * 0.14, { fill: '#FFFFFF', lw: 0, seed: seed + 11 + sd, second: false });
      if (lid) {
        // pálpebra caída: arco que cobre o topo do olho
        const ly = ey - er * 1.08 + er * 2.16 * lid * 0.75;
        ctx.save(); ctx.beginPath(); ctx.ellipse(ex, ey, er, er * 1.08, 0, 0, Math.PI * 2); ctx.clip();
        ctx.fillStyle = '#FFFFFF'; ctx.beginPath(); ctx.moveTo(ex - er * 1.2, ey - er * 1.3); ctx.lineTo(ex + er * 1.2, ey - er * 1.3); ctx.lineTo(ex + er * 1.2, ly - 2); ctx.quadraticCurveTo(ex, ly + er * 0.35, ex - er * 1.2, ly - 2); ctx.closePath(); ctx.fill();
        ctx.restore();
        G.line(ctx, [[ex - er * 1.05, ly + 1], [ex - er * 0.4, ly + er * 0.22], [ex + er * 0.4, ly + er * 0.22], [ex + er * 1.05, ly + 1]], { lw: 2.4, seed: seed + 15 + sd, step: 30 });
      }
    }
    // sobrancelhas tristes: a ponta de dentro sobe
    const up = exp === 'happy' ? 0 : exp === 'scared' ? 0.12 : 0.08;
    for (const sd of [-1, 1]) G.line(ctx, [[sd * R * 0.52, -R * 0.36], [sd * R * 0.36, -R * 0.47], [sd * R * 0.18, -R * (0.5 + up)], [sd * R * 0.1, -R * (0.5 + up * 1.4)]], { lw: 2.8, seed: seed + 20 + sd, step: 30 });
    sk(ctx, [[R * 0.04, R * 0.12], [-R * 0.06, R * 0.2], [R * 0.02, R * 0.28]], 2.4, seed + 27); // nariz
    const my = R * 0.5;
    if (exp === 'scared') G.ellipse(ctx, 0, my, R * 0.13, R * 0.17, { fill: '#9A9A9A', lw: 2.8, seed: seed + 30, second: false });
    else if (exp === 'faint') G.ellipse(ctx, 0, my, R * 0.09, R * 0.06, { fill: '#9A9A9A', lw: 2.8, seed: seed + 32, second: false });
    else if (exp === 'happy') sk(ctx, [[-R * 0.3, my - 8], [0, my + 10], [R * 0.3, my - 8]], 3.6, seed + 33);
    else sk(ctx, [[-R * 0.13, my + 3], [0, my - 2], [R * 0.13, my + 3]], 2.8, seed + 34); // boquinha triste
  }

  // ---------- pessoas: traço fino, cabeça grande, boné/touca azul hachurado ----------
  const ARMS = {
    down: [[[-80, -250], [-84, -180]], [[80, -250], [84, -180]]],
    hold: [[[-80, -250], [-84, -180]], [[70, -230], [36, -135]]],
    phone: [[[-80, -250], [-84, -180]], [[88, -290], [50, -392]]],
    umb: [[[-80, -250], [-84, -180]], [[96, -330], [74, -450]]],
    head: [[[-80, -250], [-84, -180]], [[100, -360], [52, -470]]],
    out: [[[-100, -290], [-150, -300]], [[100, -290], [150, -300]]],
    chest: [[[-80, -250], [-84, -180]], [[60, -250], [20, -285]]],
    press: [[[-60, -240], [60, -120]], [[10, -240], [70, -118]]],
    raise: [[[-80, -250], [-84, -180]], [[110, -380], [150, -480]]],
    belly: [[[-80, -270], [-24, -232]], [[80, -270], [24, -226]]],
  };
  function hand(ctx, x, y, seed, dir = 1) {
    G.ellipse(ctx, x, y, 11, 13, { fill: '#FFFFFF', lw: 2.8, seed, second: false });
    for (let i = 0; i < 4; i++) { const fx = x + (i - 1.5) * 6.5 * dir; G.limb(ctx, [[fx, y + 6], [fx + (i - 1.5) * 2, y + 22]], { color: '#FFFFFF', lw: 6, seed: seed + i, outline: 2.4 }); }
  }
  function shoe(ctx, x, y, dir, seed) {
    const P = [[x - 16 * dir, y - 20], [x + 8 * dir, y - 22], [x + 30 * dir, y - 12], [x + 34 * dir, y - 2], [x - 18 * dir, y - 2]];
    G.shape(ctx, P, { fill: '#FFFFFF', lw: 3.2, seed });
    sk(ctx, [[x - 18 * dir, y - 6], [x + 34 * dir, y - 6]], 2.2, seed + 1);
    for (let k = 0; k < 3; k++) sk(ctx, [[x + (k * 7 - 4) * dir, y - 20], [x + (k * 7) * dir, y - 14]], 2, seed + 2 + k);
  }
  function person(ctx, o) {
    const { x, y, s = 1, kind = 'tonico', exp = 'calm', arms = 'down', pale = 0, t = 0, sweat = 0, lie = 0, shake = 0 } = o;
    const R = 70, sd = o.seed || (kind === 'nina' ? 200 : 100);
    const walking = o.walk !== undefined && !lie;
    const ph = walking ? o.walk * Math.PI * 2 : 0, sw = Math.sin(ph);
    ctx.save(); ctx.translate(x + (shake ? U.noise1(t * 30, 4) * shake : 0), y - (walking ? Math.abs(Math.sin(ph)) * 6 : 0)); ctx.scale(s, s);
    if (lie) { ctx.translate(0, -50 * lie); ctx.rotate((-Math.PI / 2) * lie); }
    // sombra rabiscada no chão
    if (!lie) for (let k = 0; k < 6; k++) sk(ctx, [[-50 + k * 4, 2 + k * 1.5], [50 - k * 6, 2 + k * 1.5]], 1.8, sd + 90 + k);
    // pernas bem finas
    const legs = walking
      ? [[[-10, -180], [-10 + sw * 16, -96], [sw * 40 - 6, -22 - Math.max(0, Math.cos(ph)) * 12]], [[10, -180], [10 - sw * 16, -96], [-sw * 40 + 6, -22 - Math.max(0, -Math.cos(ph)) * 12]]]
      : [[[-12, -180], [-14, -96], [-18, -22]], [[12, -180], [14, -96], [18, -22]]];
    const pant = kind === 'nina' ? '#FFFFFF' : '#FFFFFF';
    legs.forEach((L, i) => { G.limb(ctx, L, { color: pant, lw: 12, seed: sd + 1 + i, outline: 2.8 }); shoe(ctx, L[2][0] - 4, L[2][1] + 20, kind === 'nina' ? (i ? 1 : -1) : 1, sd + 3 + i * 5); });
    if (walking) { for (const q of [0, 1]) sk(ctx, [[60 + q * 10, -60 + q * 14], [66 + q * 10, -44 + q * 14], [60 + q * 10, -30 + q * 14]], 2.2, sd + 70 + q); }
    // tronco fino
    const tr = kind === 'nina' ? [[-30, -350], [30, -350], [62, -165], [-62, -165]] : [[-28, -350], [28, -350], [30, -176], [-30, -176]];
    G.poly(ctx, tr, { fill: '#FFFFFF', lw: 3, seed: sd + 5 });
    xhatch(ctx, tr, { gap: 8, angles: kind === 'nina' ? [0.8, -0.8] : [0.9], alpha: 0.35, seed: sd + 61, lw: 1.2, poly2: [[6, -360], [80, -360], [80, -150], [10, -150]] });
    // braços finos com mãos de 4 dedos
    const A = ARMS[arms] || ARMS.down;
    A.forEach(([el, ha], i) => { const sx = i ? 26 : -26; const sw2 = walking && arms === 'down' ? (i ? -sw : sw) * 14 : 0; const H2 = [ha[0] * 0.75 + sw2, ha[1] + 10]; G.limb(ctx, [[sx, -335], [el[0] * 0.62 + sw2 * 0.5, el[1] + 4], H2], { color: '#FFFFFF', lw: 11, seed: sd + 6 + i, outline: 2.6 }); hand(ctx, H2[0], H2[1] + 8, sd + 8 + i * 4, i ? 1 : -1); });
    if (walking) sk(ctx, [[-50, -330], [-56, -312], [-50, -296]], 2.2, sd + 75);
    if (arms === 'hold') { G.rrect(ctx, 6, -168, 46, 60, 8, { fill: '#F3F3F3', lw: 3, seed: sd + 12 }); G.ellipse(ctx, 29, -138, 13, 16, { fill: RED, lw: 2, seed: sd + 13, second: false }); xhatch(ctx, ell(29, -138, 13, 16), { gap: 4, angles: [0.8], alpha: 0.6, seed: 9, lw: 1.2 }); }
    if (arms === 'phone') G.rrect(ctx, 30, -420, 24, 40, 5, { fill: '#2A2A2A', lw: 3.5, seed: sd + 14 });
    if (arms === 'umb') sk(ctx, [[56, -450], [56, -330]], 3.5, sd + 15);
    // pescoço fino
    sk(ctx, [[-7, -372], [-7, -346]], 2.6, sd + 16); sk(ctx, [[7, -372], [7, -346]], 2.6, sd + 17);
    // cabeça grande
    ctx.save(); ctx.translate(0, -440);
    G.ellipse(ctx, 0, 0, R, R, { fill: '#FFFFFF', lw: 3.6, seed: sd + 17 });
    xhatch(ctx, ell(0, 0, R, R, 30), { gap: 6 - 2 * pale, angles: [0.9, -0.5], alpha: 0.2 + 0.4 * pale, seed: sd + 62, lw: 1.1, poly2: [[18, -R], [R + 4, -R], [R + 4, R], [-20, R + 4]] });
    ctx.save(); ctx.translate(kind === 'tonico' ? -R * 0.1 : 0, kind === 'tonico' ? R * 0.2 : R * 0.08);
    face(ctx, R, exp, t, sd + 40);
    ctx.restore();
    if (kind === 'tonico') {
      ctx.save(); ctx.translate(0, -R * 0.14);
      // boné azul com aba para o lado
      const dome = Array.from({ length: 17 }, (_, i) => { const a = Math.PI * 1.04 + (i / 16) * Math.PI * 0.98; return [Math.cos(a) * (R + 5) + 4, Math.sin(a) * (R * 0.78) - R * 0.3]; });
      G.shape(ctx, dome, { fill: '#2F63C8', lw: 3.6, seed: sd + 18 });
      xhatch(ctx, dome, { gap: 5, angles: [0.8, -0.8], color: '#102A66', alpha: 0.5, seed: sd + 63, lw: 1.2, poly2: [[0, -R * 2], [R * 2, -R * 2], [R * 2, 0], [-10, 0]] });
      const brim = [[-R * 0.25, -R * 0.36], [-R * 1.15, -R * 0.42], [-R * 1.32, -R * 0.28], [-R * 1.05, -R * 0.2], [-R * 0.2, -R * 0.26]];
      G.shape(ctx, brim, { fill: '#2F63C8', lw: 3.4, seed: sd + 21 });
      xhatch(ctx, brim, { gap: 5, angles: [0.6], color: '#102A66', alpha: 0.6, seed: sd + 64, lw: 1.2 });
      sk(ctx, [[4, -R * 1.08], [-R * 0.3, -R * 0.38]], 2.2, sd + 22); sk(ctx, [[4, -R * 1.08], [R * 0.5, -R * 0.42]], 2.2, sd + 23);
      G.ellipse(ctx, 4, -R * 1.08, 7, 5, { fill: '#2F63C8', lw: 2.5, seed: sd + 24 });
      sk(ctx, [[-R * 0.05, -R * 0.66], [R * 0.08, -R * 0.72], [R * 0.2, -R * 0.64]], 2.4, sd + 25, '#FFFFFF');
      ctx.restore();
    } else {
      const hair = Array.from({ length: 15 }, (_, i) => { const a = Math.PI + (i / 14) * Math.PI; return [Math.cos(a) * (R + 4), Math.sin(a) * (R * 0.95) - R * 0.1]; });
      G.shape(ctx, hair, { fill: '#FFFFFF', lw: 3.6, seed: sd + 18 });
      xhatch(ctx, hair, { gap: 4, angles: [1.0, -1.0], alpha: 0.8, seed: sd + 64, lw: 1.3 });
      G.ellipse(ctx, -R * 0.55, -R * 1.05, 26, 26, { fill: '#FFFFFF', lw: 3.6, seed: sd + 19 }); xhatch(ctx, ell(-R * 0.55, -R * 1.05, 26, 26), { gap: 4, angles: [1.0, -1.0], alpha: 0.8, seed: sd + 65, lw: 1.3 });
      for (const q of [-1, 1]) G.ellipse(ctx, q * R * 0.36, -R * 0.05, R * 0.27, R * 0.27, { fill: null, lw: 2.8, seed: sd + 50 + q, second: false });
    }
    ctx.restore();
    if (sweat) drops(ctx, 0, -520, t, 3, sd, 1.2 * sweat);
    ctx.restore();
  }

  // ---------- órgãos: tinta, hachura e rosto ----------
  function heart(ctx, x, y, s, pulse, exp, t) {
    const pts = []; for (let i = 0; i < 40; i++) { const a = (i / 40) * Math.PI * 2; pts.push([16 * Math.pow(Math.sin(a), 3), -(13 * Math.cos(a) - 5 * Math.cos(2 * a) - 2 * Math.cos(3 * a) - Math.cos(4 * a))]); }
    ctx.save(); ctx.translate(x, y); ctx.scale(s * (1 + 0.16 * pulse), s * (1 + 0.16 * pulse));
    const P = pts.map(([a, b]) => [a * 9, b * 9]);
    // vasos no topo
    G.limb(ctx, [[-44, -110], [-50, -150], [-46, -178]], { color: '#7FA8D8', lw: 22, seed: 301, outline: 4 });
    G.limb(ctx, [[14, -112], [10, -168], [52, -196], [96, -170], [104, -128]], { color: '#B3302C', lw: 30, seed: 302, outline: 4 });
    G.shape(ctx, P, { fill: '#C9302C', lw: 5, seed: 300 });
    xhatch(ctx, P, { gap: 7, angles: [0.8, -0.9], alpha: 0.5, seed: 70, lw: 1.5, poly2: [[-10, -200], [180, -200], [180, 160], [-80, 160]] });
    G.ellipse(ctx, -70, -48, 26, 14, { fill: '#F4D6D2', lw: 0, seed: 305, second: false }); // brilho
    ctx.translate(0, -30); face(ctx, 64, exp, t, 310); ctx.restore();
  }
  function brain(ctx, x, y, s, t, dark, exp) {
    const pts = []; for (let i = 0; i < 56; i++) { const a = (i / 56) * Math.PI * 2; const r = 1 + 0.06 * Math.sin(a * 9) + 0.03 * Math.sin(a * 5); pts.push([Math.cos(a) * 190 * r, Math.sin(a) * 140 * r]); }
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    G.shape(ctx, pts, { fill: '#F1F1F1', lw: 5, seed: 400 });
    xhatch(ctx, pts, { gap: 9, angles: [0.8, -0.8], alpha: 0.45, seed: 71, lw: 1.4, poly2: [[20, -170], [220, -170], [220, 170], [-60, 170]] });
    for (let k = 0; k < 30; k++) { const a = hh(k, 1) * 6.28, r = 30 + hh(k, 2) * 120, px = Math.cos(a) * r * 1.2, py = Math.sin(a) * r * 0.85; sk(ctx, [[px - 30, py], [px - 10, py - 18], [px + 12, py - 4], [px + 34, py - 16]], 3, 401 + k); }
    const n = Math.floor(dark * 110);
    for (let i = 0; i < n; i++) { const px = lerp(190, -70, hh(i, 1) * (0.4 + 0.6 * dark)) * 0.95, py = (hh(i, 2) - 0.5) * 240 * Math.sqrt(Math.max(0, 1 - Math.pow(px / 190, 2))); sk(ctx, [[px, py], [px - 34 + hh(i, 3) * 24, py + 18], [px + 6, py + 34]], 3, 500 + i); }
    ctx.save(); ctx.translate(-55, 5); face(ctx, 78, exp, t, 420); ctx.restore();
    ctx.restore();
  }
  function bag(ctx, x, y, level, t, label) {
    const w = 170, h = 330;
    ctx.save(); ctx.translate(x, y);
    sk(ctx, [[w / 2, -60], [w / 2, 0]], 4, 600); G.rrect(ctx, w / 2 - 30, -78, 60, 26, 8, { fill: '#E6E6E6', lw: 3.5, seed: 601 });
    ctx.save(); ctx.beginPath(); ctx.roundRect(0, 0, w, h, 34); ctx.clip();
    const top = h * (1 - level); ctx.fillStyle = RED; ctx.beginPath(); ctx.moveTo(0, top);
    for (let i = 0; i <= 20; i++) ctx.lineTo((i / 20) * w, top + Math.sin(i * 0.9 + t * 3) * 4); ctx.lineTo(w, h); ctx.lineTo(0, h); ctx.fill();
    ctx.restore();
    xhatch(ctx, [[0, top], [w, top], [w, h], [0, h]], { gap: 8, angles: [0.8], alpha: 0.4, seed: 72, lw: 1.3, poly2: ell(w / 2, h / 2, w / 2, h / 2, 24) });
    G.rrect(ctx, 0, 0, w, h, 34, { fill: null, lw: 5, seed: 602, hatch: null });
    for (let i = 1; i < 5; i++) sk(ctx, [[w - 38, h * i / 5], [w - 6, h * i / 5]], 2.5, 610 + i);
    lab(ctx, label, w / 2, h + 70, 62, { align: 'center', color: RED });
    lab(ctx, 'SANGUE NO CORPO', w / 2, h + 112, 30, { align: 'center' });
    ctx.restore();
  }
  function pulse(list, t, k = 1) { let p = 0; for (const b of list) { if (b.t > t) break; const a = t - b.t; if (a < 0.5) p = Math.max(p, b.a * (Math.exp(-a * 11) + 0.55 * Math.exp(-Math.pow(a - 0.19, 2) * 600))); } return p * k; }
  const tag = (ctx, t, t0, s, x, y, tx, ty, size = 44, seed = 5, align = 'left', color = INK) => {
    const p = clamp((t - t0) / 0.4); if (p <= 0) return;
    const ls = s.split('\n');
    ctx.save(); ctx.globalAlpha = p; ls.forEach((l, i) => lab(ctx, l, x, y + i * size * 1.05, size, { align, color })); ctx.restore();
    if (tx !== undefined) arrow(ctx, x, y + 12 + (ls.length - 1) * size * 1.05, tx, ty, ease.inOutQuad(clamp((t - t0 - 0.15) / 0.5)), seed);
  };
  // ---------- marcas de nanquim: respingos, "#" rabiscados, linhas de tremor, balão espetado ----------
  function splat(ctx, n, seed, x0, y0, x1, y1) {
    for (let i = 0; i < n; i++) { const r = 2 + Math.pow(hh(seed, i), 3) * 11; G.ellipse(ctx, lerp(x0, x1, hh(seed + 1, i)), lerp(y0, y1, hh(seed + 2, i)), r, r * (0.8 + hh(seed + 3, i) * 0.4), { fill: INK, lw: 0.5, seed: seed + i, second: false }); }
  }
  function hashMark(ctx, x, y, r, seed) {
    for (let i = 0; i < 4; i++) { const a = (i % 2 ? 0.9 : -0.6) + (hh(seed, i) - 0.5) * 0.4, o = (i < 2 ? -1 : 1) * r * 0.25; sk(ctx, [[x - Math.cos(a) * r + o, y - Math.sin(a) * r], [x + Math.cos(a) * r + o, y + Math.sin(a) * r]], 2.2, seed + i); }
  }
  function shakeLines(ctx, x, y, h, seed, side = 1) { for (let i = 0; i < 3; i++) sk(ctx, [[x + side * i * 12, y + i * 10], [x + side * (i * 12 + 8), y + h / 2 + i * 10], [x + side * i * 12, y + h + i * 10]], 2.2, seed + i); }
  function spiky(ctx, cx, cy, rx, ry, tx, ty, seed) {
    const P = []; for (let i = 0; i < 26; i++) { const a = (i / 26) * Math.PI * 2, k = i % 2 ? 1 : 0.8 + hh(seed, i) * 0.06; P.push([cx + Math.cos(a) * rx * k, cy + Math.sin(a) * ry * k]); }
    G.shape(ctx, P, { fill: '#FFFFFF', lw: 4.5, seed });
    const bx = cx - rx * 0.35, by = cy + ry * 0.75;
    G.shape(ctx, [[bx - 26, by - 12], [bx + 20, by - 8], [bx - 6, by + 22], [tx, ty], [bx - 30, by + 26]], { fill: '#FFFFFF', lw: 4.5, seed: seed + 1 });
  }
  function tear(ctx, x, y, s, seed) { G.shape(ctx, [[x, y - 12 * s], [x + 7 * s, y + 2 * s], [x, y + 9 * s], [x - 7 * s, y + 2 * s]], { fill: '#7FB2EA', lw: 2.4, seed, second: false }); }

  // ---------- você sentado, abraçando os joelhos (cena da queda) ----------
  function sitHug(ctx, x, y, s, t, pale) {
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    for (let k = 0; k < 7; k++) sk(ctx, [[-110 + k * 5, 4 + k * 2], [90 - k * 8, 4 + k * 2]], 1.8, 950 + k);
    G.poly(ctx, [[-95, -60], [-40, -60], [-30, -250], [-85, -250]], { fill: '#FFFFFF', lw: 3, seed: 951 });
    xhatch(ctx, [[-95, -60], [-40, -60], [-30, -250], [-85, -250]], { gap: 7, angles: [0.9, -0.8], alpha: 0.45, seed: 952, lw: 1.2 });
    for (const q of [-1, 1]) { G.limb(ctx, [[-60, -40 + q * 6], [10 + q * 14, -175], [10 + q * 22, -20]], { color: '#FFFFFF', lw: 15, seed: 953 + q, outline: 3 }); shoe(ctx, 22 + q * 26, 0, 1, 956 + q * 4); }
    for (const q of [-1, 1]) G.limb(ctx, [[-60, -230], [40, -205 + q * 10], [24, -150 + q * 6]], { color: '#FFFFFF', lw: 11, seed: 960 + q, outline: 2.6 });
    hand(ctx, 20, -150, 963, 1); hand(ctx, 34, -142, 967, 1);
    ctx.save(); ctx.translate(-30, -320); ctx.rotate(0.12);
    G.ellipse(ctx, 0, 0, 70, 70, { fill: '#FFFFFF', lw: 3.6, seed: 970 });
    xhatch(ctx, ell(0, 0, 70, 70, 30), { gap: 6, angles: [0.9, -0.5], alpha: 0.3 + 0.3 * pale, seed: 971, lw: 1.1, poly2: [[-70, 10], [80, 10], [80, 80], [-70, 80]] });
    ctx.save(); ctx.translate(6, 22); face(ctx, 70, 'calm', t, 972); ctx.restore();
    ctx.save(); ctx.translate(0, -10);
    const dome = Array.from({ length: 17 }, (_, i) => { const a = Math.PI * 1.04 + (i / 16) * Math.PI * 0.98; return [Math.cos(a) * 75 - 4, Math.sin(a) * 55 - 21]; });
    G.shape(ctx, dome, { fill: '#2F63C8', lw: 3.6, seed: 973 });
    xhatch(ctx, dome, { gap: 5, angles: [0.8, -0.8], color: '#102A66', alpha: 0.5, seed: 974, lw: 1.2, poly2: [[0, -140], [140, -140], [140, 0], [-10, 0]] });
    const brim = [[20, -26], [90, -34], [108, -18], [86, -10], [16, -16]];
    G.shape(ctx, brim, { fill: '#2F63C8', lw: 3.4, seed: 975 }); xhatch(ctx, brim, { gap: 5, angles: [0.6], color: '#102A66', alpha: 0.6, seed: 976, lw: 1.2 });
    ctx.restore(); ctx.restore();
    ctx.restore();
  }

  // ---------- cérebro couve-flor com rosto, lágrimas e um copo de O2 vazio ----------
  function brainChar(ctx, x, y, s, t, dark) {
    ctx.save(); ctx.translate(x, y); ctx.scale(s, s);
    // bracinhos e copo
    G.limb(ctx, [[-150, 60], [-230, 130], [-250, 40]], { color: '#FFFFFF', lw: 11, seed: 980, outline: 2.8 });
    G.limb(ctx, [[150, 60], [220, 150], [200, 210]], { color: '#FFFFFF', lw: 11, seed: 981, outline: 2.8 });
    const cup = [[-300, -110], [-200, -110], [-215, 40], [-285, 40]];
    G.poly(ctx, cup, { fill: '#FFFFFF', lw: 4, seed: 982 });
    xhatch(ctx, cup, { gap: 12, angles: [1.2], alpha: 0.25, seed: 983, lw: 1.2 });
    lab(ctx, 'O', -268, -30, 54); lab(ctx, '2', -240, -16, 30);
    hand(ctx, -250, 30, 984, -1);
    // contorno de couve-flor
    const P = []; for (let i = 0; i < 90; i++) { const a = (i / 90) * Math.PI * 2; const r = 1 + 0.07 * Math.abs(Math.sin(a * 8)) + 0.03 * Math.sin(a * 3); P.push([Math.cos(a) * 200 * r, Math.sin(a) * 165 * r - 20]); }
    G.shape(ctx, P, { fill: '#F2F2F2', lw: 5, seed: 985 });
    xhatch(ctx, P, { gap: 7, angles: [0.8, -0.8], alpha: 0.45 + 0.35 * dark, seed: 986, lw: 1.3, poly2: [[60, -260], [260, -260], [260, 200], [-120, 200]] });
    for (let k = 0; k < 44; k++) { const a = hh(k, 11) * 6.28, r = 0.35 + hh(k, 12) * 0.6, px = Math.cos(a) * 180 * r, py = Math.sin(a) * 140 * r - 20; if (Math.abs(px) < 70 && py > -60 && py < 90) continue; const q = 14 + hh(k, 13) * 12; sk(ctx, [[px - q, py], [px - q * 0.3, py - q * 0.8], [px + q * 0.4, py - q * 0.2], [px - q * 0.1, py + q * 0.5], [px + q, py + q * 0.2]], 2.6, 990 + k); }
    // rosto chorando: olheiras, pupilas pequenas, boca aberta ondulada
    for (const sd of [-1, 1]) {
      const ex = sd * 62, ey = -10;
      G.ellipse(ctx, ex, ey + 30, 44, 22, { fill: null, lw: 2.6, seed: 1040 + sd, second: false });
      G.ellipse(ctx, ex, ey, 36, 40, { fill: '#FFFFFF', lw: 3.6, seed: 1042 + sd });
      G.ellipse(ctx, ex + sd * 2, ey + 6, 9, 10, { fill: INK, lw: 1, seed: 1044 + sd, second: false });
      G.line(ctx, [[sd * 104, -78], [sd * 74, -88], [sd * 36, -70]], { lw: 4.5, seed: 1046 + sd });
      const ty = (t * 70 + sd * 20) % 140;
      tear(ctx, ex + sd * 20, ey + 46 + ty, 1.4, 1048 + sd);
      G.shape(ctx, [[ex - 12, ey + 34], [ex + 14, ey + 34], [ex + 6, ey + 50], [ex - 4, ey + 46]], { fill: '#7FB2EA', lw: 2, seed: 1050 + sd, second: false });
    }
    const mo = 18 + 8 * Math.sin(t * 9);
    G.shape(ctx, [[-60, 78], [-30, 68], [0, 72], [30, 66], [62, 80], [40, 80 + mo], [0, 86 + mo], [-40, 82 + mo]], { fill: '#2A2222', lw: 4, seed: 1052 });
    // tronco cerebral
    G.limb(ctx, [[20, 130], [36, 200], [30, 260]], { color: '#F2F2F2', lw: 34, seed: 1054, outline: 4 });
    ctx.restore();
  }

  // ---------- cenas ----------
  const SC = S.S;
  function rua(ctx, t) {
    const yt = (x) => lerp(117, 417, x / 626), yb = (x) => lerp(913, 691, x / 626);
    const wall = [[0, yt(0)], [626, yt(626)], [626, yb(626)], [0, yb(0)]];
    G.poly(ctx, wall, { fill: '#FFFFFF', lw: 4, seed: 810 });
    const rows = 14;
    for (let r = 1; r < rows; r++) G.line(ctx, [[0, lerp(yt(0), yb(0), r / rows)], [626, lerp(yt(626), yb(626), r / rows)]], { lw: 2.2, seed: 820 + r, step: 50, amp: 1 });
    for (let r = 0; r < rows; r++) for (let k = 0; k < 16; k++) { const u = 1 - Math.pow(1 - (k + (r % 2) * 0.5) / 16, 1.7), x = u * 626; if (x > 622) continue; G.line(ctx, [[x, lerp(yt(x), yb(x), r / rows) + 1], [x, lerp(yt(x), yb(x), (r + 1) / rows) - 1]], { lw: 2, seed: 860 + r * 30 + k, step: 60, amp: 0.7 }); }
    xhatch(ctx, wall, { gap: 17, angles: [0.75, -0.7], alpha: 0.55, seed: 80, lw: 1.4 });
    xhatch(ctx, [[380, 0], [640, 0], [640, 1000], [380, 1000]], { gap: 9, angles: [0.75, -0.75], alpha: 0.55, seed: 81, lw: 1.3, poly2: wall });
    G.poly(ctx, [[0, 70], [640, 398], [640, 417], [626, 417], [0, 117]], { fill: '#FFFFFF', lw: 4, seed: 811 }); sk(ctx, [[0, 96], [632, 408]], 2.2, 812);
    const walk = [[0, 913], [626, 691], [870, 672], [222, 1080], [0, 1080]];
    G.poly(ctx, walk, { fill: '#FFFFFF', lw: 3.5, seed: 813 });
    for (let k = 0; k < 5; k++) { const cx = 120 + hh(k, 1) * 450, cy = 880 + hh(k, 2) * 150; sk(ctx, [[cx, cy], [cx + 24, cy - 6], [cx + 10, cy + 8], [cx + 40, cy + 2]], 2, 820 + k); }
    sk(ctx, [[870, 672], [222, 1080]], 4, 815); sk(ctx, [[890, 674], [256, 1080]], 3, 816);
    const road = [[256, 1080], [890, 674], [1200, 672], [1920, 1017], [1920, 1080]];
    G.poly(ctx, road, { fill: '#7C7C7C', lw: 3.5, seed: 817 });
    for (let k = 0; k < 26; k++) { const px = lerp(400, 1800, hh(k, 3)), py = lerp(700, 1060, hh(k, 4)); sk(ctx, [[px, py], [px + 20 + hh(k, 5) * 30, py + 2]], 1.8, 830 + k, '#4A4A4A'); }
    sk(ctx, [[1200, 672], [1920, 1017]], 3.5, 818); sk(ctx, [[1230, 672], [1920, 985]], 2.5, 819);
    // poste piscando
    G.limb(ctx, [[639, 693], [639, 450], [639, 250]], { color: '#FFFFFF', lw: 12, seed: 840, outline: 3 });
    G.rrect(ctx, 627, 640, 24, 52, 6, { fill: '#FFFFFF', lw: 3, seed: 841 });
    sk(ctx, [[639, 252], [648, 226], [690, 214], [730, 226]], 4, 842);
    G.ellipse(ctx, 738, 230, 30, 10, { fill: '#FFFFFF', lw: 3.2, seed: 843 });
    const on = !(((t * 7) | 0) % 9 === 4 || ((t * 5) | 0) % 13 === 7);
    if (on) xhatch(ctx, [[714, 240], [762, 238], [840, 430], [650, 430]], { gap: 8, angles: [0.8, -0.8], alpha: 0.55, seed: 84, lw: 1.3 });
    for (const [px, py, pw, ph] of [[980, 700, 46, 8], [1060, 780, 80, 14], [930, 1010, 200, 42], [1640, 990, 180, 36], [1380, 820, 48, 9]]) {
      const P = Array.from({ length: 24 }, (_, i) => { const a = (i / 24) * Math.PI * 2; const rr = 1 + 0.2 * Math.sin(a * 3 + px) + 0.08 * Math.sin(a * 7); return [px + Math.cos(a) * pw * rr, py + Math.sin(a) * ph * rr]; });
      G.shape(ctx, P, { fill: '#E4E6E8', lw: 2.8, seed: px, second: false });
      xhatch(ctx, P, { gap: 6, angles: [0.1], color: '#9AA0A6', alpha: 0.5, seed: px + 5, lw: 1.2, poly2: [[px - pw * 2, py], [px + pw * 2, py], [px + pw * 2, py + ph * 2], [px - pw * 2, py + ph * 2]] });
      for (const q of [-0.25, -0.15, 0.2]) sk(ctx, [[px + pw * q, py - ph * 0.45], [px + pw * q, py + ph * 0.55]], 2, px + 9 + q * 10);
    }
    lab(ctx, '23:10', 34, 92, 92);
    const xNow = 820 + t * 30;
    person(ctx, { x: xNow, y: 925, s: 1.16, kind: 'tonico', exp: 'calm', arms: 'down', walk: t * 0.8, t, seed: 100 });
    const na = clamp((t - 2.2) / 0.4);
    if (na > 0) {
      ctx.save(); ctx.globalAlpha = na; lab(ctx, 'VOCÊ', 1300, 150, 96); ctx.restore();
      const hx = xNow - 10, p = ease.inOutQuad(clamp((t - 2.4) / 0.6));
      G.line(ctx, [[1280, 118], [1170, 126], [hx + 40, 175], [hx + 6, 270]].slice(0, 2 + Math.round(p * 2)), { lw: 6, seed: 880, step: 12 });
      if (p > 0.95) G.line(ctx, [[hx - 22, 232], [hx + 6, 270], [hx + 30, 238]], { lw: 6, seed: 881 });
    }
    tag(ctx, t, 7.2, 'poste piscando', 820, 110, 745, 205, 40, 886);
    tag(ctx, t, 9.0, 'cheiro de chuva', 1420, 760, 1600, 960, 40, 887);
  }

  function queda(ctx, t, t0) {
    const u = t - t0;
    // muro em diagonal, cinza, com tijolos e rabiscos (como no exemplo)
    const top = (x) => lerp(120, 430, x / 1920), base = (x) => lerp(820, 740, x / 1920);
    const wall = [[0, top(0)], [1920, top(1920)], [1920, base(1920)], [0, base(0)]];
    G.poly(ctx, wall, { fill: '#C9C9C9', lw: 4, seed: 900 });
    const rows = 13;
    for (let r = 1; r < rows; r++) G.line(ctx, [[0, lerp(top(0), base(0), r / rows)], [1920, lerp(top(1920), base(1920), r / rows)]], { lw: 2.2, seed: 901 + r, step: 60 });
    for (let r = 0; r < rows; r++) for (let k = 0; k < 26; k++) { const x = (k + (r % 2) * 0.5) * 76; G.line(ctx, [[x, lerp(top(x), base(x), r / rows) + 1], [x, lerp(top(x), base(x), (r + 1) / rows) - 1]], { lw: 2, seed: 915 + r * 30 + k, step: 60, amp: 0.7 }); }
    xhatch(ctx, wall, { gap: 11, angles: [1.2, -0.4, 0.5], alpha: 0.5, seed: 902, lw: 1.3 });
    G.poly(ctx, [[0, top(0) - 30], [1920, top(1920) - 24], [1920, top(1920)], [0, top(0)]], { fill: '#FFFFFF', lw: 4, seed: 903 });
    // luz do poste sobre você
    const g = ctx.createRadialGradient(760, 640, 20, 760, 640, 420); g.addColorStop(0, 'rgba(255,255,255,0.95)'); g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g; ctx.fillRect(300, 200, 920, 880);
    // calçada, meio-fio e rua com névoa
    const side = [[0, base(0)], [1920, base(1920)], [1920, 850], [0, 960]];
    G.poly(ctx, side, { fill: '#EDEDED', lw: 3.5, seed: 904 });
    for (let k = 0; k < 6; k++) { const x = 150 + k * 300; sk(ctx, [[x, lerp(base(x), lerp(960, 850, x / 1920), 0.1)], [x - 40, lerp(960, 850, x / 1920)]], 2, 905 + k); }
    sk(ctx, [[0, 960], [1920, 850]], 4, 906); sk(ctx, [[0, 990], [1920, 878]], 3, 907);
    const street = [[0, 990], [1920, 878], [1920, 1080], [0, 1080]];
    G.poly(ctx, street, { fill: '#8A8A8A', lw: 3, seed: 908 });
    xhatch(ctx, street, { gap: 9, angles: [0.1, 1.3], alpha: 0.3, seed: 909, lw: 1.2 });
    for (let k = 0; k < 4; k++) { const x = 300 + k * 420; sk(ctx, [[x, 1000], [x + 30, 1020], [x + 10, 1040], [x + 50, 1060]], 2.4, 910 + k); }
    // poça de sangue crescendo e cacos da garrafa
    const pool = clamp((u - 0.8) / 6);
    if (pool > 0) G.shape(ctx, Array.from({ length: 22 }, (_, i) => { const a = (i / 22) * Math.PI * 2; const rr = 1 + 0.25 * Math.sin(a * 4 + 1); return [900 + Math.cos(a) * 150 * pool * rr, 915 + Math.sin(a) * 30 * pool * rr]; }), { fill: RED, lw: 2.5, seed: 930, second: false });
    for (let i = 0; i < 6; i++) { const cx = 1010 + i * 34 + hh(i, 1) * 20, cy = 905 + hh(i, 2) * 30, r = 14 + hh(i, 3) * 14; G.shape(ctx, [[cx, cy - r], [cx + r * 0.7, cy + r * 0.3], [cx - r * 0.5, cy + r * 0.5]], { fill: '#F4F7F6', lw: 2.6, seed: 935 + i }); sk(ctx, [[cx - 3, cy - r * 0.4], [cx + 3, cy + r * 0.2]], 1.6, 940 + i); }
    G.limb(ctx, [[1170, 900], [1230, 880]], { color: '#F4F7F6', lw: 30, seed: 945, outline: 3 });
    sitHug(ctx, 740, 905, 1.55, t, clamp(u / 9) * 0.5);
    splat(ctx, 14, 950, 500, 380, 1100, 560);
    for (let i = 0; i < 4; i++) hashMark(ctx, 260 + i * 430, 330 + (i % 2) * 120, 22, 960 + i * 5);
    // "PLOFT!" da queda
    if (u < 1.1) { const p = ease.outBack(clamp(u / 0.2), 2); ctx.save(); ctx.translate(1180, 300); ctx.scale(p, p); ctx.rotate(-0.08); lab(ctx, 'PLOFT!', 0, 0, 130, { align: 'center' }); ctx.restore(); }
    tag(ctx, t, t0 + 3.3, 'GARRAFA\nQUEBRADA', 1330, 560, 1150, 880, 52, 970, 'left');
    tag(ctx, t, t0 + 5.6, 'SANGRANDO', 380, 1040, 800, 920, 52, 971, 'left', RED);
  }

  function choque(ctx, t, t0) {
    const u = t - t0;
    // você, de perto, mãos na barriga
    person(ctx, { x: 820, y: 1330, s: 2.25, kind: 'tonico', exp: 'scared', arms: 'belly', t, seed: 100, shake: 2 });
    const st = clamp(u / 3);
    ctx.save(); ctx.translate(820, 1330 - 2.25 * 230);
    G.shape(ctx, Array.from({ length: 20 }, (_, i) => { const a = (i / 20) * Math.PI * 2; const rr = 1 + 0.3 * Math.sin(a * 5); return [Math.cos(a) * 60 * st * rr + 40, Math.sin(a) * 50 * st * rr + 30]; }), { fill: RED, lw: 2, seed: 1100, second: false });
    ctx.restore();
    // linhas de impacto na barriga
    for (let i = 0; i < 9; i++) { const a = -0.3 + (i / 8) * 1.6, r0 = 230 + 20 * Math.sin(t * 20 + i), r1 = r0 + 70; const cx = 880, cy = 830; sk(ctx, [[cx + Math.cos(a) * r0, cy - Math.sin(a) * r0 * 0.7], [cx + Math.cos(a) * r1, cy - Math.sin(a) * r1 * 0.7]], 3.5, 1110 + i); }
    shakeLines(ctx, 560, 300, 120, 1120, -1); shakeLines(ctx, 1090, 300, 120, 1123, 1);
    splat(ctx, 20, 1130, 150, 120, 1800, 700);
    for (let i = 0; i < 5; i++) hashMark(ctx, 220 + i * 360, 180 + (i % 3) * 140, 24, 1140 + i * 5);
    tag(ctx, t, t0 + 1.2, 'DOR?', 1340, 260, undefined, undefined, 110, 1150);
    tag(ctx, t, t0 + 2.2, 'AINDA NÃO.', 1340, 370, undefined, undefined, 80, 1151, 'left', RED);
    tag(ctx, t, t0 + 4.0, 'PRESSÃO SURDA,\nCOMO UM SOCO', 1300, 640, 1000, 800, 58, 1152);
    tag(ctx, t, t0 + 2.6, 'o choque\nsegura a dor', 140, 560, 520, 720, 50, 1153);
  }

  function sede(ctx, t, t0) {
    const u = t - t0;
    // chão e muro ao fundo
    sk(ctx, [[0, 880], [1920, 860]], 4, 1200); xhatch(ctx, [[0, 880], [1920, 860], [1920, 1080], [0, 1080]], { gap: 12, angles: [0.2], alpha: 0.25, seed: 1201, lw: 1.2 });
    for (let k = 0; k < 6; k++) sk(ctx, [[0, 300 + k * 80], [340 + k * 6, 300 + k * 80]], 2, 1202 + k);
    xhatch(ctx, [[0, 300], [360, 300], [360, 880], [0, 880]], { gap: 13, angles: [0.8, -0.8], alpha: 0.4, seed: 1209, lw: 1.3 });
    sk(ctx, [[360, 300], [360, 880]], 4, 1208);
    // você recostado, pálido, suando, pedindo água
    person(ctx, { x: 820, y: 880, s: 1.05, kind: 'tonico', exp: 'worried', arms: 'raise', pale: clamp(u / 5) * 0.9, sweat: 1, lie: 0.42, shake: 2.5, t, seed: 100 });
    G.shape(ctx, Array.from({ length: 18 }, (_, i) => { const a = (i / 18) * Math.PI * 2; return [760 + Math.cos(a) * 160 * (1 + 0.2 * Math.sin(a * 3)), 885 + Math.sin(a) * 26]; }), { fill: RED, lw: 2.2, seed: 1210, second: false });
    shakeLines(ctx, 330, 420, 140, 1211, -1); shakeLines(ctx, 870, 380, 120, 1214, 1);
    for (let i = 0; i < 6; i++) hashMark(ctx, 420 + hh(i, 1) * 600, 300 + hh(i, 2) * 420, 18, 1220 + i * 5);
    const pb = appear(t, t0 + 4.0);
    if (pb > 0) { ctx.save(); ctx.translate(1180, 260); ctx.scale(pb, pb); spiky(ctx, 0, 0, 290, 150, -560, 210, 1230); lab(ctx, 'ÁGUA, POR', 0, -10, 76, { align: 'center' }); lab(ctx, 'FAVOR!', 0, 70, 76, { align: 'center' }); ctx.restore(); }
    // coração disparado em destaque
    heart(ctx, 1600, 760, 0.85, pulse(S.beats, t), 'scared', t);
    tag(ctx, t, t0 + 1.0, 'CORAÇÃO\nDISPARADO!', 1640, 500, 1610, 620, 46, 1240, 'center');
    tag(ctx, t, t0 + 2.6, 'PELE FRIA\nE PÁLIDA', 380, 220, 640, 420, 46, 1241);
  }

  function cerebro(ctx, t, t0) {
    const u = t - t0;
    splat(ctx, 40, 1300, 100, 60, 1820, 1000);
    lab(ctx, 'CÉREBRO SEM OXIGÊNIO', 960, 120, 92, { align: 'center' });
    G.line(ctx, [[660, 140], [905, 136], [1010, 142]], { lw: 5, seed: 1301 });
    brainChar(ctx, 980, 560, 1.2, t, clamp(u / 7));
    for (let i = 0; i < 3; i++) spiral(ctx, 400 + i * 80, 260 + (i % 2) * 70, 30 + i * 6, t, 1310 + i, t * 3 + i);
    for (let i = 0; i < 3; i++) spiral(ctx, 1470 + i * 90, 300 + (i % 2) * 60, 28 + i * 5, t, 1320 + i, -t * 3 - i);
    tag(ctx, t, t0 + 2.0, 'CADÊ O AR?', 380, 860, 560, 700, 56, 1330);
    tag(ctx, t, t0 + 3.5, 'BUÁÁÁ!', 1260, 860, 1080, 720, 64, 1331);
    tag(ctx, t, t0 + 4.6, 'TONTURA', 1500, 520, undefined, undefined, 50, 1332);
  }

  function ajuda(ctx, t, t0) {
    lab(ctx, 'MAS DÁ PARA AGIR!', 960, 130, 96, { align: 'center', color: '#2E7D4F' });
    G.line(ctx, [[540, 160], [960, 154], [1380, 162]], { lw: 6, seed: 1400, color: '#2E7D4F' });
    heart(ctx, 1640, 360, 0.75, pulse(S.calm, t, 0.8), 'happy', t);
    const steps = [['1', 'LIGUE 192', 'SAMU — peça ajuda já'], ['2', 'APERTE O FERIMENTO', 'com um pano limpo, sem soltar'], ['3', 'ESPERE A AJUDA', 'mantenha a pessoa deitada']];
    steps.forEach(([n, a, b], i) => {
      const q = appear(t, t0 + 4.4 + i * 1.6); if (q <= 0) return;
      ctx.save(); ctx.globalAlpha = clamp(q); ctx.translate(120, 260 + i * 190);
      G.ellipse(ctx, 50, 50, 50, 50, { fill: '#2E7D4F', lw: 4, seed: 1410 + i });
      lab(ctx, n, 50, 76, 76, { color: '#FFF', align: 'center' });
      lab(ctx, a, 140, 54, 64); lab(ctx, b, 140, 106, 42, { color: '#555' });
      ctx.restore();
    });
    person(ctx, { x: 1780, y: 1000, s: 0.9, kind: 'tonico', exp: 'calm', arms: 'down', pale: 0.4, lie: 1, t });
    person(ctx, { x: 1450, y: 990, s: 0.95, kind: 'nina', exp: 'worried', arms: 'press', t });
    const ring = Math.sin(t * 22) * (t > t0 + 4.4 && t < t0 + 6.4 ? 4 : 0);
    ctx.save(); ctx.translate(1000, 300); ctx.rotate(ring * Math.PI / 180); G.rrect(ctx, 0, 0, 110, 190, 18, { fill: '#2A2A2A', lw: 4, seed: 1420 }); lab(ctx, '192', 55, 110, 46, { color: '#FFF', align: 'center' }); ctx.restore();
    splat(ctx, 10, 1430, 100, 60, 1820, 240);
  }
  function fim(ctx, t) {
    ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, 1920, 1080);
    splat(ctx, 24, 1500, 100, 80, 1820, 1000);
    lab(ctx, 'SANGRAMENTO GRAVE', 960, 430, 120, { align: 'center' });
    lab(ctx, 'É EMERGÊNCIA.', 960, 560, 120, { align: 'center', color: RED });
    lab(ctx, 'LIGUE 192', 960, 710, 90, { align: 'center', color: '#2E7D4F' });
    lab(ctx, 'prévia de 1 minuto · conteúdo educativo', 960, 830, 38, { align: 'center', color: '#666' });
  }

  let SUBS = [];
  Studio.film({
    async init() { G.setStyle('paper', { amp: 1.6, boilFps: 8 }); const vo = await Studio.loadJSON('out/voice.json'); SUBS = globalThis.Subs ? globalThis.Subs.fromVoice(vo, { maxWords: 6, hold: 0.3 }) : []; },
    draw(ctx, t) {
      ctx.fillStyle = '#FFFFFF'; ctx.fillRect(0, 0, G.W, G.H);
      ctx.save(); ctx.scale(G.W / 1920, G.H / 1080);
      if (t < SC.queda[0]) rua(ctx, t);
      else if (t < SC.choque[0]) queda(ctx, t, SC.queda[0]);
      else if (t < SC.sede[0]) choque(ctx, t, SC.choque[0]);
      else if (t < SC.cerebro[0]) sede(ctx, t, SC.sede[0]);
      else if (t < ev.cut) cerebro(ctx, t, SC.cerebro[0]);
      else if (t < SC.fim[0]) ajuda(ctx, t, SC.ajuda[0]);
      else fim(ctx, t);
      for (const k of ['choque', 'sede', 'cerebro']) { const v = (t - SC[k][0]) / 0.3; if (v >= 0 && v < 1) { ctx.fillStyle = `rgba(255,255,255,${1 - v})`; ctx.fillRect(0, 0, 1920, 1080); } }
      const sh = t >= ev.fall && t < ev.fall + 0.5 ? (1 - (t - ev.fall) / 0.5) * 16 : 0; // tremida da queda (desenhada depois, como um flash)
      if (t >= ev.fall && t < ev.fall + 0.12) { ctx.fillStyle = 'rgba(255,255,255,0.6)'; ctx.fillRect(0, 0, 1920, 1080); }
      ctx.restore();
      if (t < ev.cut) globalThis.Subs && Subs.draw(ctx, t, SUBS, { style: 'box', color: '#FFFFFF', fam: 'Patrick Hand', size: 50 });
      else if (t < SC.fim[0] + 2) globalThis.Subs && Subs.draw(ctx, t, SUBS, { style: 'box', color: '#FFFFFF', fam: 'Patrick Hand', size: 50 });
      if (t >= ev.dark && t < ev.cut) { ctx.fillStyle = `rgba(0,0,0,${ease.inQuad(clamp((t - ev.dark) / (ev.cut - ev.dark - 0.05)))})`; ctx.fillRect(0, 0, G.W, G.H); }
      const fl = t >= ev.cut ? Math.exp(-(t - ev.cut) * 7) : 0; if (fl > 0.02) { ctx.fillStyle = `rgba(255,255,255,${fl})`; ctx.fillRect(0, 0, G.W, G.H); }
      if (t < 0.3) { ctx.fillStyle = `rgba(255,255,255,${1 - t / 0.3})`; ctx.fillRect(0, 0, G.W, G.H); }
    },
    post: { paper: 0, vignette: 0, grain: 0.03 },
  });
})();
