// Sense 版のマイク（V02）：頼まれている間だけ声を録り、Bluetooth で PC に送る
// - 名前は「ShinkokyuMic-XXXX」（本体の「Shinkokyu-XXXX」と見分ける）。Nordic UART Service（NUS）を使う
// - 録る：PC から「REC 1」（PC の「押している間 話す」・Ctrl+Alt+M）か、D1 につないだボタンを押している間。30秒で自動で止まる（11/06：20秒だとゆっくり話すと足りなかった）
// - 送る：16kHz・16bit の声を IMA ADPCM で 4bit に縮め（1秒に約8KB）、話しながら少しずつ送る
// - 送る形（バイトの並び。1つの「まとまり」＝ A5 5A・種類・長さ（2バイト）・中身）
//     1 はじめ：1秒の回数（2バイト）・縮め方（1＝IMA ADPCM）・きっかけ（0＝PC・1＝ボタン）
//     2 声　　：番号（2バイト）・その時点の予測値（2バイト）・段（1バイト）・400サンプル分の 4bit（200バイト）
//     3 おわり：最後の番号（2バイト）・理由（0＝止めた・1＝30秒・2＝つながりが切れた）・取りこぼしたサンプル数（4バイト）
// - PC から受けとる行：REC 1／REC 0（録る・止める）、TONE 1／TONE 0（確かめ用：マイクの代わりに 440Hz の音を送る）、GAIN n、
//   LIGHT n（n 秒、紫に点滅する。本体の長押しで一服のお誘いが届いたしるし。LIGHT 0 で止める）
// - LED：緑＝PC とつながっている、赤＝録っている、紫の点滅＝お誘いが届いた、火の色＝本体で吸っている（11/13：本体と同じ色。曲が進むと 赤→橙→黄→白っぽい火 の4段。前は青。本体の D6 → この D0 の線1本）
// - 眠る（11/11）：電池を本体と分け合っているので、使っていない間は深く眠って電池を守る
//     ① 本体が眠るとき、D6 を HIGH・LOW と 3 回すばやく切り替える（眠る合図）→ これを見たら、すぐ眠る
//     ② PC とつながっていない・光っていない・録っていない・ボタンも押されていない、が 3 分続いたら眠る
//   起きる：本体で吹く（D0 が HIGH）か、話すボタン（D1）を押す。起きると最初から動き直す（PC とはつなぎ直し）
//   起きた直後に 15 秒何もなければ（本体の眠る合図で起きてしまったときなど）、すぐ眠り直す
// ボード：Seeed nRF52 Boards の「Seeed XIAO nRF52840 Sense」
#include <Arduino.h>
#include <PDM.h>
#include <bluefruit.h>
#include "adpcm.h"

const int RATE = 16000;
const int BLOCK = 400;           // 1つの「声」のまとまり＝400サンプル（25ms）
const uint32_t MAX_MS = 30000;   // 30秒で自動で止まる
const int BUTTON_PIN = D1;       // 話すボタン（D1 と GND の間。なくてもよい）
int micGain = 0x40;              // 0x28 が 0dB、1増えるごとに +0.5dB。0x40 で +12dB（V01 と同じ）

BLEUart uart;
char devName[24];
volatile bool connected = false;

// ---------------- マイク → 輪のような入れ物（割り込みで入れて、loop で取りだす） ----------------
const int RING = 8192;  // 0.5秒ぶん
int16_t ring[RING];
volatile uint32_t wr = 0, rd = 0, dropped = 0;
volatile bool recording = false;
bool testTone = false;
int16_t pdmTmp[512];

void onPDMdata() {
  int bytes = PDM.available();
  PDM.read(pdmTmp, bytes);
  if (!recording) return;
  int n = bytes / 2;
  for (int i = 0; i < n; i++) {
    if (wr - rd >= RING) { dropped++; continue; }  // 送るのが追いつかない
    ring[wr % RING] = pdmTmp[i];
    wr++;
  }
}

