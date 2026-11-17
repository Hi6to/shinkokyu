"""songs/*.json から、本体のプログラム用の songs.h を作る

使い方：py firmware/shinkokyu/make_songs.py
- 音名（例：G4、F#4、Bb4）を MIDI の番号にする。本体では1オクターブ上げて鳴らす（プログラムの側で +12）
- 拍数は4倍して整数にする（0.25拍まで表せる）
- 曲の順番はファイル名の順（本体の SW1 を押すたびに、この順に替わる。起動したときは1曲目）
- PC のアプリ用に、同じ順番の曲の一覧 songs/index.json も作る（11/12）
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
SONGS = ROOT / "songs"
OUT = pathlib.Path(__file__).resolve().parent / "songs.h"

NOTE = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def midi(name):
    n = NOTE[name[0]]
    rest = name[1:]
    while rest and rest[0] in "#b":
        n += 1 if rest[0] == "#" else -1
        rest = rest[1:]
    return n + 12 * (int(rest) + 1)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    files = sorted(f for f in SONGS.glob("*.json") if f.name != "index.json")
    lines = [
        "// songs/*.json から make_songs.py で作ったファイル。手で直さない",
        "#pragma once",
        "#include <stdint.h>",
        "",
        "struct Note { uint8_t midi; uint8_t q; };  // q = 拍数×4",
        "struct Phrase { const Note *notes; uint8_t n; };",
        "struct Song { const char *id; uint16_t bpm; const Phrase *phrases; uint8_t n; };",
        "",
    ]
    song_rows = []
    ids = []
    for f in files:
        song = json.loads(f.read_text(encoding="utf-8"))
        sid = song["id"]
        ids.append(sid)
        phrase_rows = []
        for i, phrase in enumerate(song["phrases"]):
            notes = []
            for name, beats in phrase:
                q = round(beats * 4)
                assert abs(q - beats * 4) < 1e-6 and 0 < q < 256, (f.name, name, beats)
                notes.append(f"{{{midi(name)}, {q}}}")
            lines.append(f"const Note {sid}_p{i}[] = {{{', '.join(notes)}}};")
            phrase_rows.append(f"{{{sid}_p{i}, {len(phrase)}}}")
        lines.append(f"const Phrase {sid}_phrases[] = {{{', '.join(phrase_rows)}}};")
        lines.append("")
        song_rows.append(f'{{"{sid}", {song["bpm"]}, {sid}_phrases, {len(phrase_rows)}}}')
        print(f"{f.name}：{song['title']}（{len(phrase_rows)}フレーズ、bpm {song['bpm']}）")
    lines.append(f"const Song SONGS[] = {{{', '.join(song_rows)}}};")
    lines.append(f"const int SONG_COUNT = {len(song_rows)};")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print(f"書いた：{OUT}")
    index = SONGS / "index.json"
    index.write_text(json.dumps({"songs": ids}, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"書いた：{index}")


if __name__ == "__main__":
    main()
