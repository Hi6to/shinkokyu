# 本体のプログラム

| フォルダ | 中身 |
|---|---|
| [board_check/](board_check/) | B版の基板の動作確認。LED の点滅、気圧センサーの値、ボタン、アンプの「ピッ」 |
| [shinkokyu/](shinkokyu/) | **本体のプログラム**。吐いている間だけ曲が進む（1フレーズ＝1回の息）。音は笛・泡・オルゴール・効果音の4つ（SW2＋SW3 の同時押しで切り替え）、SW1 短く＝曲の最初から、**SW1 長押し＝一服のお誘い**（PC に通知、本体と Sense 版の LED が紫に点滅。S06）、SW2・SW3＝音量。曲のデータ songs.h は `make_songs.py` で songs/*.json から作る |
| [sense_mic/](sense_mic/) | **Sense 版のマイクのプログラム（V02）**。PC から頼まれている間（または D1 につないだボタンを押している間）だけ声を録り、IMA ADPCM で 4分の1に縮めて、話しながら Bluetooth で PC に送る。名前は「ShinkokyuMic-XXXX」。ボードは「Seeed XIAO nRF52840 Sense」（`Seeeduino:nrf52:xiaonRF52840Sense`）。PC から「LIGHT n」で n 秒、紫に点滅する（一服のお誘いが届いたしるし） |
| [mic_check/](mic_check/) | Sense 版のマイクの確認。4秒録音して PC に送り、`record_wav.py` で WAV に保存して再生する。`transcribe.py` で文字にする（ボードは Seeed XIAO nRF52840 Sense） |

## 書き込みの準備（1回だけ）

- Arduino IDE 2 の「ボードマネージャ」に、Seeed の URL を足す：`https://files.seeedstudio.com/arduino/package_seeeduino_boards_index.json`
- **Seeed nRF52 Boards**（`Seeeduino:nrf52`、1.1.13 で確認）を入れる。「mbed-enabled」の方ではない
- ボードは **Seeed XIAO nRF52840**（Sense 版を使うときは Seeed XIAO nRF52840 Sense）

### Windows で「exit status 9009」が出るとき

コンパイルの最後に `python` を呼ぶ所で、Windows の「ストアへの案内」の python が先に見つかって止まる。どちらかで直る。

- Windows の設定 →「アプリ」→「アプリの詳細設定」→「アプリ実行エイリアス」で、python.exe と python3.exe をオフにする
- コマンドで書き込むときは、本物の Python を先に置く：`PATH="$LOCALAPPDATA/Python/bin:$PATH"`

## コマンドで書き込む（Claude Code が使う方法）

Arduino IDE の中の arduino-cli を使う（設定は IDE と同じファイル）。

```bash
CLI="$HOME/OneDrive/Desktop/Arduino IDE/resources/app/lib/backend/resources/arduino-cli.exe"
"$CLI" --config-file ~/.arduinoIDE/arduino-cli.yaml compile -b Seeeduino:nrf52:xiaonRF52840 firmware/board_check
"$CLI" --config-file ~/.arduinoIDE/arduino-cli.yaml upload -p COM8 -b Seeeduino:nrf52:xiaonRF52840 firmware/board_check
```

- COM の番号は `board list` で調べる。書き込むと番号が変わることがある
- 届いたときの XIAO には Sense 用のプログラムが入っていて、Sense と表示される（B版の XIAO は Sense ではない）

## 声を文字にする（PC の中の Whisper）

声は PC の外に出さず、faster-whisper で文字にする。OneDrive の外に専用の Python の場所を作って入れる。

```bash
py -m venv ~/venvs/shinkokyu-voice
~/venvs/shinkokyu-voice/Scripts/python -m pip install faster-whisper pyserial numpy
~/venvs/shinkokyu-voice/Scripts/python firmware/mic_check/transcribe.py voice.wav
```

- 初めて動かすとき、文字にするためのデータ（small、約480MB）をダウンロードする。途中で止まったら、`HF_HUB_DISABLE_XET=1` を付けてやり直す
- faster-whisper 1.2.1 と PyAV 19 は合わないので、`transcribe.py` は WAV を自分で読んで渡している
- Hi6to の PC（ARM の CPU）では、普通の PC 用（x64）の Python が Windows の置き換えで動く。4秒の声を約7秒で文字にできた

## 確認の記録

| 日付 | 基板 | 結果 |
|---|---|---|
| 2026/11/05 | 部品付き1枚目 | 書き込み OK／LED OK／ボタン3つ OK／気圧センサー OK（101,635Pa・20.3℃、吹かないときの揺れ ±1Pa、基板に直接息をかけて最大 +86Pa）。吹いたあと、吹いていないときの値が −3〜−12Pa ずれた（本番では基準を追いかける） |
| 2026/11/05 | 部品付き1枚目（スピーカーを J3 にはんだ付け） | アンプ OK：USB だけで「ピッ」が鳴る（約1000Hz・最大の約4分の1の音量）。音割れなし |
| 2026/11/05 | Sense 版の XIAO（USB だけ） | マイク OK：4秒の録音に 4003ms（1秒に16000回で正しい）。机に置いて 20〜30cm で話すと「あ、今喋ってます。聞こえてますか?」と正しく文字になった（7.6秒）。口を近づけて息が当たると、ゴーッという音になり、文字にならない。一度に 64KB 以上を送ると切れるので、4KB ずつ送る |
| 2026/11/05 | 部品付き2枚目 | 書き込み OK／ボタン3つ OK／気圧センサー OK（101,187Pa、吹いて最大 +79Pa）。温度は 33〜36℃（暖房を強くしていた。次に1枚目と並べて比べる）。アンプはスピーカーを付けてから |
| 2026/11/05 | 部品付き1枚目（shinkokyu） | 吹くと曲が進み、止めると止まる。アメイジング・グレイスに聞こえる。起動直後、最初の温度が出る前の気圧を基準にすると約1秒後に 17Pa 跳ねて「吐いた」と取り違えたので、温度を待ち、最初の1秒は使わないようにした。素の基板に吹くと息は 10〜30Pa（最大 52Pa）で揺れが大きく、止めたあとも 5〜6Pa が 0.5秒ほど残る。しきい値を上げると途中で切れるので、息が弱まると音も小さくなるようにした（「前より良い」）。4つの音を聞き比べて、**笛と泡**が好評 |
| 2026/11/06 | 部品付き2枚目（スピーカー付き） | 気圧センサーの確認用のプログラムが入ったままだったので、1枚目と同じ shinkokyu を書き込んだ（COM14）。笛のモード・音量3で動いている。Bluetooth の名前は基板ごとにちがう（Shinkokyu-XXXX） |
| 2026/11/06 | 部品付き2枚目（shinkokyu） | 音量を 0〜8 にした（0 は音なし。ボタン SW3 でも 0 まで下がる。息は今までどおり測る）。書き込み直して、PC のアプリから Bluetooth で「VOL 0」を送ると、本体から vol=0 が返ってきた。USB のケーブルからの命令は受けとらない（Bluetooth だけ）。1枚目はまだ前のプログラム（音量は1まで） |
| 2026/11/06 | 部品付き1枚目（shinkokyu） | 音量0を使える最新のプログラムを書き込んだ（COM8）。2枚とも同じプログラムになった |
| 2026/11/06 | Sense 版（sense_mic） | 書き込み OK（COM11）。PC のアプリの操作パネルから Bluetooth でつながった（ShinkokyuMic-0DC8、つなぐまで約3秒）。確かめ用の 440Hz の音を3秒送ると、ちょうど 440Hz で、抜けなし。マイクで3秒・10秒録っても抜けなし、「止めて」から最後まで届くのに 0.02〜0.09秒（話しながら送れている）。静かな部屋の雑音は rms 0.015（PC のマイクより大きい）ので、PC 側で「その場の雑音の3倍」を声の目安にした |