// 青だけは明るさを変えられる（PWM）。XIAO の LED は LOW で光るので、255 − 明るさ を出す
void ledBlue(float v) {
  analogWrite(LED_BLUE, 255 - (int)(constrain(v, 0.0f, 1.0f) * 255));
}

// 11/13：赤・緑も明るさを変えられるように（火の色を出すため）。3色とも PWM。XIAO の LED は LOW で光るので、255 − 明るさ
void ledRGB(float r, float g, float b) {
  analogWrite(LED_RED, 255 - (int)(constrain(r, 0.0f, 1.0f) * 255));
  analogWrite(LED_GREEN, 255 - (int)(constrain(g, 0.0f, 1.0f) * 255));
  ledBlue(b);
}
void led(bool r, bool g, bool b) { ledRGB(r ? 1.0f : 0.0f, g ? 1.0f : 0.0f, b ? 1.0f : 0.0f); }

// 11/13 改：火の色は4段（なだらかに変えると、変わったのが分からなかった）。0 赤 → 1 橙 → 2 黄 → 3 白っぽい火
void stageColor(int st, float &r, float &g, float &b) {
  static const float C[4][3] = {{1.0f, 0.0f, 0.0f}, {1.0f, 0.22f, 0.0f}, {1.0f, 0.65f, 0.0f}, {1.0f, 0.9f, 0.55f}};
  st = constrain(st, 0, 3);
  r = C[st][0]; g = C[st][1]; b = C[st][2];
}

// ---------------- LED の点滅（お誘いが届いた） ----------------
uint32_t lightUntil = 0;
void updateLight() {
  if (recording) return;  // 録っている間は赤のまま
  static bool lit = false;
  if (lightUntil && millis() < lightUntil) {
    bool on = (millis() / 400) % 2 == 0;
    if (on != lit) { lit = on; led(on, false, on); }  // 紫（赤＋青）
  } else if (lightUntil) {
    lightUntil = 0; lit = false; led(false, connected, false);
  }
}

// ---------------- 眠る（11/11） ----------------
const int GLOW_PIN_SLEEP = D0;          // 本体の D6 から来る線（GLOW_PIN と同じ）
const uint32_t IDLE_SLEEP_MS = 180000;  // 何もしていないのが 3 分続いたら眠る
const uint32_t WAKE_IDLE_MS = 15000;    // 起きた直後だけは 15 秒
uint32_t idleLimit = IDLE_SLEEP_MS;
uint32_t lastActive = 0;
void markActive() {
  lastActive = millis();
  idleLimit = IDLE_SLEEP_MS;
}

void gpioSense(int arduinoPin, uint32_t pull, uint32_t sense) {
  uint32_t pin = g_ADigitalPinMap[arduinoPin];
  NRF_GPIO_Type *port = (pin >= 32) ? NRF_P1 : NRF_P0;
  port->PIN_CNF[pin & 31] = (GPIO_PIN_CNF_DIR_Input << GPIO_PIN_CNF_DIR_Pos) |
                            (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) |
                            (pull << GPIO_PIN_CNF_PULL_Pos) | (sense << GPIO_PIN_CNF_SENSE_Pos);
}

