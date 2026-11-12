// O FILME — menino entrando na escola. Cada quadro é função pura de t.
(function () {
  const U = globalThis.U, G = globalThis.G, Ch = globalThis.Ch, S = globalThis.SCORE, Studio = globalThis.Studio;
  const { BEAT, ev, clock, T } = S;
  const { clamp, lerp, ease } = U;
  const W = G.W, H = G.H;
  const GROUND = Math.round(H * 0.8);
  const K = Math.min(W, H) / 1080;
  const X = (x) => (x * W) / 1920;
  const DOORX = X(1500), DOORW = 150 * K, DOORH = 270 * K;
  const GATEX = W * S.GATE;
  const STYLE = { skin: '#B9774E', hair: '#1C1715', hairStyle: 'short', outfit: 'tee', shirt: '#2F7FD1', bottoms: 'shorts', shorts: '#2B3A67', shoes: '#F6F0E2', sleeves: 'short' };

  function sky(ctx, t) {
    const u = ease.inOutQuad(clamp(t / T(2)));
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, `rgb(${lerp(60, 120, u)},${lerp(70, 190, u)},${lerp(130, 235, u)})`);
    g.addColorStop(1, `rgb(${lerp(240, 255, u)},${lerp(150, 232, u)},${lerp(110, 180, u)})`);
    ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    // sol nascendo
    const sy = lerp(GROUND + 40, H * 0.2, ease.outQuad(clamp(t / T(2.5))));
    ctx.save(); ctx.globalCompositeOperation = 'lighter';
    const gl = ctx.createRadialGradient(W * 0.2, sy, 0, W * 0.2, sy, 320 * K);
    gl.addColorStop(0, 'rgba(255,230,150,0.8)'); gl.addColorStop(1, 'rgba(255,230,150,0)');
    ctx.fillStyle = gl; ctx.fillRect(0, 0, W, H); ctx.restore();
    G.ellipse(ctx, W * 0.2, sy, 70 * K, 70 * K, { fill: '#FFD45E', lw: 5, seed: 5 });
    // nuvens
    [[0.35, 0.16, 1], [0.7, 0.1, 0.8], [0.9, 0.25, 0.6]].forEach(([cx, cy, s], i) => {
      const x = ((cx * W + t * 14 * s) % (W + 400 * K)) - 200 * K, y = cy * H;
      for (const [dx, dy, r] of [[0, 0, 50], [55, -15, 62], [115, 0, 48]]) G.ellipse(ctx, x + dx * s * K, y + dy * s * K, r * s * K, r * 0.75 * s * K, { fill: '#FFFFFF', lw: 3, seed: 20 + i });
    });
  }

  function street(ctx, t) {
    G.poly(ctx, [[0, GROUND - 90 * K], [X(400), GROUND - 150 * K], [X(900), GROUND - 100 * K], [X(1400), GROUND - 160 * K], [W, GROUND - 110 * K], [W, H], [0, H]], { fill: '#6FB36A', lw: 5, seed: 3, hatch: { color: 'rgba(0,0,0,0.12)', gap: 9 } });
    G.poly(ctx, [[-20, GROUND - 10 * K], [W + 20, GROUND - 10 * K], [W + 20, H + 20], [-20, H + 20]], { fill: '#D9CDB4', lw: 5, seed: 4, hatch: { color: 'rgba(120,80,40,0.15)', gap: 8 } });
    // árvores
    for (const [tx, s] of [[0.1, 1], [0.38, 0.8]]) {
      const x = W * tx, sway = Math.sin(t * 1.5 + tx * 9) * 4;
      G.rrect(ctx, x - 14 * K * s, GROUND - 230 * K * s, 28 * K * s, 230 * K * s, 6, { fill: '#7A5230', lw: 4, seed: 40 });
      G.ellipse(ctx, x + sway, GROUND - 270 * K * s, 120 * K * s, 100 * K * s, { fill: '#3E9A5A', lw: 5, seed: 41, hatch: { color: 'rgba(0,0,0,0.15)', gap: 9 } });
    }
  }

  function school(ctx, t) {
    const bx = X(1180), bw = X(700), by = GROUND - 420 * K, bh = 430 * K;
    G.rrect(ctx, bx, by, bw, bh, 8, { fill: '#F2C86B', lw: 6, seed: 50, hatch: { color: 'rgba(120,70,0,0.12)', gap: 9 } });
    G.poly(ctx, [[bx - 30 * K, by + 4], [bx + bw / 2, by - 120 * K], [bx + bw + 30 * K, by + 4]], { fill: '#C4533E', lw: 6, seed: 51, hatch: { color: 'rgba(0,0,0,0.14)', gap: 9 } });
    // placa
    G.rrect(ctx, bx + bw / 2 - 150 * K, by - 85 * K, 300 * K, 56 * K, 10, { fill: '#FFF6DC', lw: 4, seed: 52 });
    G.text(ctx, 'ESCOLA', bx + bw / 2, by - 44 * K, { size: 44 * K, color: '#B23A2E', align: 'center' });
    // janelas
    for (const wx of [0.12, 0.3, 0.7, 0.88]) {
      const x = bx + bw * wx - 55 * K;
      G.rrect(ctx, x, by + 70 * K, 110 * K, 110 * K, 8, { fill: '#9FD6F2', lw: 5, seed: 60 + wx * 10 });
      G.line(ctx, [[x + 55 * K, by + 70 * K], [x + 55 * K, by + 180 * K]], { lw: 4, seed: 61 });
      G.line(ctx, [[x, by + 125 * K], [x + 110 * K, by + 125 * K]], { lw: 4, seed: 62 });
    }
    // porta: interior escuro e folhas que abrem com o sino
    const open = ease.outBack(clamp((t - ev.doorOpen) / 0.5), 1.2);
    const dx = DOORX - DOORW / 2, dy = GROUND - DOORH;
    G.rrect(ctx, dx - 12 * K, dy - 12 * K, DOORW + 24 * K, DOORH + 12 * K, 6, { fill: '#8A5A34', lw: 5, seed: 70 });
    G.rrect(ctx, dx, dy, DOORW, DOORH, 4, { fill: '#2A2038', lw: 4, seed: 71 });
    const lg = ctx.createLinearGradient(dx, dy, dx, dy + DOORH);
    lg.addColorStop(0, 'rgba(255,220,150,0.85)'); lg.addColorStop(1, 'rgba(255,200,120,0.3)');
    ctx.fillStyle = lg; ctx.globalAlpha = open; ctx.fillRect(dx + 6, dy + 6, DOORW - 12, DOORH - 6); ctx.globalAlpha = 1;
    const leaf = DOORW / 2 * (1 - open * 0.85);
    G.rrect(ctx, dx, dy, leaf, DOORH, 3, { fill: '#C07A3E', lw: 4, seed: 72 });
    G.rrect(ctx, dx + DOORW - leaf, dy, leaf, DOORH, 3, { fill: '#C07A3E', lw: 4, seed: 73 });
    // sino tremendo
    const ring = t >= ev.bell && t < ev.bell + 2.4 ? Math.sin((t - ev.bell) * 40) * 10 * Math.exp(-(t - ev.bell) * 1.5) : 0;
    ctx.save(); ctx.translate(bx + bw * 0.5, by - 130 * K); ctx.rotate(ring * Math.PI / 180);
    G.ellipse(ctx, 0, 14 * K, 20 * K, 22 * K, { fill: '#F2B84B', lw: 4, seed: 75 });
    ctx.restore();
    if (ring) for (let i = 0; i < 3; i++) G.text(ctx, '♪', bx + bw * 0.5 + (i - 1) * 60 * K, by - 170 * K - ((t - ev.bell) * 40 + i * 20) % 60, { size: 40 * K, color: '#B23A2E', align: 'center', alpha: Math.exp(-(t - ev.bell) * 0.8) });
    // cerca
    for (let i = 0; i < 14; i++) G.rrect(ctx, X(1150) - 160 * K + i * 28 * K, GROUND - 80 * K, 14 * K, 90 * K, 3, { fill: '#FFFFFF', lw: 3, seed: 80 + i });
  }

  function backpack(ctx, x, y, s, bob) {
    G.rrect(ctx, x - 70 * s, y - 250 * s - bob, 52 * s, 110 * s, 14 * s, { fill: '#E0703E', lw: 4.5, seed: 90 });
    G.rrect(ctx, x - 62 * s, y - 175 * s - bob, 36 * s, 34 * s, 8 * s, { fill: '#B8502A', lw: 3.5, seed: 91 });
  }

  function boy(ctx, t) {
    const dur = ev.stop - ev.walkStart;
    const u = clamp((t - ev.walkStart) / dur);
    const s = 1.35 * K;
    const walkingIn = t >= ev.enterStart;
    let x = lerp(-120 * K, GATEX, u), y = GROUND, sc = s, alpha = 1, o;
    if (t < ev.walkStart) { x = -120 * K; }
    const phase = Math.max(0, Math.min(t, ev.stop) - ev.walkStart) * 1.0 / BEAT * 0.5;
    const bob = Math.abs(Math.sin(phase * Math.PI * 2)) * 6 * K;
    if (t < ev.stop) {
      o = { pose: 'walk', walk: phase % 1, eyes: 'happy', mouth: 'smile', gesture: null };
    } else if (t < ev.enterStart) {
      o = { pose: 'stand', eyes: 'happy', mouth: 'grin', gesture: t < ev.bell ? 'wave' : null, headRot: Math.sin(t * 4) * 0.03 };
      if (t >= ev.bell) { o.eyes = 'wide'; o.mouth = 'o'; o.look = 1; }
    } else {
      const v = clamp((t - ev.enterStart) / (ev.enterEnd - ev.enterStart));
      const walk = ((t - ev.enterStart) * 1.8) % 1;
      x = lerp(GATEX, DOORX, ease.inOutQuad(clamp(v * 1.4)));
      const inside = clamp((v - 0.55) / 0.45);
      sc = s * lerp(1, 0.45, ease.inQuad(inside)); y = GROUND - inside * 40 * K; alpha = 1 - ease.inQuad(clamp((inside - 0.4) / 0.6));
      o = { pose: 'walk', walk, eyes: 'happy', mouth: 'grin' };
    }
    // sombra
    ctx.save(); ctx.globalAlpha = 0.2 * alpha; G.ellipse(ctx, x, GROUND + 6, 70 * sc / s * K, 12 * K, { fill: '#000', lw: 0 }); ctx.restore();
    ctx.save(); ctx.globalAlpha = alpha;
    Ch.person(ctx, { x, y: y - (o.pose === 'walk' ? bob * 0 : 0), s: sc, style: STYLE, facing: 1, ...o });
    backpack(ctx, x, y, sc, o.pose === 'walk' ? bob : 0);
    ctx.restore();
  }

  Studio.film({
    draw(ctx, t) {
      sky(ctx, t);
      street(ctx, t);
      school(ctx, t);
      if (t >= ev.stop && t < ev.bell) { /* mãe fora do quadro: coração sobe */ const a = (t - ev.stop) / (ev.bell - ev.stop); G.heart(ctx, W * 0.08 + a * 40, GROUND - 200 * K - a * 120 * K, 0.9 * K * (1 - a * 0.5)); }
      boy(ctx, t);
      if (t < 0.4) { ctx.fillStyle = `rgba(10,10,20,${1 - t / 0.4})`; ctx.fillRect(0, 0, W, H); }
      for (const c of S.captions) G.caption(ctx, c, t);
      if (t >= ev.end) {
        ctx.fillStyle = `rgba(20,25,50,${0.55 * clamp((t - ev.end) / 0.4)})`; ctx.fillRect(0, 0, W, H);
        const e = S.endText, size = 170;
        const full = e.words.map((w) => w.w).join(' ');
        let x = W / 2 - G.measure(ctx, full, size) / 2; const y = H * 0.48;
        e.words.forEach((w, i) => {
          const ww = G.measure(ctx, w.w + (i < e.words.length - 1 ? ' ' : ''), size);
          const p = ease.inOutQuad(clamp((t - w.t) / w.d));
          if (p > 0) { ctx.save(); ctx.beginPath(); ctx.rect(x - 10, y - size, ww * p + 12, size * 1.6); ctx.clip(); G.text(ctx, w.w, x, y, { size, color: '#FFF3D6' }); ctx.restore(); }
          x += ww;
        });
        const sa = clamp((t - e.sub.t) / 0.6);
        if (sa > 0) G.text(ctx, e.sub.text, W / 2, y + 90, { size: 64, fam: 'Patrick Hand', weight: 400, color: '#FFE9B8', align: 'center', alpha: sa });
      }
    },
    post: { paper: 0.4, vignette: 0.3, grain: 0.05 },
  });
})();
