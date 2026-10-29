"""Score and mix for the story video, generated in numpy (no samples, no licences). 48 kHz stereo.

usage: mix.py <work dir> voice    assembles the narration from voice/s_*.wav -> voice_raw.wav (mono)
       mix.py <work dir> final    music + processed narration (voice_fx.wav) -> mix_raw.wav, amp.json
Both read starts.json (scene starts from the page) and voice/timeline.json (sentence offsets).

The music follows the story: a dark drone while the NPU waits, an impact when MIRA appears, a pulse while it
answers, a breakdown for the proof, the full groove for the CPU and the question series, calm for "offline", a last
impact on the end card. (Same score as the Lumen video, so the two belong together.)
"""
import json
import sys

import numpy as np
import soundfile as sf

d, mode = sys.argv[1], sys.argv[2]
SR = 48000
o = json.load(open(f"{d}/starts.json"))
starts, total, ids = o["starts"], o["total"], o["ids"]
tl = json.load(open(f"{d}/voice/timeline.json"))
N = int((total + 1) * SR)
sx = lambda s: int(s * SR)  # noqa: E731

if mode == "voice":
    v = np.zeros(N)
    for i, sc in enumerate(tl):
        for j, (off, _) in enumerate(sc["sent"]):
            a, _ = sf.read(f"{d}/voice/s_{i:02d}_{j:02d}.wav")
            k = sx(starts[i] + off)
            v[k:k + len(a)] += a[:N - k]
    sf.write(f"{d}/voice_raw.wav", v.astype(np.float32), SR)
    print("voice track ok")
    sys.exit()

rng = np.random.default_rng(5)
t = np.arange(N) / SR
hz = lambda m: 440.0 * 2 ** ((m - 69) / 12)  # noqa: E731
beat = 60 / 100
bar = 4 * beat
S = lambda i: starts[min(i, len(starts) - 1)]  # noqa: E731
I = ids.index                           # scene index by id, so new scenes do not shift the score


def lp(x, fc, order=2):
    """Zero-phase low-pass in the frequency domain (offline rendering)."""
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(np.fft.rfft(x) / np.sqrt(1 + (f / fc) ** (2 * order)), len(x))


def hp(x, fc, order=2):
    f = np.fft.rfftfreq(len(x), 1 / SR)
    return np.fft.irfft(np.fft.rfft(x) / np.sqrt(1 + (fc / np.maximum(f, 1)) ** (2 * order)), len(x))


def saw(freq, n, phase0=0.0):
    """Band-limited sawtooth (polyBLEP)."""
    dt = freq / SR
    p = (phase0 + dt * np.arange(n)) % 1.0
    y = 2 * p - 1
    a = p < dt
    x = p[a] / dt
    y[a] -= 2 * x - x * x - 1
    b = p > 1 - dt
    x = (p[b] - 1) / dt
    y[b] -= x * x + 2 * x + 1
    return y


def place(buf, k, x):
    if k >= len(buf) or k + len(x) <= 0:
        return
    if k < 0:
        x, k = x[-k:], 0
    buf[k:k + len(x)] += x[:len(buf) - k]


def window(a, b):
    """1 from scene a to scene b, with soft edges."""
    e = np.zeros(N)
    e[sx(S(a)):sx(S(b)) if b < len(starts) else N] = 1
    return lp(e, 2)


pad, sub, bass, drums, arp, fx = (np.zeros(N) for _ in range(6))
CH = [[45, 57, 60, 64, 71], [41, 57, 60, 64, 69], [48, 55, 60, 62, 67], [43, 55, 59, 62, 64]]  # Am9 Fmaj7 Cadd9 G6
t0 = S(I('mira'))
chord_at = lambda s: CH[int(max(0, s - t0) / (bar * 2)) % 4]  # noqa: E731

