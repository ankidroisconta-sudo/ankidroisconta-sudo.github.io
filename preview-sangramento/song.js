// TRILHA — melancólica e esparsa; os batimentos são os mesmos eventos que a imagem usa.
const path = require('path');
const { SR, Bus, reverb, pingpong } = require('./engine/audio/dsp');
const I = require('./engine/audio/instruments');
const MIX = require('./engine/audio/mix');
const Voice = require('./engine/audio/voice');
const sc = require('./score');
const { T, BEAT, DURATION, m, ev, S } = sc;

const N = Math.ceil(DURATION * SR);
const bus = () => new Bus(N);
const hb = bus(), bass = bus(), pad = bus(), keys = bus(), fx = bus(), str = bus(), verb = bus(), dly = bus();

const HB = I.heartbeat();
for (const b of sc.beats) hb.addMono(HB, b.t, 0.9 * b.a);
for (const b of sc.calm) hb.addMono(HB, b.t, 0.5);

for (const c of sc.chords) {
  if (c.t0 >= ev.dark - 0.5 && c.t0 < ev.cut) continue;
  const tense = c.t0 >= S.sede[0] && c.t0 < ev.cut, hope = c.t0 >= ev.cut;
  for (const n of c.notes) { const { L, R } = I.padNote(n, c.t1 - c.t0 + 0.4, { cutoff: tense ? 700 : hope ? 1500 : 950, attack: 0.9, release: 1.6 }); pad.addStereo(L, R, c.t0, hope ? 0.1 : 0.085); }
  bass.addMono(I.bass(c.bass + 12, (c.t1 - c.t0) * 0.9, { bright: 0.2, sub: 1 }), c.t0, tense ? 0.55 : 0.4);
}
for (let b = 10; b < 16; b++) for (const n of ['A3', 'E4', 'F4']) { const s = I.strings(m(n) + (b > 12 ? 1 : 0), 3.4, { attack: 1.2, release: 1.2, bright: 0.6 }); str.addStereo(s.L, s.R, T(b), 0.07 + 0.02 * (b - 10)); }

// piano melancólico na caminhada
const mel = ['E5', 'C5', 'A4', 'B4', 'C5', 'A4', 'G4', 'A4'];
for (let i = 0; i < 16; i++) { const t = 0.3 + i * 1.5; if (t > S.choque[0]) break; const k = I.epiano(m(mel[i % mel.length]), 1.3); keys.addMono(k, t, 0.17); verb.addMono(k, t, 0.22); }
// esperança no final
const hopeMel = [['C5', 0], ['E5', 1], ['G5', 2], ['E5', 3], ['D5', 4], ['E5', 5], ['G5', 6], ['C6', 7]];
for (let b = 16; b < 20; b++) for (const [n, i] of hopeMel) { const t = T(b) + 0.05 + i * BEAT * 0.5; if (t > DURATION - 0.8) continue; const x = I.musicBox(m(n)); keys.addMono(x, t, 0.22); verb.addMono(x, t, 0.2); dly.addMono(x, t, 0.08); }

// ambiente da rua, a queda, viradas de página
fx.addMono(I.noiseSweep(S.queda[0], 2200, 1400, { q: 0.6, pink: true, shape: () => 1 }), 0, 0.035);
fx.addMono(I.noiseSweep(0.35, 3000, 500, { q: 1, pink: true }), ev.fall - 0.3, 0.3);
fx.addMono(I.thud(70, 0.12), ev.fall, 0.8);
fx.addMono(I.glass(4, { size: 0.6 }), ev.fall + 0.05, 0.22);
for (const k of ['choque', 'sede', 'cerebro']) fx.addMono(I.paperFwip(0.8, S[k][0] * 10), S[k][0] - 0.03, 0.3);
fx.addMono(I.noiseSweep(T(3), 200, 5000, { q: 0.9, shape: (x) => x * x, pink: true }), S.cerebro[0], 0.15);
fx.addMono(I.noiseSweep(0.9, 6000, 400, { q: 0.8, pink: true }), ev.dark, 0.25);
fx.addMono(I.pop(1500), ev.cut, 0.55);
fx.addMono(I.subBoom(1.8, 70, 36), ev.cut, 0.45);
for (const n of ['C4', 'E4', 'G4', 'C5']) { const x = I.musicBox(m(n)); keys.addMono(x, ev.cut, 0.35); verb.addMono(x, ev.cut, 0.3); }

const vo = Voice.speak(sc.VO, { out: path.join(__dirname, 'out'), length: DURATION, gain: 1 });
MIX.duck([pad, str, keys, bass], vo.bus, { depth: 0.55 });
MIX.duck([hb], vo.bus, { depth: 0.3 });

const stems = { voice: vo.bus, hb, bass, pad, keys, fx, str, verb: reverb(verb, { room: 0.8, damp: 0.35 }), dly: pingpong(dly, BEAT * 0.75, 0.35, 3000) };
const GAIN = { voice: 2.4, hb: 0.7, bass: 0.8, pad: 2.4, keys: 1, fx: 0.9, str: 1.6, verb: 1, dly: 1 };
const out = path.join(__dirname, 'out');
const mix = MIX.mixdown(stems, GAIN, { stemDir: process.env.STEMS ? out : null });
MIX.highpass(mix, 24);
MIX.gate(mix, ev.dark + 0.9, ev.cut);
MIX.fadeOut(mix, DURATION - 2, DURATION);
const M = MIX.master(mix, 0.8, undefined, { lufs: -14 });
MIX.writeWav(path.join(out, 'music.wav'), mix);
console.log(`wrote out/music.wav (${DURATION}s, ${M.lufs.toFixed(1)} LUFS)`);
