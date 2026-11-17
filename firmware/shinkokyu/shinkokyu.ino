// シン呼吸 ポータブル版の本体（H04：吐いている間だけ曲が進む、H05：ボタン）
// ボード：Seeed nRF52 Boards の「Seeed XIAO nRF52840」（B版の基板）
//
// - 気圧センサーで「吐く・止める・吸う」を見分け、吐いている間だけ曲が一定の速さで進む
// - 1フレーズは1回の吐く息の目安。息が止まったら音も止まり、次の息で続きから。吹き続ければ次のフレーズへ進む
// - 最後のフレーズを吹き終えたら、おりんが鳴り、その息が終わるまで待つ（次の息で曲の最初から）
// - 音のモード：笛（息の音とゆらぎ付き）／泡（煙の粒が消える「ポコッ」でメロディ）／オルゴール／効果音だけ（高さ一定の泡）
// - 息が弱まると音も小さくなる（止める瞬間に合わせて消えていく）。曲の進む速さは息の強さで変えない
// - ボタン（吹いている間は効かない）
//   SW1 短く：曲の最初から（試しに3秒鳴らす）。曲が2つ以上なら次の曲
//   SW1 長押し：一服のお誘い（S06）。PC に「INVITE」を送る。PC が通知を出し、本体と Sense 版の LED を紫に点滅させる
//   SW2・SW3：音量を上げる・下げる（8段階）
//   SW2＋SW3 同時押し：声を録る（PC に「TALK」を送る。PC が Sense 版のマイクで録り始め、もう一度で終わる。11/11）
//     Sense 版が眠っていたら起こすために、D6 に短い HIGH を出す（起きて PC とつながるまで数秒は PC のマイクで録る）
//   SW2 を1.2秒長押し：音のモードを切り替える（試しに3秒鳴らす）（11/11 に SW2＋SW3 同時押しから移した）
//   SW3 を3秒長押し：眠る（電源を切る代わり。「ぽっ、ぽっ」と赤い LED のあと、深い眠りへ）。どれかのボタンを押すと起きて、
//   最初から動く（起動の合図のおりんが鳴る）。USB をさしても起きる（11/09。電源スイッチがないため）
// - LED：吸っている間だけ火の色（11/13。曲が進むと 赤→橙→黄→白っぽい火 の4段。前は青）。同じ明るさを D6 から Sense 版へ出す（線1本で Sense 版の D0 へ）。お誘いが届いたら紫に点滅（PC から LIGHT）
// - シリアル（115200）と Bluetooth（名前 Shinkokyu-XXXX、Nordic UART）に、同じ行を出す（S01）
//   S dP=.. st=E/I/- ph= n= wait= mode= vol= song=   … 1秒に10回
//   START exhale / END exhale 3.2s peak=41.3 / RESET baseline / SONG done / MODE flute / VOLUME 5 / INVITE / TALK
//   NOTE 74（鳴らし始めた音の MIDI の番号。NOTE 0 は止めた）/ HELLO Shinkokyu-XXXX song=..（つながったとき）
// - PC から受け取る行：RESTART（曲を最初に戻す。煙の画面で「いっぱいにする」を押したときなど）／VOL 0〜10（音量。0 は音なし）／
//   LIGHT n（n 秒、紫に点滅する。お誘いが届いたしるし。LIGHT 0 で止める）
// - 曲のデータ（songs.h）は make_songs.py で songs/*.json から作る。SW1 を押すたびに次の曲へ（SONG restart 曲の名前）（11/12：2曲）

#include <Arduino.h>
#include <Wire.h>
#include "songs.h"
#include "dps368.h"
#include "breath.h"
#include "synth.h"
#include "blelink.h"

