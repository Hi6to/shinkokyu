// Sense 版のマイクの確認（V01）
// - PC から「r」を受け取ると、LED が青く3回点滅（準備）→ 赤く光っている4秒だけ録音する
// - 録った声を PC に送る。PC 側は record_wav.py で WAV に保存して再生する
// - 送る形：「LEVEL ...」の行 →「AUDIO <サンプル数>」の行 → 16bit のデータ →「END」の行
// ボード：Seeed nRF52 Boards の「Seeed XIAO nRF52840 Sense」

#include <Arduino.h>
#include <PDM.h>

const int RATE = 16000;        // 1秒に16000回（声を文字にするには十分）
const int SECS = 4;            // 録音する秒数
const int N = RATE * SECS;     // 64000サンプル＝128KB（RAM に入る）
const int MIC_GAIN = 0x40;     // 0x28 が 0dB、1増えるごとに +0.5dB。0x40 で +12dB

int16_t rec[N];
volatile int recPos = 0;
volatile bool recording = false;
int16_t tmp[512];

void onPDMdata() {
  int bytes = PDM.available();
  PDM.read(tmp, bytes);
  if (!recording) return;
  int n = bytes / 2;
  for (int i = 0; i < n && recPos < N; i++) rec[recPos++] = tmp[i];
  if (recPos >= N) recording = false;
}

void led(bool r, bool g, bool b) {  // XIAO の LED は LOW で光る
  digitalWrite(LED_RED, r ? LOW : HIGH);
  digitalWrite(LED_GREEN, g ? LOW : HIGH);
  digitalWrite(LED_BLUE, b ? LOW : HIGH);
}

void setup() {
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  led(false, false, false);

  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 3000) delay(10);
  Serial.println();
  Serial.println("=== mic_check (Sense) ===");

  PDM.onReceive(onPDMdata);
  if (!PDM.begin(1, RATE)) {
    Serial.println("PDM: NG（マイクが動かない）");
    while (1) {
      led(true, false, false);
      delay(200);
      led(false, false, false);
      delay(200);
    }
  }
  PDM.setGain(MIC_GAIN);
  Serial.println("PDM: OK。r を送ると録音する");
  led(false, true, false);  // 緑＝待っている
}

void loop() {
  if (!Serial.available()) return;
  if (Serial.read() != 'r') return;

  for (int i = 0; i < 3; i++) {  // 準備：青く3回点滅（約3秒）
    led(false, false, true);
    delay(500);
    led(false, false, false);
    delay(500);
  }

  led(true, false, false);  // 赤＝録音中
  recPos = 0;
  uint32_t tStart = millis();
  recording = true;
  while (recording) delay(1);
  uint32_t tRec = millis() - tStart;  // 4000ms 前後なら、1秒に16000回で録れている
  led(false, true, false);

  // 音の大きさ（PC 側でも計算するが、ここでも出しておく）
  int64_t sum = 0;
  for (int i = 0; i < N; i++) sum += rec[i];
  int32_t mean = sum / N;
  int32_t peak = 0;
  double sq = 0;
  for (int i = 0; i < N; i++) {
    int32_t v = rec[i] - mean;
    if (abs(v) > peak) peak = abs(v);
    sq += (double)v * v;
  }
  Serial.print("LEVEL mean=");
  Serial.print(mean);
  Serial.print(" peak=");
  Serial.print(peak);
  Serial.print(" rms=");
  Serial.print(sqrt(sq / N), 1);
  Serial.print(" ms=");
  Serial.println(tRec);

  Serial.print("AUDIO ");
  Serial.println(N);
  // 一度に 64KB 以上を送ると後ろが切れるので、4KB ずつ送る
  const uint8_t *p = (const uint8_t *)rec;
  for (int sent = 0; sent < N * 2; sent += 4096) {
    Serial.write(p + sent, min(4096, N * 2 - sent));
  }
  Serial.println();
  Serial.println("END");
}