void goToSleep() {
  Serial.println("SLEEP");
  Serial.flush();
  PDM.end();  // マイクを止める
#ifdef PIN_PDM_PWR
  pinMode(PIN_PDM_PWR, OUTPUT);  // マイクの電源も切る
  digitalWrite(PIN_PDM_PWR, LOW);
#endif
  sd_clock_hfclk_release();
  // LED を消す（PWM を止めて、ふつうの出力 HIGH に）
  NRF_PWM0->ENABLE = 0;
  NRF_PWM1->ENABLE = 0;
  NRF_PWM2->ENABLE = 0;
  NRF_PWM3->ENABLE = 0;
  const int leds[3] = {LED_RED, LED_GREEN, LED_BLUE};
  for (int i = 0; i < 3; i++) {
    uint32_t pin = g_ADigitalPinMap[leds[i]];
    NRF_GPIO_Type *port = (pin >= 32) ? NRF_P1 : NRF_P0;
    port->OUTSET = 1UL << (pin & 31);
    port->PIN_CNF[pin & 31] = (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos) |
                              (GPIO_PIN_CNF_INPUT_Disconnect << GPIO_PIN_CNF_INPUT_Pos);
  }
  // 話すボタンを離すまで待つ（押したまま眠ると、すぐ起きてしまう）
  uint32_t t0 = millis();
  while (digitalRead(BUTTON_PIN) == LOW && millis() - t0 < 10000) delay(10);
  delay(50);
  // 起きるきっかけ：本体で吹いて D0 が HIGH になる・話すボタンで D1 が LOW になる
  gpioSense(GLOW_PIN_SLEEP, GPIO_PIN_CNF_PULL_Pulldown, GPIO_PIN_CNF_SENSE_High);
  gpioSense(BUTTON_PIN, GPIO_PIN_CNF_PULL_Pullup, GPIO_PIN_CNF_SENSE_Low);
  sd_power_system_off();
  while (true) {
  }
}

// ---------------- 息に合わせて青く光る（11/10）：updateLight の後ろに置く ----------------
// 本体の D6 から、本体の青と同じ明るさの信号（PWM）が線1本で D0 に来る。何回も読んで「HIGH の割合」＝明るさにする
const int GLOW_PIN = D0;
float glow = 0;
bool glowShown = false;
void updateGlow() {
  static uint32_t last = 0;
  if (millis() - last < 10) return;  // 1秒に100回
  last = millis();
  int hi = 0;
  const int N = 300;
  for (int i = 0; i < N; i++) {  // 本体の PWM と周期がそろわないよう、待つ時間を少しずつ変える
    hi += digitalRead(GLOW_PIN);
    delayMicroseconds(1 + (i * 7) % 5);
  }
  float v = (float)hi / N;
  // 本体の「眠る合図」：0.1秒以上の全部 HIGH から全部 LOW へ、40ms 以内に落ちるのが 2 秒の間に 3 回（息ではこんなに速く消えない）
  //   本体の「声を録る」で起こすための短い HIGH（30ms）は数えない（11/11）
  static bool sawHigh = false;
  static uint32_t highStart = 0, highAt = 0, firstFallAt = 0;
  static int falls = 0;
  if (v >= 0.95f) {
    if (!sawHigh) highStart = millis();
    sawHigh = true;
    highAt = millis();
  } else if (v <= 0.05f && sawHigh) {
    sawHigh = false;
    if (millis() - highAt <= 40 && highAt - highStart >= 100) {
      if (falls == 0 || millis() - firstFallAt > 2000) {
        falls = 0;
        firstFallAt = millis();
      }
      if (++falls >= 3) goToSleep();
    }
  }
  glow += (v - glow) * 0.5f;
  if (glow < 0.02f) glow = 0;
  bool busy = recording || (lightUntil && millis() < lightUntil);  // 録っている間（赤）とお誘い（紫）が先
  if (busy) { glowShown = false; return; }
  if (glow > 0) {
    markActive();
    // 11/13：本体と同じ火の色で光る。線の値の意味（本体が決める）：0.10／0.30／0.50／0.70＝段 0〜3（赤・橙・黄・白っぽい火）、0.80 以上＝パチッ（瞬き）
    //   明るさまでは線1本で送れないので、明るさは一定（BR）
    float r, g, b;
    if (v >= 0.80f) { r = 1.0f; g = 1.0f; b = 1.0f; }
    else {
      const float BR = 0.8f;
      stageColor((int)((v - 0.10f) / 0.20f + 0.5f), r, g, b);  // 今読んだ値で段を決める（なめらかにした値だと、段の間の色を通ってしまう）
      r *= BR; g *= BR; b *= BR;
    }
    ledRGB(r, g, b);
    glowShown = true;
  } else if (glowShown) {
    glowShown = false;
    led(false, connected, false);  // 吹き終わったら、つながっているしるし（緑）に戻す
  }
}

