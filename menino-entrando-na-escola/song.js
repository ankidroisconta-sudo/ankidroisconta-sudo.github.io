// THE SONG — renders every sound from the score into out/music.wav.
//   node song.js            (STEMS=1 also writes out/stem-*.wav, DRIVE=0.8 sets master loudness)
const path = require('path');
const { SR, Bus, reverb, pingpong } = require('./engine/audio/dsp');
const I = require('./engine/audio/instruments');
const MIX = require('./engine/audio/mix');
const sc = require('./score');
const { T, BEAT, DURATION, m, ev, clock } = sc;

const N = Math.ceil(DURATION * SR);
const bus = () => new Bus(N);
const drums = bus(), bass = bus(), pad = bus(), keys = bus(), brass = bus(), fx = bus();
const verb = bus(), dly = bus();

// ---------- percussão suave: shaker + woodblock nos passos ----------
const SH = [I.shaker(1, 15), I.shaker(1, 16)];
clock.eachStep(2, 9, 8, (t, b, s) => { if (s % 2 === 1 || b < 2) return; drums.addMono(SH[(s / 2) % 2 | 0], t, 0.16, s % 4 ? 0.3 : -0.3); });
for (const t of sc.steps) drums.addMono(I.woodTick(1 + 0.05 * ((t * 10) % 3)), t, 0.35);
clock.eachStep(6, 9, 4, (t, b, s) => { if (s === 0 || s === 2) drums.addMono(I.kick({ punch: 0.5, tail: 0.2 }), t, 0.45); });

// ---------- baixo ----------
clock.eachStep(2, 9, 4, (t, b, s) => {
  const c = sc.chordAt(t);
  if (!c) return;
  if (s === 0 || s === 2) bass.addMono(I.bass(s === 2 ? c.bass + 19 : c.bass + 12, BEAT * 0.9, { sub: 0.7, bright: 0.5 }), t, 0.5);
});
bass.addMono(I.bass(m('C2'), 2.5, { bright: 0.3, sub: 1 }), ev.end, 0.5);

// ---------- pads ----------
for (const c of sc.chords) {
  const opts = { cutoff: c.t0 >= ev.end ? 1400 : 1100, attack: 0.5, release: 1.4 };
  for (const n of c.notes) { const { L, R } = I.padNote(n, c.t1 - c.t0, opts); pad.addStereo(L, R, c.t0, 0.09); }
}

// ---------- caixinha de música e marimba ----------
for (const n of sc.musicbox) { const mb = I.musicBox(n.midi); keys.addMono(mb, n.t, 0.2); verb.addMono(mb, n.t, 0.2); dly.addMono(mb, n.t, 0.08); }
for (const n of sc.melody) {
  const x = I.marimba(n.midi, { thock: 0.1 });
  keys.addMono(x, n.t, 0.45); verb.addMono(x, n.t, 0.2); dly.addMono(x, n.t, 0.06);
  if (n.t >= ev.enterStart) { const b2 = I.brassNote(n.midi, n.dur * 0.9, { bright: 0.4 }); brass.addStereo(b2.L, b2.R, n.t, 0.12); }
}

// ---------- efeitos ----------
sc.bells.forEach((t, i) => { const b = I.bell(m('G5') * 0 + 880 * (i % 2 ? 1.25 : 1), 0.5, 2.6); fx.addMono(b, t, 0.35); verb.addMono(b, t, 0.3); });
fx.addMono(I.noiseSweep(0.6, 400, 2500, { q: 1, pink: true }), ev.doorOpen - 0.3, 0.2);
fx.addMono(I.pop(1200), ev.doorOpen, 0.4);
for (const c of sc.captions) fx.addMono(I.paperFwip(0.9, Math.round(c.t * 10)), c.t - 0.03, 0.22);
for (const w of sc.endText.words) fx.addMono(I.scribble(w.d, Math.round(w.t * 7)), w.t, 0.2);
drums.addMono(I.crash(18), ev.end, 0.18, 0.2);

// ---------- mix ----------
const stems = {
  drums, bass, pad, keys, brass, fx,
  verb: reverb(verb, { room: 0.84, damp: 0.3 }),
  dly: pingpong(dly, BEAT * 0.75, 0.38, 3500),
};
const GAIN = { drums: 0.5, bass: 0.7, pad: 2.6, keys: 0.9, brass: 1.6, fx: 0.8, verb: 1, dly: 1 };
const out = path.join(__dirname, 'out');
const mix = MIX.mixdown(stems, GAIN, { stemDir: process.env.STEMS ? out : null });
MIX.highpass(mix, 22);
MIX.fadeOut(mix, DURATION - 1.6, DURATION);
// LUFS=-14 node song.js masters to a target loudness (±0.2 LU) (-14 suits YouTube/Spotify-normalised platforms)
const M = MIX.master(mix, parseFloat(process.env.DRIVE || '0.8'), undefined, { lufs: process.env.LUFS ? parseFloat(process.env.LUFS) : null });
MIX.writeWav(path.join(out, 'music.wav'), mix);
console.log(`wrote out/music.wav (${DURATION.toFixed(2)}s${M.lufs !== undefined ? `, ${M.lufs.toFixed(1)} LUFS at drive ${M.drive.toFixed(2)}` : ''})`);
