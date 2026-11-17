"""録った声（WAV）を、PC の中の Whisper で文字にする（V01・V03 の試し）

使い方：<Whisper 用の Python> transcribe.py <WAV ファイル> [...] [--model small]
- 声は PC の外に出ない（faster-whisper を PC の中で動かす）
- 初めて動かすときに、文字にするためのデータ（small で約500MB）をダウンロードする
"""

import sys
import time
import wave

import numpy as np
from faster_whisper import WhisperModel


def read_wav(path):
    """16kHz・16bit・1チャンネルの WAV を読む（faster-whisper の読み込み部品は版が合わないことがあるため）"""
    with wave.open(path) as w:
        assert w.getframerate() == 16000 and w.getsampwidth() == 2 and w.getnchannels() == 1
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    return x.astype(np.float32) / 32768


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    model_name = "small"
    if "--model" in args:
        i = args.index("--model")
        model_name = args[i + 1]
        del args[i:i + 2]

    t0 = time.time()
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    print(f"準備：{time.time() - t0:.1f}秒（モデル {model_name}）")

    for path in args:
        t0 = time.time()
        segments, info = model.transcribe(read_wav(path), language="ja", beam_size=5)
        text = "".join(s.text for s in segments)
        print(f"{path}：「{text}」（{time.time() - t0:.1f}秒）")


if __name__ == "__main__":
    main()