// ---------------- 送る ----------------
uint8_t frame[8 + 5 + BLOCK / 2];
void sendFrame(uint8_t type, const uint8_t *body, int len) {
  if (!connected || !uart.notifyEnabled()) return;
  frame[0] = 0xA5; frame[1] = 0x5A; frame[2] = type; frame[3] = len & 0xFF; frame[4] = len >> 8;
  memcpy(frame + 5, body, len);
  uart.write(frame, 5 + len);  // 1回で送れる長さに分けて送る（空くまで待つ）
}

adpcm::State st;
uint16_t seq = 0;
int32_t dc = 0;             // 直流のずれ（マイクの「0」の位置）。256倍の大きさで持つ
uint32_t recStart = 0;
uint8_t startedBy = 0;
float tonePhase = 0;

void startRec(uint8_t by) {
  if (recording || !connected) return;
  noInterrupts(); wr = rd = 0; dropped = 0; interrupts();
  st = adpcm::State(); seq = 0; recStart = millis(); startedBy = by; tonePhase = 0;
  uint8_t b[4] = {(uint8_t)(RATE & 0xFF), (uint8_t)(RATE >> 8), 1, by};
  sendFrame(1, b, 4);
  recording = true;
  led(true, false, false);
}

void flushBlocks(bool all) {
  uint8_t body[5 + BLOCK / 2];
  while ((wr - rd) >= (uint32_t)BLOCK || (all && wr != rd)) {
    int n = min((uint32_t)BLOCK, wr - rd);
    body[0] = seq & 0xFF; body[1] = seq >> 8;
    body[2] = (uint16_t)(int16_t)st.pred & 0xFF; body[3] = (uint16_t)(int16_t)st.pred >> 8; body[4] = st.index;
    memset(body + 5, 0, BLOCK / 2);
    for (int i = 0; i < n; i++) {
      int32_t x = ring[rd % RING]; rd++;
      if (testTone) { x = (int32_t)(8000 * sinf(tonePhase)); tonePhase += 2 * PI * 440 / RATE; if (tonePhase > 2 * PI) tonePhase -= 2 * PI; }
      else { dc += ((x << 8) - dc) >> 10; x -= dc >> 8; } // 直流（マイクの「0」のずれ）をゆっくり追いかけて引く（約2.5Hz より下を消す）
      if (x > 32767) x = 32767;
      if (x < -32768) x = -32768;
      uint8_t code = adpcm::encode((int16_t)x, st);
      body[5 + i / 2] |= (i & 1) ? (code << 4) : code;  // 前のサンプルが下の 4bit
    }
    sendFrame(2, body, 5 + (n + 1) / 2);
    seq++;
  }
}

void stopRec(uint8_t reason) {
  if (!recording) return;
  recording = false;
  flushBlocks(true);
  uint32_t d = dropped;
  uint16_t last = seq ? seq - 1 : 0;
  uint8_t b[7] = {(uint8_t)(last & 0xFF), (uint8_t)(last >> 8), reason, (uint8_t)d, (uint8_t)(d >> 8), (uint8_t)(d >> 16), (uint8_t)(d >> 24)};
  sendFrame(3, b, 7);
  led(false, connected, false);
}

void onConnect(uint16_t) { connected = true; led(false, true, false); }
void onDisconnect(uint16_t, uint8_t) { connected = false; if (recording) { recording = false; } led(false, false, false); }

