// PRÉVIA 1 MIN — "Imagine a cena": o que você sente quando perde muito sangue. Fonte única de música e imagem.
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

  // cenas, em compassos de 3 s
  const SC = { rua: [0, 4], queda: [4, 7], choque: [7, 10], sede: [10, 13], cerebro: [13, 16], ajuda: [16, 19], fim: [19, 20] };
  const S = {}; for (const k in SC) S[k] = [T(SC[k][0]), T(SC[k][1])];

  const CH = {
    Am: { notes: ['A3', 'C4', 'E4'], bass: 'A1' }, Dm: { notes: ['A3', 'D4', 'F4'], bass: 'D2' },
    E: { notes: ['Ab3', 'B3', 'E4'], bass: 'E2' }, Bb: { notes: ['Bb3', 'D4', 'F4'], bass: 'Bb1' },
    C: { notes: ['G3', 'C4', 'E4'], bass: 'C2' }, F: { notes: ['A3', 'C4', 'F4'], bass: 'F1' }, G: { notes: ['G3', 'B3', 'D4'], bass: 'G1' },
  };
  const prog = ['Am', 'F', 'C', 'G', 'Am', 'Dm', 'E', 'Am', 'Dm', 'E', 'Dm', 'E', 'Bb', 'Bb', 'E', 'Bb', 'C', 'F', 'G', 'C'];
  const { chords, chordAt } = makeChords(clock, CH, prog.map((c, i) => [i, 0, 4, c]));

  const ev = { fall: S.queda[0] + 0.15, cut: S.ajuda[0], dark: S.ajuda[0] - 1.2 };

  // batimentos: começam na queda, disparam, enfraquecem e somem quando a tela escurece
  const bpmAt = (t) => {
    if (t < S.choque[0]) return U.lerp(72, 86, (t - ev.fall) / 9);
    if (t < S.sede[0]) return U.lerp(86, 108, (t - S.choque[0]) / 9);
    if (t < S.cerebro[0]) return U.lerp(108, 132, (t - S.sede[0]) / 9);
    return U.lerp(132, 58, (t - S.cerebro[0]) / 7.8);
  };
  const beats = [];
  for (let t = ev.fall + 0.9; t < ev.dark + 0.3;) {
    const f = Math.max(0, Math.min(1, (ev.dark + 0.3 - t) / 7));
    beats.push({ t, a: t > S.cerebro[0] ? 0.25 + 0.75 * f : 1 });
    t += 60 / bpmAt(t);
  }
  const calm = [];
  for (let t = ev.cut + 1.2; t < DURATION - 0.6; t += 60 / 72) calm.push({ t, a: 0.55 });

  // narração em segunda pessoa, como uma história (texto original)
  const VOICE = { voice: 'mb-br1', rate: 140 };
  const VO = [
    { at: 0.5, text: 'Imagine a cena.' },
    { at: 2.0, text: 'Passa das onze da noite e você volta pra casa por uma rua estreita, com um poste piscando e cheiro de chuva no asfalto.' },
    { at: 12.4, text: 'Aí você escorrega numa poça, cai em cima de uma garrafa quebrada... e percebe que está sangrando.' },
    { at: 21.3, text: 'O curioso? Quase não dói. O choque segura a dor, e fica só uma pressão surda, como um soco que tira o ar.' },
    { at: 30.3, text: 'Seu coração dispara pra compensar o sangue que falta. A pele fica fria e pálida, e bate uma sede enorme.' },
    { at: 39.3, text: 'Com menos sangue, chega menos oxigênio ao cérebro. Tudo gira, e a visão escurece...' },
    { at: 48.4, text: 'Mas essa história pode acabar bem: aperte o ferimento com um pano limpo e ligue 192. Cada minuto conta.' },
    { at: 57.0, text: 'Sangramento grave é emergência.' },
  ].map((l) => ({ ...VOICE, ...l }));

  const markers = { rua: 0, queda: S.queda[0], choque: S.choque[0], sede: S.sede[0], cerebro: S.cerebro[0], cut: { t: ev.cut, sync: 'av' }, fim: S.fim[0] };

  const SCORE = { FPS, FORMAT, W, H, SAFE, DURATION, clock, T, BEAT, S, m, chords, chordAt, beats, calm, ev, markers, bpmAt, prog, VO };
  if (node) module.exports = SCORE; else globalThis.SCORE = SCORE;
})();
