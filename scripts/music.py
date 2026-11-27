"""Original instrumental score generator (royalty-free, synthesised from scratch).

Each chapter gets a mood (piano + strings pad + optional pulse/percussion); cues are crossfaded
into one continuous track. No third-party/copyrighted music is used.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import fftconvolve, butter, sosfilt

SR = 44100
NOTE = {n: i for i, n in enumerate(["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"])}


def hz(name: str) -> float:
    n, o = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((NOTE[n] + 12 * (o + 1) - 69) / 12)


def chord(root: str, quality: str, octave: int) -> list[float]:
    r = NOTE[root] + 12 * (octave + 1)
    iv = {"maj": [0, 4, 7], "min": [0, 3, 7], "sus2": [0, 2, 7], "maj7": [0, 4, 7, 11], "min7": [0, 3, 7, 10], "add9": [0, 4, 7, 14]}[quality]
    return [440.0 * 2 ** ((r + i - 69) / 12) for i in iv]


MOODS = {
    #            bpm  progression (root, quality)                                   pulse  perc   bright
    "opening":  (70, [("D", "maj"), ("A", "maj"), ("B", "min"), ("G", "maj")],      "arp8", False, 0.8),
    "formal":   (64, [("G", "maj"), ("E", "min"), ("C", "maj"), ("D", "sus2")],     "arp4", False, 0.6),
    "bright":   (96, [("A", "maj"), ("E", "maj"), ("F#", "min"), ("D", "maj")],     "pluck8", True, 1.0),
    "progressive": (100, [("E", "min7"), ("C", "maj7"), ("G", "maj"), ("D", "add9")], "tick16", True, 0.9),
    "triumph":  (76, [("C", "maj"), ("G", "maj"), ("A", "min"), ("F", "maj")],      "arp8", "timp", 1.0),
    "warm":     (62, [("F", "maj"), ("C", "maj"), ("D", "min"), ("A#", "maj")],     "arp4", False, 0.55),
    "closing":  (68, [("D", "maj"), ("A", "maj"), ("B", "min"), ("G", "maj")],      "arp4", False, 0.7),
}


def env(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def pad(freqs, dur, bright):
    n = int(dur * SR)
    t = np.arange(n) / SR
    out = np.zeros((n, 2))
    for f in freqs:
        for det, pan in ((-0.25, 0.3), (0.25, 0.7)):
            ff = f * 2 ** (det / 100 * 4)
            sig = np.zeros(n)
            for h in range(1, 6):
                sig += np.sin(2 * np.pi * ff * h * t + h) * (bright ** (h - 1)) / h ** 1.6
            out[:, 0] += sig * (1 - pan)
            out[:, 1] += sig * pan
    out *= env(n, min(1.6, dur * 0.4), min(1.6, dur * 0.4))[:, None]
    trem = 1 + 0.05 * np.sin(2 * np.pi * 0.2 * t)
    return out * trem[:, None] / (len(freqs) * 2.5)


def piano(f, dur, vel=1.0, bright=0.8):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.zeros(n)
    for h in range(1, 9):
        fh = f * h * (1 + 0.0004 * h * h)
        sig += np.sin(2 * np.pi * fh * t) * (bright ** (h - 1)) / h ** 1.2 * np.exp(-t * (1.2 + 0.7 * h))
    sig *= 1 - np.exp(-t * 400)
    return sig * vel * 0.35


def pluck(f, dur, vel=1.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(4 * np.pi * f * t) + 0.15 * np.sin(6 * np.pi * f * t)) * np.exp(-t * 7)
    return sig * (1 - np.exp(-t * 600)) * vel * 0.25


def bass(f, dur):
    n = int(dur * SR)
    t = np.arange(n) / SR
    sig = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(4 * np.pi * f * t)
    return sig * env(n, 0.05, 0.4) * np.exp(-t * 0.6) * 0.32


def kick():
    t = np.arange(int(0.35 * SR)) / SR
    f = 45 + 75 * np.exp(-t * 25)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9) * 0.45


def hat(rng):
    t = np.arange(int(0.06 * SR)) / SR
    x = rng.standard_normal(len(t))
    x = sosfilt(butter(2, 7000, "hp", fs=SR, output="sos"), x)
    return x * np.exp(-t * 70) * 0.05


def timp():
    t = np.arange(int(1.6 * SR)) / SR
    return (np.sin(2 * np.pi * 73 * t) + 0.5 * np.sin(2 * np.pi * 110 * t)) * np.exp(-t * 2.5) * 0.35


def add(buf, sig, start, gain=1.0, pan=0.5):
    i = int(start * SR)
    if i >= len(buf):
        return
    sig = sig[: len(buf) - i]
    if sig.ndim == 1:
        buf[i:i + len(sig), 0] += sig * gain * (1 - pan) * 2 ** 0.5
        buf[i:i + len(sig), 1] += sig * gain * pan * 2 ** 0.5
    else:
        buf[i:i + len(sig)] += sig * gain


def cue(mood: str, dur: float, seed: int = 0, intensity_curve=True) -> np.ndarray:
    bpm, prog, pulse, perc, bright = MOODS[mood]
    rng = np.random.default_rng(seed)
    beat = 60 / bpm
    bar = beat * 4
    buf = np.zeros((int((dur + 3) * SR), 2))
    nb = int(np.ceil(dur / bar)) + 1
    for b in range(nb):
        t0 = b * bar
        if t0 > dur + 1:
            break
        root, q = prog[b % len(prog)]
        build = min(1.0, 0.45 + 0.55 * (t0 / max(dur, 1))) if intensity_curve else 1.0
        add(buf, pad(chord(root, q, 3), bar + 1.5, bright), t0, 0.55 * (0.7 + 0.3 * build))
        add(buf, bass(chord(root, q, 1)[0], bar), t0, 0.9)
        notes = chord(root, q, 4) + [chord(root, q, 5)[0]]
        if pulse == "arp8":
            for k in range(8):
                f = notes[[0, 1, 2, 3, 2, 1, 2, 3][k] % len(notes)]
                add(buf, piano(f, 2.2, 0.55 + 0.2 * (k % 4 == 0), bright), t0 + k * beat / 2, 0.8 * build, pan=0.35 + 0.3 * (k % 2))
        elif pulse == "arp4":
            for k in range(4):
                f = notes[[0, 2, 1, 3][k] % len(notes)]
                add(buf, piano(f, 3.0, 0.6, bright), t0 + k * beat, 0.85, pan=0.4 + 0.2 * (k % 2))
            if b % 2 == 1:
                mel = chord(root, q, 5)
                add(buf, piano(mel[rng.integers(0, len(mel))], 3.5, 0.45, bright), t0 + beat * 2.5, 0.7, pan=0.6)
        elif pulse == "pluck8":
            for k in range(8):
                f = notes[[0, 2, 1, 3, 0, 2, 3, 1][k] % len(notes)]
                add(buf, pluck(f, 0.6, 0.7 + 0.3 * (k % 2 == 0)), t0 + k * beat / 2, 0.9 * build, pan=0.3 + 0.4 * (k % 2))
            if b % 2 == 0:
                add(buf, piano(chord(root, q, 5)[1], 2.5, 0.5, bright), t0 + beat * 1.5, 0.6)
        elif pulse == "tick16":
            for k in range(16):
                f = notes[(k * 3) % len(notes)] * 2
                add(buf, pluck(f, 0.25, 0.45 + 0.3 * (k % 4 == 0)), t0 + k * beat / 4, 0.55 * build, pan=0.2 + 0.6 * ((k // 2) % 2))
        if perc is True:
            for k in range(4):
                add(buf, kick(), t0 + k * beat, 0.55 * build)
                add(buf, hat(rng), t0 + k * beat + beat / 2, 1.0 * build, pan=0.65)
        elif perc == "timp" and b % 2 == 0:
            add(buf, timp(), t0, 0.8 * build)
    return buf[: int(dur * SR)]


def reverb(x: np.ndarray, seconds=2.4, wet=0.22) -> np.ndarray:
    rng = np.random.default_rng(7)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t * 3.2)[:, None]
    ir = sosfilt(butter(2, 5000, "lp", fs=SR, output="sos"), ir, axis=0)
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    out = np.empty_like(x)
    for c in range(2):
        out[:, c] = fftconvolve(x[:, c], ir[:, c])[: len(x)]
    return x * (1 - wet) + out * wet * 1.4


def score(cues: list[tuple[float, float, str]], total: float, xfade=2.5) -> np.ndarray:
    """cues: (start, duration, mood). Returns stereo float32 track of `total` seconds, peak-normalised."""
    out = np.zeros((int((total + 1) * SR), 2))
    for i, (st, du, mood) in enumerate(cues):
        seg = cue(mood, du + xfade, seed=i)
        n = len(seg)
        fi, fo = int(xfade * SR), int(xfade * SR)
        e = np.ones(n)
        if i > 0:
            e[:fi] = np.linspace(0, 1, fi) ** 0.5
        e[-fo:] = np.linspace(1, 0, fo) ** 0.5
        a = int(max(0.0, st - (xfade if i > 0 else 0)) * SR)
        seg = seg[: max(0, len(out) - a)]
        out[a:a + len(seg)] += seg * e[: len(seg), None]
    out = reverb(out)[: int(total * SR)]
    out /= np.max(np.abs(out)) + 1e-9
    return (out * 0.89).astype(np.float32)