bool readLine(char *out, int size) {
  static char buf[32];
  static int n = 0;
  while (uart.available()) {
    char c = uart.read();
    if (c == 10 || c == 13) {
      if (n == 0) continue;
      buf[n] = 0; strncpy(out, buf, size - 1); out[size - 1] = 0; n = 0;
      return true;
    }
    if (n < (int)sizeof(buf) - 1) buf[n++] = c;
  }
  return false;
}

void setup() {
  pinMode(LED_RED, OUTPUT); pinMode(LED_GREEN, OUTPUT); pinMode(LED_BLUE, OUTPUT);
  led(false, false, false);
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  pinMode(GLOW_PIN, INPUT_PULLDOWN);  // 線が外れていても光らない
  Serial.begin(115200);

  Bluefruit.autoConnLed(false);
  Bluefruit.configPrphBandwidth(BANDWIDTH_MAX);  // 1回で長く送れるようにする（MTU 247）
  Bluefruit.begin();
  Bluefruit.setTxPower(4);
  snprintf(devName, sizeof(devName), "ShinkokyuMic-%04X", (unsigned)(NRF_FICR->DEVICEADDR[0] & 0xFFFF));
  Bluefruit.setName(devName);
  Bluefruit.Periph.setConnInterval(6, 12);
  Bluefruit.Periph.setConnectCallback(onConnect);
  Bluefruit.Periph.setDisconnectCallback(onDisconnect);
  uart.begin();
  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(uart);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);
  sd_clock_hfclk_request();  // マイクの 16kHz を正確に保つ

  PDM.onReceive(onPDMdata);
  if (!PDM.begin(1, RATE)) {
    Serial.println("PDM: NG（マイクが動かない）");
    while (1) { led(true, false, false); delay(200); led(false, false, false); delay(200); }
  }
  PDM.setGain(micGain);
  Serial.print("HELLO "); Serial.println(devName);
  markActive();
  // 眠りから起きた：何もなければすぐ眠り直す。Bluetooth（SoftDevice）を始めたあとは NRF_POWER を直接さわると止まるので、sd_ を使う（11/11）
  uint32_t why = 0;
  sd_power_reset_reason_get(&why);
  if (why & POWER_RESETREAS_OFF_Msk) idleLimit = WAKE_IDLE_MS;
  sd_power_reset_reason_clr(0xFFFFFFFF);  // 理由を消しておく（次に起きたとき見分けるため）
}

void loop() {
  char cmd[32];
  while (readLine(cmd, sizeof(cmd))) {
    if (!strcmp(cmd, "REC 1")) startRec(0);
    else if (!strcmp(cmd, "REC 0")) stopRec(0);
    else if (!strcmp(cmd, "TONE 1")) testTone = true;
    else if (!strcmp(cmd, "TONE 0")) testTone = false;
    else if (!strncmp(cmd, "GAIN ", 5)) { micGain = constrain(atoi(cmd + 5), 0, 0x50); PDM.setGain(micGain); }
    else if (!strncmp(cmd, "LIGHT ", 6)) { int sec = constrain(atoi(cmd + 6), 0, 60); lightUntil = sec ? millis() + sec * 1000UL : 1; } // 0 は「すぐ止める」
  }
  updateLight();
  updateGlow();
  // 話すボタン（押している間だけ録る）
  static bool lastBtn = false;
  static uint32_t btnAt = 0;
  bool btn = digitalRead(BUTTON_PIN) == LOW;
  if (btn != lastBtn && millis() - btnAt > 30) {
    lastBtn = btn; btnAt = millis();
    if (btn) startRec(1); else if (startedBy == 1) stopRec(0);
  }
  if (recording) {
    flushBlocks(false);
    if (millis() - recStart > MAX_MS) stopRec(1);
  }
  if (!connected && recording) stopRec(2);
  // 眠る：PC とつながっていない・録っていない・光っていない・ボタンもお誘いもない、が続いたら
  if (connected || recording || lastBtn || (lightUntil && millis() < lightUntil)) markActive();
  if (millis() - lastActive > idleLimit) goToSleep();
}