const int PIN_BTN[3] = {D0, D1, D2};  // 曲送り・音量＋・音量−
const int PIN_AMP_EN = D7;            // 高い＝アンプが動く
const uint32_t TICK_MS = 50;          // 息の判定は 50ms ごと（その間の気圧の平均で）
const int PIN_GLOW_OUT = D6;      // 息の明るさを Sense 版に伝える（11/10。J6 の D6 → Sense 版の D0）
const uint32_t LONG_MS = 800;         // 長押し
const uint32_t MODE_MS = 1200;        // SW2 をこれだけ押し続けると、音のモードを切り替える（11/11）
const uint32_t SLEEP_MS = 3000;       // SW3 をこれだけ押し続けると眠る（音量を下げるつもりの押し方と間違えないよう長め）
// 11/12：吸う方で使う（たばこのように、本体から吸っている間だけ曲が進む）。true＝吸う／false＝前の吹く方
//   気圧の値の向きを逆にして、息の見分け（breath.h）に渡す。こうすると「吸う」が今までの「吐く」と同じに扱われ、
//   見分け方・曲・LED・PC へ送る行（START exhale・S st=E・dP）はそのまま使える（行の「exhale」は「曲を進める息」の意味になる。今は吸う）
const bool SUCK_MODE = true;
// 息の強さと音の大きさ：BREATH_SOFT Pa で 0.3、BREATH_FULL Pa 以上で 1（強く吹いても、それ以上は大きくならない）
// 素の基板に吹いたときの値（10〜30Pa）に合わせた。筒ができたら見直す
const float BREATH_SOFT = 5.0f;
const float BREATH_FULL = 25.0f;

breath::Detector det;
bool dpsOk = false;
float paSum = 0;
int paN = 0;
int volume = 3;  // 0〜VOL_MAX。0 は音なし（息は今までどおり測る）（11/05：試している間は小さめに）
// 11/12：音量 9・10 を足した（もっと大きくしたい）。8 までは前と同じ大きさ。9 は 8 の約 1.4 倍、10 は約 2 倍。
// 8 でも音の出せる大きさの 4割ほどしか使っていなかった。重なって大きすぎる所は synth の出口でやわらかく抑える（割れにくい）
const int VOL_MAX = 10;
const float VOL_GAIN[VOL_MAX + 1] = {0.0f, 0.12f, 0.24f, 0.36f, 0.48f, 0.60f, 0.72f, 0.84f, 0.96f, 1.36f, 1.92f};
uint32_t lightUntil = 0;  // お誘いの紫の点滅を、いつまで続けるか

// シリアルと Bluetooth に同じ1行を出す
// 11/12 夜：I2C の線がとまったとき（センサーが途中で止まって SDA を下げたまま）に、SCL を9回たたいてほどき、Wire を始め直す
void i2cRecover() {
  Wire.end();
  pinMode(PIN_WIRE_SDA, INPUT_PULLUP);
  pinMode(PIN_WIRE_SCL, OUTPUT);
  for (int i = 0; i < 9 && digitalRead(PIN_WIRE_SDA) == LOW; i++) {
    digitalWrite(PIN_WIRE_SCL, LOW); delayMicroseconds(5);
    digitalWrite(PIN_WIRE_SCL, HIGH); delayMicroseconds(5);
  }
  pinMode(PIN_WIRE_SCL, INPUT_PULLUP);
  Wire.begin();
  Wire.setClock(400000);
}
// USB にだけ：I2C で返事をした番地を出す（例：I2C 0x77。何も返事がなければ I2C none。SDA が下がったままなら sda=0）
void i2cScan() {
  Serial.print("I2C");
  int n = 0;
  for (uint8_t a = 0x08; a < 0x78; a++) { Wire.beginTransmission(a); if (Wire.endTransmission() == 0) { Serial.print(" 0x"); Serial.print(a, HEX); n++; } }
  if (!n) Serial.print(" none");
  Serial.print(" sda=");
  Serial.println(digitalRead(PIN_WIRE_SDA));
}

void report(const char *line) {
  Serial.println(line);
  blelink::send(line);
}

// 小数1けたの文字にする（printf の %f は使えないことがあるため）
const char *fmt1(char *out, float v) {
  int x = (int)lroundf(v * 10);
  sprintf(out, "%s%d.%d", x < 0 ? "-" : "", abs(x) / 10, abs(x) % 10);
  return out;
}

// 青だけは明るさを変えられる（PWM）。XIAO の LED は LOW で光るので、255 − 明るさ を出す
void ledBlue(float v) {
  analogWrite(LED_BLUE, 255 - (int)(constrain(v, 0.0f, 1.0f) * 255));
}

