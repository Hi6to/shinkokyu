"""Sense 版のマイクで録った声を WAV に保存して、PC で再生する（V01）

使い方：py record_wav.py [保存するファイル] [--no-play]
- Sense 版（mic_check を書き込んだもの）を USB でつないでおく
- 実行すると Sense 版の LED が青く3回点滅し、赤く光っている4秒だけ録音する
"""

import math
import struct
import sys
import time
import wave

import serial
import serial.tools.list_ports as list_ports

RATE = 16000
SENSE_PID = 0x8045  # Seeed XIAO nRF52840 Sense（B版の XIAO は 0x8044）


def highpass(x, fc=120.0):
    """低い音（ゴーッという音・息の風）を消す。2次のバターワース型"""
    w0 = 2 * math.pi * fc / RATE
    alpha = math.sin(w0) / (2 * 0.7071)
    cw = math.cos(w0)
    a0 = 1 + alpha
    b0, b1, b2 = (1 + cw) / 2 / a0, -(1 + cw) / a0, (1 + cw) / 2 / a0
    a1, a2 = -2 * cw / a0, (1 - alpha) / a0
    y = []
    x1 = x2 = y1 = y2 = 0.0
    for v in x:
        out = b0 * v + b1 * x1 + b2 * x2 - a1 * y1 - a2 * y2
        x2, x1, y2, y1 = x1, v, y1, out
        y.append(out)
    return y


def find_port():
    for p in list_ports.comports():
        if p.vid == 0x2886 and p.pid == SENSE_PID:
            return p.device
    sys.exit("Sense 版が見つからない（USB でつないで、mic_check を書き込んだか確かめる）")


def read_line(s, timeout):
    t0 = time.time()
    buf = b""
    while time.time() - t0 < timeout:
        c = s.read(1)
        if not c:
            continue
        if c == b"\n":
            return buf.decode("utf-8", "replace").strip()
        buf += c
    sys.exit("Sense 版から返事がない")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out_path = args[0] if args else "voice.wav"
    play = "--no-play" not in sys.argv

    port = find_port()
    s = serial.Serial(port, 115200, timeout=0.2)
    time.sleep(0.3)
    s.reset_input_buffer()
    print(f"{port} に録音の合図を送る（青く3回点滅 → 赤の4秒間に話す）")
    s.write(b"r")

    n = 0
    while True:
        line = read_line(s, 15)
        if line.startswith("LEVEL"):
            print("Sense 版で測った大きさ：", line)
        if line.startswith("AUDIO"):
            n = int(line.split()[1])
            break

    data = b""
    t0 = time.time()
    while len(data) < n * 2 and time.time() - t0 < 10:
        data += s.read(n * 2 - len(data))
    s.close()
    if len(data) < n * 2:
        sys.exit(f"データが途中で切れた（{len(data)} / {n * 2} バイト）")

    samples = list(struct.unpack(f"<{n}h", data))
    mean = sum(samples) / n
    samples = [v - mean for v in samples]  # マイクの直流分を引く
    samples = highpass(samples)  # マイクに入る低いゴーッという音を消す
    # 0.25秒ごとの大きさ（声が入ったところが大きくなる）
    step = RATE // 4
    rms = []
    for i in range(0, n, step):
        part = samples[i:i + step]
        rms.append((sum(v * v for v in part) / len(part)) ** 0.5)
    peak = max(abs(v) for v in samples)
    print("0.25秒ごとの大きさ：", " ".join(f"{r:.0f}" for r in rms))
    print(f"一番大きいところ：{peak:.0f}（最大 32767）")

    # 聞きやすい大きさにそろえる（一番大きいところを最大の約7割に）
    gain = 23000 / peak if peak > 0 else 1
    out = [int(max(-32768, min(32767, v * gain))) for v in samples]
    with wave.open(out_path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(struct.pack(f"<{n}h", *out))
    print(f"保存した：{out_path}（音量を {gain:.1f} 倍にした）")

    if play:
        import winsound
        print("PC のスピーカーで再生する")
        winsound.PlaySound(out_path, winsound.SND_FILENAME)


if __name__ == "__main__":
    main()
