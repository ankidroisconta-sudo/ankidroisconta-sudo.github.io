// PRÉVIA 1 MIN — "O que o corpo sente quando perde sangue" (explicativo educativo, traço de caneta).
(function () {
  const node = typeof require !== 'undefined';
  const U = node ? require('./engine/util') : globalThis.U;
  const MU = node ? require('./engine/music') : globalThis.MUSIC;
  const { m, makeClock, makeChords } = MU;

  const FPS = 30;
  const FORMAT = '16:9';
  const [W, H] = U.formatSize(FORMAT);
  const SAFE = U.safeArea(W, H);
  const clock = makeClock({ bpm: 80, offset: 0 }); // 1 compasso = 3 s
  const { T, BEAT } = clock;
  const DURATION = 60;

  // cenas (em compassos de 3 s)
  const SC = { rua: [0, 3], e1: [3, 6], e2: [6, 9], e3: [9, 12], e4: [12, 15], ajuda: [15, 19], fim: [19, 20] }
  const sc = {}; for (const k in SC) sc[k] = [T(SC[k][0]), T(SC[k][1])];
  const S = sc;

  const CH = {
    Am: { notes: ['A3', 'C4', 'E4'], bass: 'A1' }, Dm: { notes: ['A3', 'D4', 'F4'], bass: 'D2' },
    E: { notes: ['Ab3', 'B3', 'E4'], bass: 'E2' }, Bb: { notes: ['Bb3', 'D4', 'F4'], bass: 'Bb1' },
    C: { notes: ['G3', 'C4', 'E4'], bass: 'C2' }, F: { notes: ['A3', 'C4', 'F4'], bass: 'F1' }, G: { notes: ['G3', 'B3', 'D4'], bass: 'G1' },
  };
  const prog = ['Am', 'Am', 'Am', 'Am', 'Dm', 'Am', 'Dm', 'E', 'Dm', 'E', 'Bb', 'E', 'Bb', 'E', 'Bb', 'C', 'F', 'C', 'G', 'C'];
  const { chords, chordAt } = makeChords(clock, CH, prog.map((c, i) => [i, 0, 4, c]));

  // batimentos: a frequência acelera, enfraquece e some quando a cena escurece
  const bpmAt = (t) => {
    if (t < T(3)) return 62;
    if (t < T(6)) return U.lerp(62, 92, (t - T(3)) / 9);
    if (t < T(9)) return U.lerp(92, 128, (t - T(6)) / 9);
    if (t < T(12)) return U.lerp(128, 118, (t - T(9)) / 9);
    if (t < T(15) - 0.8) return U.lerp(118, 46, (t - T(12)) / 8.2);
    return 0;
  };
  const beats = [];
  for (let t = 0.6; t < T(15) - 0.8;) {
    const f = Math.max(0, Math.min(1, (T(15) - 0.8 - t) / 8)); // força cai no fim
    beats.push({ t, a: t > T(12) ? 0.25 + 0.75 * f : 1 });
    t += 60 / bpmAt(t);
  }
  const calm = [];
  for (let t = T(15) + 1.2; t < DURATION - 0.5; t += 60 / 72) calm.push({ t, a: 0.55 });

  const ev = { cut: T(15), dark: T(15) - 1.2 };
  const markers = { rua: 0, e1: T(3), e2: T(6), e3: T(9), e4: T(12), cut: { t: ev.cut, sync: 'av' }, ajuda: T(16), fim: T(19) };

  const SCORE = { FPS, FORMAT, W, H, SAFE, DURATION, clock, T, BEAT, S, m, chords, chordAt, beats, calm, ev, markers, bpmAt, prog };
  if (node) module.exports = SCORE; else globalThis.SCORE = SCORE;
})();