// Sense 版へ息の明るさを送る（D6）。analogWrite は D6 で出なかった（11/10 に確かめた）ので、
// nRF52840 の PWM3 を直接使う：16MHz ÷ 16 ＝ 1MHz、250 で1周（4kHz）。Sense 版は D0 を何回も読んで HIGH の割合を明るさにする
static uint16_t glowSeq[1] = {0x8000};
void glowOutBegin() {
  pinMode(PIN_GLOW_OUT, OUTPUT);
  digitalWrite(PIN_GLOW_OUT, LOW);
  NRF_PWM3->PSEL.OUT[0] = g_ADigitalPinMap[PIN_GLOW_OUT];
  NRF_PWM3->PSEL.OUT[1] = 0xFFFFFFFF;
  NRF_PWM3->PSEL.OUT[2] = 0xFFFFFFFF;
  NRF_PWM3->PSEL.OUT[3] = 0xFFFFFFFF;
  NRF_PWM3->ENABLE = 1;
  NRF_PWM3->MODE = PWM_MODE_UPDOWN_Up;
  NRF_PWM3->PRESCALER = PWM_PRESCALER_PRESCALER_DIV_16;
  NRF_PWM3->COUNTERTOP = 250;
  NRF_PWM3->LOOP = 0;
  NRF_PWM3->DECODER = (PWM_DECODER_LOAD_Common << PWM_DECODER_LOAD_Pos) | (PWM_DECODER_MODE_RefreshCount << PWM_DECODER_MODE_Pos);
  NRF_PWM3->SEQ[0].PTR = (uint32_t)glowSeq;
  NRF_PWM3->SEQ[0].CNT = 1;
  NRF_PWM3->SEQ[0].REFRESH = 0;
  NRF_PWM3->SEQ[0].ENDDELAY = 0;
  NRF_PWM3->TASKS_SEQSTART[0] = 1;
}
void glowOutSet(float v) {
  static uint16_t last = 0xFFFF;
  uint16_t x = (uint16_t)(constrain(v, 0.0f, 1.0f) * 250);
  if (x == last) return;
  last = x;
  glowSeq[0] = x | 0x8000;  // 0x8000：値の間だけ HIGH（Adafruit の HardwarePWM と同じ向き）
  NRF_PWM3->TASKS_SEQSTART[0] = 1;  // 新しい値を読みこませる（最後の値を出し続ける）
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

// 11/13：曲の段（0〜3）。曲を4つに分けた今の場所（今の2曲は4フレーズなので、フレーズごとに1段）。最後まで吹いて待っている間は 3
int songStage() {
  const Song &sg = synth::song();
  if (synth::phraseDone) return 3;
  return constrain((int)synth::phraseIdx * 4 / max((int)sg.n, 1), 0, 3);
}

void setVolume(int v) {
  volume = constrain(v, 0, VOL_MAX);
  synth::gain = VOL_GAIN[volume];
  synth::reqBlip = true;
  char b[24];
  snprintf(b, sizeof(b), "VOLUME %d", volume);
  report(b);
}

void onRelease(int i, uint32_t heldMs) {
  if (synth::exhaling) {
    report("BUTTON ignored (blowing)");
    return;
  }
  if (i == 0) {
    if (SONG_COUNT > 1) synth::reqNextSong = true;
    else synth::reqRestart = true;
    char b[48];
    snprintf(b, sizeof(b), "SONG restart %s", SONGS[(synth::songIdx + (SONG_COUNT > 1 ? 1 : 0)) % SONG_COUNT].id);
    report(b);
  } else if (i == 1) {
    setVolume(volume + 1);
  } else {
    setVolume(volume - 1);
  }
}

// SW1 長押し：一服のお誘い。吹いている間でも送れる（音は変えない）
void onLongPress() {
  synth::reqBlip = true;  // 押せたしるしに「ポッ」
  report("INVITE");
}

// SW2＋SW3 同時押し：声を録る（始める・終わるの切り替えは PC がする）。吹いている間でも送れる
void onTalkCombo() {
  synth::reqBlip = true;  // 押せたしるしに「ポッ」
  report("TALK");
  // Sense 版が眠っていたら起こす：D6 を 30ms だけ HIGH（起きている Sense 版は一瞬青く光るだけ）
  uint16_t keep = glowSeq[0];
  glowSeq[0] = 250 | 0x8000;
  NRF_PWM3->TASKS_SEQSTART[0] = 1;
  delay(30);
  glowSeq[0] = keep;  // 元の明るさに戻す
  NRF_PWM3->TASKS_SEQSTART[0] = 1;
}

// SW2 を長押し：音のモードを切り替える
void onModeCombo() {
  if (synth::exhaling) return;
  synth::mode = (synth::mode + 1) % synth::MODE_COUNT;
  synth::reqRestart = true;
  char b[24];
  snprintf(b, sizeof(b), "MODE %s", synth::MODE_NAME[synth::mode]);
  report(b);
}

// SW3 を3秒長押し：深い眠り（nRF52840 の System OFF）。電池の減りは数µA ほどになる
// 起きるとリセットと同じで、setup() から始まる（音量・モードは最初の値に戻る）
void goToSleep() {
  report("SLEEP");
  // 眠るしるし：「ぽっ、ぽっ」と赤い LED（音量0でも LED で分かる）
  led(true, false, false);
  synth::reqBlip = true;
  delay(180);
  synth::reqBlip = true;
  delay(500);

  // ボタンを離すまで待つ（押したまま眠ると、すぐ起きてしまう）
  uint32_t t0 = millis();
  while (millis() - t0 < 10000) {
    bool any = false;
    for (int i = 0; i < 3; i++) any |= digitalRead(PIN_BTN[i]) == LOW;
    if (!any) break;
    delay(10);
  }
  delay(100);  // 離したときのチャタリングよけ
  led(false, false, false);

  // 電気を使う部品を止める
  digitalWrite(PIN_AMP_EN, LOW);  // アンプを止める（眠っている間も LOW のまま保たれる）
  delay(20);
  NVIC_DisableIRQ(I2S_IRQn);
  NRF_I2S->TASKS_STOP = 1;
  NRF_I2S->ENABLE = 0;
  if (dpsOk) dps::writeReg(0x08, 0x00);  // 気圧センサーを待機に
  // LED の PWM を止めて、ふつうの出力 HIGH（消える）にする。止めないと、眠っている間に LED が点いたままになることがある
  //   11/13：赤・緑も PWM にしたので、3色とも
  NRF_PWM0->ENABLE = 0;
  NRF_PWM1->ENABLE = 0;
  NRF_PWM2->ENABLE = 0;
  NRF_PWM3->ENABLE = 0;
  const int ledPins[3] = {LED_RED, LED_GREEN, LED_BLUE};
  for (int i = 0; i < 3; i++) {
    uint32_t pin = g_ADigitalPinMap[ledPins[i]];
    NRF_GPIO_Type *port = (pin >= 32) ? NRF_P1 : NRF_P0;
    port->OUTSET = 1UL << (pin & 31);
    port->PIN_CNF[pin & 31] = (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos) |
                              (GPIO_PIN_CNF_INPUT_Disconnect << GPIO_PIN_CNF_INPUT_Pos);
  }
  {  // Sense 版へ「眠る合図」（11/11）：D6 を HIGH・LOW と 3 回すばやく切り替える。Sense 版はこれを見て眠る
    NRF_PWM3->PSEL.OUT[0] = 0xFFFFFFFF;  // PWM から外して、ふつうの出力に
    pinMode(PIN_GLOW_OUT, OUTPUT);
    for (int i = 0; i < 3; i++) {
      digitalWrite(PIN_GLOW_OUT, HIGH);
      delay(150);
      digitalWrite(PIN_GLOW_OUT, LOW);
      delay(150);
    }
  }
  {  // Sense 版へ出している D6 も LOW に（Sense 版の青が消える）
    uint32_t pin = g_ADigitalPinMap[PIN_GLOW_OUT];
    NRF_GPIO_Type *port = (pin >= 32) ? NRF_P1 : NRF_P0;
    port->OUTCLR = 1UL << (pin & 31);
    port->PIN_CNF[pin & 31] = (GPIO_PIN_CNF_DIR_Output << GPIO_PIN_CNF_DIR_Pos) |
                              (GPIO_PIN_CNF_INPUT_Disconnect << GPIO_PIN_CNF_INPUT_Pos);
  }
  Serial.flush();

  // どのボタンでも起きるように：押されて LOW になったら起きる
  for (int i = 0; i < 3; i++) {
    uint32_t pin = g_ADigitalPinMap[PIN_BTN[i]];
    NRF_GPIO_Type *port = (pin >= 32) ? NRF_P1 : NRF_P0;
    port->PIN_CNF[pin & 31] = (GPIO_PIN_CNF_DIR_Input << GPIO_PIN_CNF_DIR_Pos) |
                              (GPIO_PIN_CNF_INPUT_Connect << GPIO_PIN_CNF_INPUT_Pos) |
                              (GPIO_PIN_CNF_PULL_Pullup << GPIO_PIN_CNF_PULL_Pos) |
                              (GPIO_PIN_CNF_SENSE_Low << GPIO_PIN_CNF_SENSE_Pos);
  }
  sd_power_system_off();  // Bluetooth（SoftDevice）を使っているので、こちらで眠る
  while (true) {
  }
}

void pollButtons(uint32_t now) {
  static uint32_t last = 0;
  static bool prev[3] = {false, false, false};
  static uint32_t pressMs[3] = {0, 0, 0};
  static bool longFired = false;
  static bool comboFired = false;  // SW2＋SW3 を同時に押した（離したときの音量の変更はしない）
  static bool modeFired = false;   // SW2 を長押しした（離したときの音量の変更はしない）
  if (now - last < 10) return;  // 10ms ごとに読む（チャタリングよけ）
  last = now;
  bool on[3];
  for (int i = 0; i < 3; i++) on[i] = digitalRead(PIN_BTN[i]) == LOW;
  // 起こすために押したボタンは、離すまで何もしない（起きたとたんに音量が下がる、などを防ぐ）
  static bool first = true;
  static bool wakeHeld[3] = {false, false, false};
  if (first) {
    first = false;
    for (int i = 0; i < 3; i++) prev[i] = wakeHeld[i] = on[i];
    return;
  }
  bool anyWake = false;
  for (int i = 0; i < 3; i++) {
    if (wakeHeld[i] && !on[i]) {
      wakeHeld[i] = false;
      prev[i] = false;
    }
    anyWake |= wakeHeld[i];
  }
  if (anyWake) return;
  if (on[1] && on[2] && !comboFired) {
    comboFired = true;
    onTalkCombo();
  }
  for (int i = 0; i < 3; i++) {
    if (on[i] && !prev[i]) {
      pressMs[i] = now;
      if (i == 0) longFired = false;
      if (i == 1) modeFired = false;
    }
    // SW2 だけを長押ししたら、音のモードを切り替える（SW3 と同時押しのときはしない）
    if (on[i] && i == 1 && !modeFired && !comboFired && now - pressMs[1] >= MODE_MS) {
      modeFired = true;
      onModeCombo();
    }
    if (on[i] && i == 0 && !longFired && now - pressMs[0] >= LONG_MS) {
      longFired = true;
      onLongPress();
    }
    // SW3 だけを3秒押し続けたら眠る（SW2 と同時押しのときと、吹いている間はしない）
    if (on[i] && i == 2 && !comboFired && !synth::exhaling && now - pressMs[2] >= SLEEP_MS) goToSleep();
    bool skip = (i == 0 && longFired) || (i > 0 && comboFired) || (i == 1 && modeFired);
    if (!on[i] && prev[i] && !skip) onRelease(i, now - pressMs[i]);
    prev[i] = on[i];
  }
  if (comboFired && !on[1] && !on[2]) comboFired = false;
}

void setup() {
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  glowOutBegin();
  led(false, false, false);
  for (int i = 0; i < 3; i++) pinMode(PIN_BTN[i], INPUT_PULLUP);
  pinMode(PIN_AMP_EN, OUTPUT);
  digitalWrite(PIN_AMP_EN, HIGH);

  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 2000) delay(10);
  Serial.println();
  Serial.println("=== shinkokyu (H04) ===");

  Wire.begin();  // D4=SDA、D5=SCL
  Wire.setClock(400000);
  dpsOk = dps::begin();
  Serial.println(dpsOk ? "DPS368: OK" : "DPS368: NG");

  blelink::begin();  // Bluetooth を先に始める（音の割り込みより前に）
  Serial.print("BLE: ");
  Serial.println(blelink::name);

  synth::gain = VOL_GAIN[volume];
  synth::begin();
  synth::reqBell = 0.4f;  // 起動の合図：おりんを小さく1回
  Serial.print("SONG ");
  Serial.print(SONGS[0].id);
  Serial.print(" MODE ");
  Serial.println(synth::MODE_NAME[synth::mode]);
}

