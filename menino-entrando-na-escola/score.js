// A SCORE — primeiro dia de aula. Fonte única de verdade para música E imagem.
(function () {
  const node = typeof require !== 'undefined';
  const U = node ? require('./engine/util') : globalThis.U;
  const MU = node ? require('./engine/music') : globalThis.MUSIC;
  const { m, makeClock, placeBar, makeChords } = MU;

  const FPS = 30;
  const FORMAT = U.pickFormat('16:9');
  const [W, H] = U.formatSize(FORMAT);
  const SAFE = U.safeArea(W, H);
  const WIDE = W / H > 1.2;
  const clock = makeClock({ bpm: 100, offset: 0.5 }); // 1 beat = 0.6s, 1 bar = 2.4s
  const { T, BEAT } = clock;
  const DURATION = T(10) + 2;

  const S = {
    sunrise: [0, T(2)],
    walk: [T(2), T(5, 2)],
    wave: [T(5, 2), T(7)],
    enter: [T(7), T(9)],
    outro: [T(9), DURATION],
  };

  const { chords, chordAt } = makeChords(clock, {
    C: { notes: ['G3', 'C4', 'E4'], bass: 'C2' },
    G: { notes: ['G3', 'B3', 'D4'], bass: 'G1' },
    Am: { notes: ['A3', 'C4', 'E4'], bass: 'A1' },
    F: { notes: ['A3', 'C4', 'F4'], bass: 'F1' },
    Cmaj: { notes: ['G3', 'C4', 'E4', 'B4'], bass: 'C2' },
  }, [
    [0, 0, 4, 'C'], [1, 0, 4, 'G'],
    [2, 0, 4, 'Am'], [3, 0, 4, 'F'], [4, 0, 4, 'C'], [5, 0, 4, 'G'],
    [6, 0, 4, 'Am'], [7, 0, 4, 'F'], [8, 0, 4, 'C'],
    [9, 0, 4, 'Cmaj'], [10, 0, 4, 'Cmaj'],
  ]);

  // melodia (grade de colcheias): [nota, início, duração]
  const HOOK = {
    a: [['E5', 0, 2], ['G5', 2, 1], ['E5', 3, 1], ['D5', 4, 2], ['C5', 6, 2]],
    b: [['D5', 0, 2], ['E5', 2, 1], ['D5', 3, 1], ['B4', 4, 2], ['G4', 6, 2]],
    c: [['A4', 0, 2], ['C5', 2, 1], ['E5', 3, 1], ['A5', 4, 2], ['G5', 6, 2]],
    d: [['F5', 0, 2], ['E5', 2, 1], ['D5', 3, 1], ['C5', 4, 4]],
    e: [['E5', 0, 2], ['E5', 2, 1], ['G5', 3, 1], ['C6', 4, 4]],
  };

  const ev = {
    walkStart: T(2),
    stop: T(5, 2),     // chega ao portão e para
    waveEnd: T(7),
    bell: T(7),        // o sinal toca
    doorOpen: T(7),    // a porta abre junto com o sinal
    enterStart: T(7, 2),
    enterEnd: T(8, 3),
    end: T(9),
  };
  const GATE = 0.57; // fração da largura onde o menino para (x = W*GATE)

  // caixinha de música no amanhecer; marimba durante a caminhada
  const musicbox = [...placeBar(clock, HOOK.a, 0, 12), ...placeBar(clock, HOOK.b, 1, 12), { t: T(9), dur: 3, midi: m('C6') }];
  const melody = [
    ...placeBar(clock, HOOK.a, 2), ...placeBar(clock, HOOK.b, 3),
    ...placeBar(clock, HOOK.c, 4), ...placeBar(clock, HOOK.d, 5),
    ...placeBar(clock, HOOK.a, 6), ...placeBar(clock, HOOK.b, 7),
    ...placeBar(clock, HOOK.e, 8),
  ];
  // passos: um por meio-compasso de caminhada, sincronizados com o pulso
  const steps = [];
  for (let t = ev.walkStart; t < ev.stop - 0.01; t += BEAT) steps.push(t);
  const bells = [0, 0.4, 0.8, 1.2, 1.6, 2.0].map((d) => ev.bell + d); // sino da escola

  const markers = {
    sunrise: T(1),
    walk: ev.walkStart,
    gate: ev.stop,
    bell: { t: ev.bell, sync: 'av' }, // sino + porta abre
    enter: ev.enterStart,
    end: ev.end, // título final (surge em fade: sem sync)
  };

  const captions = [
    { t: T(0, 3), end: T(1, 3.5), text: 'Primeiro dia de aula!', x: WIDE ? 640 : SAFE.x + 20, y: WIDE ? 140 : SAFE.y + 40, rot: -0.03, size: 78 },
    { t: ev.stop + 0.3, end: ev.bell - 0.2, text: 'Tchau, mãe!', x: WIDE ? 560 : SAFE.x + 20, y: WIDE ? 230 : SAFE.y + 40, rot: 0.03, size: 64 },
  ];
  const endText = { words: [{ w: 'Bom', t: T(9, 0), d: 0.4 }, { w: 'dia,', t: T(9, 1), d: 0.4 }, { w: 'escola!', t: T(9, 2), d: 0.55 }], sub: { t: T(9, 3), text: 'a aventura começa agora' } };

  const SCORE = { FPS, FORMAT, W, H, SAFE, WIDE, DURATION, clock, T, BEAT, S, m, chords, chordAt, HOOK, ev, GATE, markers, musicbox, melody, steps, bells, captions, endText };
  if (node) module.exports = SCORE; else globalThis.SCORE = SCORE;
})();