# act 1: a low drone while the NPU waits
n1 = sx(S(I('mira')) + 1)
drone = sum(saw(hz(m) * (1 + dt), n1, rng.random()) for m in (33, 40, 45) for dt in (-0.003, 0.0, 0.004))
lfo = 0.5 + 0.5 * np.sin(2 * np.pi * 0.07 * t[:n1])
drone = lp(drone * 0.05, 220) * (0.6 + 0.4 * lfo) * np.minimum(1, t[:n1] / 5) * np.clip((S(I('mira')) + 0.6 - t[:n1]) / 1.2, 0, 1)
place(pad, 0, drone)
place(fx, 0, hp(rng.standard_normal(n1), 6000) * 0.006 * (0.5 + 0.5 * np.sin(2 * np.pi * 0.11 * t[:n1]))
      * np.clip((S(I('mira')) - t[:n1]) / 1.5, 0, 1))

# pads from MIRA on: detuned saws through a slowly breathing filter, wide open for the question series
seg = bar * 2
for c0 in np.arange(t0, total, seg):
    ch = chord_at(c0 + 0.01)
    n = sx(seg + 2.5)
    tt = np.arange(n) / SR
    x = sum(saw(hz(m) * (1 + dt), n, rng.random()) for m in ch[1:] for dt in (-0.006, -0.002, 0.003, 0.007))
    fc = 3200 if S(I('series')) <= c0 < S(I('offline')) else 900 + 1800 * (0.5 + 0.5 * np.sin(2 * np.pi * (c0 - t0) / 60))
    env = np.minimum(1, tt / 1.2) * np.clip((seg + 2.5 - tt) / 2.5, 0, 1)
    place(pad, sx(c0), lp(x, fc) * 0.012 * env)
    place(sub, sx(c0), np.sin(2 * np.pi * hz(ch[0] - 12) * tt) * 0.05 * env)
bass += sub * window(I('read'), I('work'))

# drums and off-beat bass while MIRA works; breakdown for the proof, calm for "offline"
groove = [(I('ask'), I('proof'), 1.0), (I('cpu-free'), I('offline'), 1.0), (I('work'), I('end'), 0.7)]
kt = np.arange(sx(0.45)) / SR
kick = np.sin(2 * np.pi * np.cumsum(45 + 110 * np.exp(-kt * 32)) / SR) * np.exp(-kt * 7)
kick[:sx(0.004)] += hp(rng.standard_normal(sx(0.004)), 2000) * 0.3
kick = np.tanh(kick * 1.6) * 0.55
hat = hp(rng.standard_normal(sx(0.06)), 7500) * np.exp(-np.arange(sx(0.06)) / SR * 70) * 0.11
ohat = hp(rng.standard_normal(sx(0.25)), 6500) * np.exp(-np.arange(sx(0.25)) / SR * 14) * 0.07
clap = sum(np.roll(lp(hp(rng.standard_normal(sx(0.22)), 900), 5000) * np.exp(-np.arange(sx(0.22)) / SR * 22), sx(k * 0.011))
           for k in range(3)) * 0.12
side = np.ones(N)                       # sidechain: pads and bass dip with every kick
for a, b, lvl in groove:
    for k, c0 in enumerate(np.arange(S(a), S(b), beat)):
        place(drums, sx(c0), kick * lvl)
        place(side, sx(c0), -0.55 * lvl * np.exp(-np.arange(sx(0.3)) / SR * 9))
        place(drums, sx(c0 + beat / 2), ohat * lvl)
        for q in (0.25, 0.75):
            place(drums, sx(c0 + beat * q), hat * lvl * (0.7 + 0.3 * rng.random()))
        if a >= I('cpu-free') and k % 2 == 1:
            place(drums, sx(c0), clap * lvl)
        ch = chord_at(c0 + 0.01)
        n = sx(beat * 0.45)
        tt = np.arange(n) / SR
        place(bass, sx(c0 + beat / 2), lp(saw(hz(ch[0] - 12), n) + 0.5 * saw(hz(ch[0]) * 1.002, n), 700) * np.exp(-tt * 6) * 0.11 * lvl)

# plucked arpeggio with a ping-pong delay
pat = [0, 2, 1, 3, 2, 4, 3, 1]
for k, c0 in enumerate(np.arange(t0 + bar, S(I('end')) + bar, beat / 2)):
    if S(I('offline')) <= c0 < S(I('work')):
        continue
    ch = chord_at(c0 + 0.01)
    m = ch[1 + pat[k % 8] % 4] + 12
    n = sx(0.35)
    tt = np.arange(n) / SR
    place(arp, sx(c0), lp(saw(hz(m), n) + 0.3 * saw(hz(m) * 2.001, n), 2600) * np.exp(-tt * 11) * 0.05 * (0.55 if c0 < S(I('ask')) else 1.0))