void loop() {
  uint32_t now = millis();

  static uint32_t lastRead = 0, lastGood = millis(), lastRetry = millis(); // 起動の直後は、起動のときにつないだ結果をそのまま使う
  static uint16_t readsN = 0;   // USB の行に出す：0.1秒に読めた回数（ふつう 3〜4）
  if (dpsOk && now - lastRead >= 5) {
    lastRead = now;
    float p;
    if (dps::read(p)) {
      paSum += p;
      paN++;
      lastGood = now;
      readsN++;
    }
  }
  // 11/12 夜：2台目で、起動したときに気圧センサーが見つからず（DPS368: NG）、吸っても何も起きなかった。前は起動のときに1回しか
  //   つながず、見つからなければそのままだった → 見つからない・1秒値が来ないときは、2秒ごとにつなぎ直す。PC にも知らせる（SENSOR ok／ng）
  if ((!dpsOk || now - lastGood > 1000) && now - lastRetry > 2000) {
    lastRetry = now;
    static bool warned = false;
    if (!dpsOk) i2cRecover();   // 線が止まったまま（SDA が下がったまま）なら、ほどいてから
    bool ok = dps::begin();
    if (!ok) i2cScan();          // USB の行に、返事をした部品の番地を出す（センサーの線が外れているのか、番地がちがうのかを見分ける）
    if (ok) {
      if (!dpsOk || warned) report("SENSOR ok");
      dpsOk = true; warned = false; lastGood = now; det.reset();
    } else {
      dpsOk = false;
      if (!warned) { warned = true; report("SENSOR ng"); }
    }
  }

  static uint32_t lastTick = 0;
  if (now - lastTick >= TICK_MS) {
    lastTick = (now - lastTick > 5 * TICK_MS) ? now : lastTick + TICK_MS;
    if (paN > 0) {
      det.update(SUCK_MODE ? -(paSum / paN) : paSum / paN, now); // 吸う方：気圧が下がる向きを「曲を進める息」にする
      paSum = 0;
      paN = 0;
      if (det.evEnd) {
        char a[12], c[12], b[48];
        snprintf(b, sizeof(b), "END %s %ss peak=%s", det.endKind == breath::EXHALE ? "exhale" : "inhale",
                 fmt1(a, det.endSec), fmt1(c, det.endPeak));
        report(b);
      }
      if (det.evStart) report(det.startKind == breath::EXHALE ? "START exhale" : "START inhale");
      if (det.evReset) report("RESET baseline");
      bool ex = det.state == breath::EXHALE;
      float k = constrain((det.delta - BREATH_SOFT) / (BREATH_FULL - BREATH_SOFT), 0.0f, 1.0f);
      synth::breathLevel = 0.3f + 0.7f * k;
      synth::exhaling = ex;
      // 11/13 A：吸っている間は火の色。曲が進むと 赤 → 橙 → 黄 → 白っぽい火 の4段で変わる（フレーズごと）
      //   （白く瞬く「パチッ」「パパッ」は、いらないとのことで外した。11/13 昼）
      static float glow = 0;
      int shownStage = songStage();
      float target = ex ? 0.55f + 0.45f * k : 0.0f;  // 色がはっきり分かる明るさで光る（息が強いほど、少し明るく）
      glow += (target - glow) * (target > glow ? 0.5f : 0.25f);  // 明るくなるのは速く、消えるのはゆっくり
      if (glow < 0.01f) glow = 0;
      if (!ex && lightUntil && now < lightUntil) {  // お誘い：紫に点滅
        bool b = (now / 400) % 2 == 0;
        led(b, false, b);
      } else {
        if (!(lightUntil && now < lightUntil)) lightUntil = 0;
        float r, g, b;
        stageColor(shownStage, r, g, b);
        ledRGB(r * glow, g * glow, b * glow);
      }
      // Sense 版へ（D6 → Sense 版の D0、線1本）：HIGH の割合で伝える。0＝消える、0.10／0.30／0.50／0.70＝段 0〜3。
      //   0.95 以上は Sense 版が「眠る合図」と見分けるのに使っているので、ここでは出さない
      glowOutSet(glow > 0.02f ? 0.10f + 0.20f * shownStage : 0.0f);
    }
  }

  if (synth::songDone) {
    synth::songDone = false;
    report("SONG done");
  }

  static uint8_t lastMidi = 0;  // 鳴らす音が変わったら知らせる（S02：PC でも同じ音を鳴らすため）
  uint8_t m = synth::curMidi;
  if (m != lastMidi) {
    lastMidi = m;
    char b[16];
    snprintf(b, sizeof(b), "NOTE %d", m);
    report(b);
  }

  char cmd[48];  // PC からの頼みごと
  while (blelink::readLine(cmd, sizeof(cmd))) {
    if (!strcmp(cmd, "RESTART")) {
      synth::reqReset = true;
      report("SONG reset");
    } else if (!strncmp(cmd, "VOL ", 4)) {  // 画面の音量のつまみから
      setVolume(atoi(cmd + 4));
    } else if (!strncmp(cmd, "LIGHT ", 6)) {  // お誘いが届いた：n 秒、紫に点滅
      int sec = constrain(atoi(cmd + 6), 0, 60);
      lightUntil = sec ? millis() + sec * 1000UL : 0;
    }
  }

  static bool wasReady = false;  // PC がつながったら、名前と曲と設定を知らせる
  bool rdy = blelink::ready();
  if (rdy && !wasReady) {
    char b[80];
    snprintf(b, sizeof(b), "HELLO %s song=%s mode=%s vol=%d", blelink::name, SONGS[synth::songIdx].id,
             synth::MODE_NAME[synth::mode], volume);
    report(b);
    if (!dpsOk) report("SENSOR ng");  // 11/12 夜：つながったときに、センサーが動いていなければ知らせる
  }
  wasReady = rdy;

  pollButtons(now);

  static uint32_t lastPrint = 0;
  if (now - lastPrint >= 100) {  // 1秒に10回
    lastPrint = now;
    char st = det.state == breath::EXHALE ? 'E' : det.state == breath::INHALE ? 'I' : '-';
    char a[12], b[96];
    snprintf(b, sizeof(b), "S dP=%s st=%c ph=%d n=%d wait=%d mode=%s vol=%d song=%s", fmt1(a, det.delta), st,
             synth::phraseIdx + 1, synth::noteIdx + 1, synth::phraseDone ? 1 : 0, synth::MODE_NAME[synth::mode], volume,
             SONGS[synth::songIdx].id);  // 11/12：song＝今の曲（PC の画面が、曲を替えたのについていけるように）
    blelink::send(b);
    char c[12];  // USB にだけ、息の見分けの確かめ用の値（ゆれ・なめらかが続いた回数）も足す（11/11）
    Serial.print(b);
    Serial.print(" rg=");
    Serial.print(fmt1(c, det.rough));
    Serial.print(" calm=");
    Serial.print(det.calm);
    Serial.print(" dps=");      // 11/12 夜：気圧センサーがつながっているか（1/0）と、0.1秒に読めた回数
    Serial.print(dpsOk ? 1 : 0);
    Serial.print(" rd=");
    Serial.println(readsN);
    readsN = 0;
  }
}
