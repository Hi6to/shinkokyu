"""声を文字にする係（デスクトップアプリが動かしたままにする）

- PC の中の faster-whisper で文字にする。声は PC の外に出ない
- 1行ずつ JSON で頼みを受けとり、1行ずつ JSON で答える（毎回モデルを読みこまずにすむように）
    受けとる：{"id": 1, "wav": "C:/.../voice.wav"}   … 16kHz・16bit・1チャンネルの WAV
    答える　：{"id": 1, "text": "…", "sec": 0.8}  /  {"ready": true, "sec": 2.1}  /  {"id": 1, "error": "…"}
- 使い方：<Whisper 用の Python> stt_worker.py [--model base] [--beam 1]
- base・探し方1通りで、4秒の声を約1.1秒で文字にする（small だと約4秒。11/06 に Hi6to の PC で測った）
"""

import json
import os
import sys
import time
import wave

import numpy as np
from faster_whisper import WhisperModel


def read_wav(path):
    """16kHz・16bit・1チャンネルの WAV を読む（faster-whisper の読みこみ部品は版が合わないことがあるため）"""
    with wave.open(path) as w:
        assert w.getframerate() == 16000 and w.getsampwidth() == 2 and w.getnchannels() == 1, "16kHz・16bit・1ch の WAV だけ"
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return x.astype(np.float32) / 32768


def denoise(x, n=512, hop=128):
    """雑音を消す（スペクトルの引き算）：静かな方から2割の所の音を「雑音の型」として、各周波数からその分を差し引く。
    基板のマイクで、はなれて話すと、声と雑音の差が小さくなるため"""
    if len(x) < n * 8:
        return x
    win = np.hanning(n).astype(np.float32)
    frames = 1 + (len(x) - n) // hop
    idx = np.arange(n)[None, :] + hop * np.arange(frames)[:, None]
    spec = np.fft.rfft(x[idx] * win, axis=1)
    mag = np.abs(spec)
    energy = mag.mean(axis=1)
    noise = np.median(mag[energy <= np.percentile(energy, 20)], axis=0)
    gain = np.clip(1.0 - 1.5 * noise / (mag + 1e-9), 0.1, 1.0)  # 引きすぎないよう、0.1 は残す
    gain = (gain + np.vstack([gain[:1], gain[:-1]]) + np.vstack([gain[1:], gain[-1:]])) / 3  # 時間の向きに少しならす（ピロピロ音を減らす）
    out = np.fft.irfft(spec * gain, n=n, axis=1) * win
    y = np.zeros(len(x), dtype=np.float32)
    wsum = np.zeros(len(x), dtype=np.float32)
    for i in range(frames):
        y[i * hop:i * hop + n] += out[i]
        wsum[i * hop:i * hop + n] += win * win
    y /= np.maximum(wsum, 1e-6)
    peak = np.abs(y).max()
    return y * (0.9 / peak) if peak > 0 else y


def say(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stdin.reconfigure(encoding="utf-8")
    model_name = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "base"
    beam = int(sys.argv[sys.argv.index("--beam") + 1]) if "--beam" in sys.argv else 1
    # 11/15：CPU のスレッド数。faster-whisper は何も言わないと4本しか使わない。この PC はもっと多いので、8本まで使う（--threads で変えられる）
    threads = int(sys.argv[sys.argv.index("--threads") + 1]) if "--threads" in sys.argv else min(8, os.cpu_count() or 4)
    t0 = time.time()
    models = {model_name: WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=threads)}
    say({"ready": True, "sec": round(time.time() - t0, 1), "model": model_name, "threads": threads})
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        req = {}
        try:
            req = json.loads(line)
            name = req.get("model") or model_name  # 頼みごとにモデルを変えられる（比べるとき）。はじめて使うモデルはここで読みこむ
            if name not in models:
                models[name] = WhisperModel(name, device="cpu", compute_type="int8", cpu_threads=threads)
            model = models[name]
            t0 = time.time()
            # 職場の愚痴を話す前提。言いよどみも、そのまま文字にしてよい（短い言葉にする係が整える）
            x = read_wav(req["wav"])
            if req.get("denoise"):
                x = denoise(x)
            # hotwords：よく出る言葉のヒント（「仕様変更」が「使用変更」になる、などを防ぐ）
            segments, _ = model.transcribe(x, language="ja", beam_size=beam, vad_filter=req.get("vad", True),
                                           without_timestamps=True, condition_on_previous_text=False,
                                           hotwords=req.get("hotwords") or None)
            segs = list(segments)
            text = "".join(s.text for s in segs).strip()
            # 自信の目安：文字の長さで重みをつけた平均の対数確率（0 に近いほど自信がある）
            n = sum(max(1, len(s.text)) for s in segs)
            logprob = round(sum(s.avg_logprob * max(1, len(s.text)) for s in segs) / n, 2) if segs else None
            say({"id": req.get("id"), "text": text, "sec": round(time.time() - t0, 2), "model": name,
                 "denoise": bool(req.get("denoise")), "hotwords": bool(req.get("hotwords")), "logprob": logprob})
        except Exception as e:  # 1回失敗しても、係は動き続ける
            say({"id": req.get("id"), "error": str(e)})


if __name__ == "__main__":
    main()
