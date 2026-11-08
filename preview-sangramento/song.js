// TRILHA — tensa e esparsa; o coração do filme são os batimentos (mesmos eventos que a imagem usa).
const path = require('path');
const { SR, Bus, reverb, pingpong } = require('./engine/audio/dsp');
const I = require('./engine/audio/instruments');
const MIX = require('./engine/audio/mix');
const sc = require('./score');
const { T, BEAT, DURATION, m, ev } = sc;

const N = Math.ceil(DURATION * SR);
const bus = () => new Bus(N);
const hb = bus(), bass = bus(), pad = bus(), keys = bus(), fx = bus(), str = bus(), verb = bus(), dly = bus();

// ---------- batimentos (sincronizados com o coração desenhado) ----------
const HB = I.heartbeat();
for (const b of sc.beats) { hb.addMono(HB, b.t, 0.9 * b.a); }
for (const b of sc.calm) { hb.addMono(HB, b.t, 0.5); }

// ---------- pads e baixo ----------
for (const c of sc.chords) {
  const tense = c.t0 >= T(9) && c.t0 < T(15);
  const hope = c.t0 >= T(15);
  const opts = { cutoff: tense ? 700 : hope ? 1500 : 900, attack: 0.9, release: 1.6 };
  if (c.t0 >= ev.dark && c.t0 < ev.cut) continue;
  for (const n of c.notes) { const { L, R } = I.padNote(n, c.t1 - c.t0 + 0.4, opts); pad.addStereo(L, R, c.t0, hope ? 0.1 : 0.085); }
  if (c.t0 < T(15) - 0.01 || c.t0 >= T(15)) bass.addMono(I.bass(c.bass + 12, (c.t1 - c.t0) * 0.9, { bright: 0.2, sub: 1 }), c.t0, tense ? 0.55 : 0.4);
}
// cordas sobem de tensão nas etapas 3 e 4
for (let b = 9; b < 15; b++) for (const n of ['A3', 'E4', 'F4']) { const s = I.strings(m(n) + (b > 11 ? 1 : 0), 3.4, { attack: 1.2, release: 1.2, bright: 0.6 }); str.addStereo(s.L, s.R, T(b), 0.07 + 0.02 * (b - 9)); }

// ---------- teclas: poucas notas, minor; esperança no final ----------
const am = ['A4', 'C5', 'E5', 'D5', 'C5', 'A4'];
for (let i = 0; i < 14; i++) { const t = T(0) + 0.8 + i * 2.1; if (t > T(9) - 1) break; const k = I.epiano(m(am[i % am.length]), 1.2); keys.addMono(k, t, 0.18); verb.addMono(k, t, 0.2); }
const hopeMel = [['C5', 0], ['E5', 1], ['G5', 2], ['E5', 3], ['D5', 4], ['E5', 5], ['G5', 6], ['C6', 7]];
for (let b = 15; b < 20; b++) for (const [n, i] of hopeMel) { if (i % 2 && b === 19) continue; const t = T(b) + 0.05 + i * BEAT * 0.5; if (t > DURATION - 0.8) continue; const x = I.musicBox(m(n)); keys.addMono(x, t, 0.22); verb.addMono(x, t, 0.2); dly.addMono(x, t, 0.08); }

// ---------- efeitos ----------
fx.addMono(I.noiseSweep(T(3), 2500, 1200, { q: 0.6, pink: true, shape: () => 1 }), 0, 0.05); // chuva fina na rua
for (const b of [3, 6, 9, 12]) { fx.addMono(I.paperFwip(0.8, b), T(b) - 0.03, 0.3); fx.addMono(I.pop(900 + b * 60), T(b) + 0.25, 0.18); }
fx.addMono(I.noiseSweep(T(3), 200, 5000, { q: 0.9, shape: (x) => x * x, pink: true }), T(12) - 0.5, 0.18);
fx.addMono(I.noiseSweep(0.9, 6000, 400, { q: 0.8, pink: true }), ev.dark, 0.25);
// o corte para a luz: acorde e pop exatamente em ev.cut
fx.addMono(I.pop(1500), ev.cut, 0.55);
fx.addMono(I.subBoom(1.8, 70, 36), ev.cut, 0.45);
for (const n of ['C4', 'E4', 'G4', 'C5']) { const x = I.musicBox(m(n)); keys.addMono(x, ev.cut, 0.35); verb.addMono(x, ev.cut, 0.3); }
for (let i = 0; i < 3; i++) fx.addMono(I.paperFwip(1 + i * 0.1, 40 + i), T(16) + i * 3 - 0.03, 0.25);
for (const t of [T(19) + 0.2, T(19) + 1.0]) fx.addMono(I.scribble(0.6, Math.round(t * 7)), t, 0.2);

// ---------- mix ----------
const stems = { hb, bass, pad, keys, fx, str, verb: reverb(verb, { room: 0.8, damp: 0.35 }), dly: pingpong(dly, BEAT * 0.75, 0.35, 3000) };
const GAIN = { hb: 1.2, bass: 0.8, pad: 2.4, keys: 1, fx: 0.9, str: 1.6, verb: 1, dly: 1 };
const out = path.join(__dirname, 'out');
const mix = MIX.mixdown(stems, GAIN, { stemDir: process.env.STEMS ? out : null });
MIX.highpass(mix, 24);
MIX.gate(mix, ev.dark + 0.9, ev.cut); // um instante de silêncio antes da luz
MIX.fadeOut(mix, DURATION - 2, DURATION);
const M = MIX.master(mix, 0.8, undefined, { lufs: parseFloat(process.env.LUFS || '-14') });
MIX.writeWav(path.join(out, 'music.wav'), mix);
console.log(`wrote out/music.wav (${DURATION}s, ${M.lufs !== undefined ? M.lufs.toFixed(1) + ' LUFS' : ''})`);