dly = sx(beat * 0.75)
arpL, arpR = arp.copy(), arp * 0.6
for r in range(1, 5):
    (arpR if r % 2 else arpL)[dly * r:] += arp[:-dly * r] * 0.38 ** r

# risers and impacts: MIRA, the race (or the speed), the question series, the end card
for ci in (I('mira'), I('race') if 'race' in ids else I('speed'), I('series'), I('end')):
    j = sx(S(ci))
    n = sx(2.2)
    tt = np.arange(n) / SR
    noise = hp(rng.standard_normal(n), 300) * (tt / 2.2) ** 3 * 0.06
    place(fx, j - n, lp(noise, 1500) + hp(noise, 4000) * 0.5)
    n = sx(4.5)
    tt = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(32 + 60 * np.exp(-tt * 9)) / SR) * np.exp(-tt * 1.4) * 0.5
    place(fx, j, np.tanh(boom * 1.5) * 0.6 + lp(hp(rng.standard_normal(n), 3000), 12000) * np.exp(-tt * 2.2) * 0.05)


def reverb(x, secs, seed):
    """Stereo-decorrelated exponential noise tail."""
    r = np.random.default_rng(seed)
    n = sx(secs)
    ir = lp(r.standard_normal(n), 6000) * np.exp(-np.arange(n) / SR * 6.9 / secs)
    ir[:sx(0.012)] = 0
    m = len(x) + n
    return np.fft.irfft(np.fft.rfft(x, m) * np.fft.rfft(ir, m), m)[:len(x)] * 0.03


padw = pad * side
dry = padw + bass * side + drums + fx
L = dry + arpL + reverb(padw + arpL + fx * 0.5, 3.2, 1)
R = dry + arpR + reverb(padw + arpR + fx * 0.5, 3.2, 2)
L[sx(0.011):] += padw[:-sx(0.011)] * 0.25   # small Haas offset widens the pad
R += padw * 0.25

# a licensed track can replace the generated score: video/music.(wav|mp3|flac), converted by make.ps1 to music_ext.wav
try:
    ext, _ = sf.read(f"{d}/music_ext.wav")
    ext = ext if ext.ndim > 1 else np.stack([ext, ext], 1)
    ext = np.tile(ext, (N // len(ext) + 1, 1))[:N]
    L, R = ext[:, 0].copy(), ext[:, 1].copy()
    print("using the external music track")
except (FileNotFoundError, RuntimeError):
    pass

# narration on top; the music steps back while she speaks
v, _ = sf.read(f"{d}/voice_fx.wav")
v = v.mean(axis=1) if v.ndim > 1 else v
v = np.pad(v, (0, max(0, N - len(v))))[:N]
# level the stems: the music bed sits 12 dB under the speech level, and 19 dB under it while she speaks (ducking)
sp = np.abs(v) > 0.01
v_rms = np.sqrt(np.mean(v[sp] ** 2)) if sp.any() else 0.1
m_rms = np.sqrt(np.mean(((L + R) / 2)[sx(S(I('mira'))):] ** 2))
L, R = (x * v_rms * 10 ** (-12 / 20) / m_rms for x in (L, R))
duck = 1 - 0.55 * np.clip(lp(np.abs(v), 4) * 12, 0, 1)
mus = np.minimum(1, t / 2) * np.clip((total + 0.5 - t) / 3.5, 0, 1) * duck
mix = np.tanh(np.stack([L * mus + v, R * mus + v], 1) / 0.9) * 0.9   # soft clip; loudnorm follows in ffmpeg
sf.write(f"{d}/mix_raw.wav", mix.astype(np.float32), SR)
fr = SR // 30
amp = [float(np.sqrt(np.mean(v[k:k + fr] ** 2))) for k in range(0, N, fr)]
mx = max(amp) or 1
json.dump([min(255, int(a / mx * 1.6 * 255)) for a in amp], open(f"{d}/amp.json", "w"))
print("mix ok", round(N / SR, 1), "s")
