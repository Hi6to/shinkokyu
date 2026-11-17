// B版の基板の動作確認（H01〜H03）
// - LED：赤→緑→青の順に点滅（プログラムが動いている印）
// - 気圧センサー DPS368（I2C 0x77）：気圧と、起動時からの差をシリアルに出す
// - アンプ MAX98357A（I2S）：起動時と、ボタンを押したときに「ピッ」と鳴らす
// - ボタン SW1〜SW3（D0〜D2）：押されたらシリアルに出す
// ボード：Seeed nRF52 Boards の「Seeed XIAO nRF52840」

#include <Arduino.h>
#include <Wire.h>

// ---------- ピン ----------
const int PIN_BTN[3] = {D0, D1, D2};  // 曲送り・音量＋・音量−
const int PIN_AMP_EN = D7;            // 高い＝アンプが動く、低い＝止まる
const uint8_t DPS_ADDR = 0x77;

// ---------- DPS368 ----------
// 係数（データシートの「Calibration Coefficients」）
int32_t c0, c1, c00, c10, c01, c11, c20, c21, c30;
const float KP = 7864320.0f;  // 8回の平均（PM_PRC=3）のときの倍率
const float KT = 524288.0f;   // 1回（TMP_PRC=0）のときの倍率
int32_t tmpRaw = 0;
float baseline = 0;
bool dpsOk = false;

int32_t signExtend(int32_t v, int bits) {
  if (v & ((int32_t)1 << (bits - 1))) v -= (int32_t)1 << bits;
  return v;
}

uint8_t readReg(uint8_t reg) {
  Wire.beginTransmission(DPS_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(DPS_ADDR, (uint8_t)1);
  return Wire.available() ? Wire.read() : 0xFF;
}

void readRegs(uint8_t reg, uint8_t *buf, uint8_t n) {
  Wire.beginTransmission(DPS_ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(DPS_ADDR, n);
  for (uint8_t i = 0; i < n && Wire.available(); i++) buf[i] = Wire.read();
}

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(DPS_ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

int32_t read24(uint8_t reg) {
  uint8_t b[3];
  readRegs(reg, b, 3);
  return signExtend(((int32_t)b[0] << 16) | ((int32_t)b[1] << 8) | b[2], 24);
}

bool dpsBegin() {
  Wire.beginTransmission(DPS_ADDR);
  if (Wire.endTransmission() != 0) return false;
  uint8_t id = readReg(0x0D);
  Serial.print("DPS368 product id = 0x");
  Serial.println(id, HEX);  // 0x10 なら正しい

  writeReg(0x0C, 0x09);  // ソフトリセット
  delay(50);
  uint32_t t0 = millis();
  while ((readReg(0x08) & 0xC0) != 0xC0) {  // 係数とセンサーの準備ができるまで待つ
    if (millis() - t0 > 1000) return false;
    delay(10);
  }

  uint8_t b[18];
  readRegs(0x10, b, 18);
  c0 = signExtend(((int32_t)b[0] << 4) | (b[1] >> 4), 12);
  c1 = signExtend(((int32_t)(b[1] & 0x0F) << 8) | b[2], 12);
  c00 = signExtend(((int32_t)b[3] << 12) | ((int32_t)b[4] << 4) | (b[5] >> 4), 20);
  c10 = signExtend(((int32_t)(b[5] & 0x0F) << 16) | ((int32_t)b[6] << 8) | b[7], 20);
  c01 = signExtend(((int32_t)b[8] << 8) | b[9], 16);
  c11 = signExtend(((int32_t)b[10] << 8) | b[11], 16);
  c20 = signExtend(((int32_t)b[12] << 8) | b[13], 16);
  c21 = signExtend(((int32_t)b[14] << 8) | b[15], 16);
  c30 = signExtend(((int32_t)b[16] << 8) | b[17], 16);

  uint8_t tmpExt = readReg(0x28) & 0x80;  // 係数に合う温度センサーを使う
  writeReg(0x06, (5 << 4) | 3);           // 気圧：1秒に32回・8回の平均
  writeReg(0x07, tmpExt | (0 << 4) | 0);  // 温度：1秒に1回・1回
  writeReg(0x09, 0x00);                   // 8回の平均まではずらしなし
  writeReg(0x08, 0x07);                   // 気圧と温度を続けて測る
  delay(100);
  tmpRaw = read24(0x03);
  return true;
}

// 新しい気圧が出ていれば true。p に Pa を入れる
bool dpsRead(float &p) {
  uint8_t st = readReg(0x08);
  if (st & 0x20) tmpRaw = read24(0x03);
  if (!(st & 0x10)) return false;
  float ps = read24(0x00) / KP;
  float ts = tmpRaw / KT;
  p = c00 + ps * (c10 + ps * (c20 + ps * c30)) + ts * c01 + ts * ps * (c11 + ps * c21);
  return true;
}

float dpsTempC() { return c0 * 0.5f + c1 * (tmpRaw / KT); }

// ---------- I2S（MAX98357A） ----------
// D8=P1.13 BCLK、D9=P1.14 LRCLK、D10=P1.15 DIN。約16kHz・16bit・ステレオ
const int TONE_LEN = 16;  // 16129Hz ÷ 16 ≒ 1008Hz の「ピッ」（小さいスピーカーでも聞こえやすい高さ）
uint32_t toneBuf[TONE_LEN];

void i2sBegin() {
  for (int i = 0; i < TONE_LEN; i++) {
    int16_t s = (int16_t)(8000 * sinf(2 * PI * i / TONE_LEN));  // 最大の約4分の1の音量
    toneBuf[i] = ((uint32_t)(uint16_t)s << 16) | (uint16_t)s;   // 左右に同じ音
  }
  NRF_I2S->CONFIG.MODE = I2S_CONFIG_MODE_MODE_Master;
  NRF_I2S->CONFIG.TXEN = I2S_CONFIG_TXEN_TXEN_Enabled;
  NRF_I2S->CONFIG.RXEN = I2S_CONFIG_RXEN_RXEN_Disabled;
  NRF_I2S->CONFIG.MCKEN = I2S_CONFIG_MCKEN_MCKEN_Enabled;
  NRF_I2S->CONFIG.MCKFREQ = I2S_CONFIG_MCKFREQ_MCKFREQ_32MDIV31;
  NRF_I2S->CONFIG.RATIO = I2S_CONFIG_RATIO_RATIO_64X;
  NRF_I2S->CONFIG.SWIDTH = I2S_CONFIG_SWIDTH_SWIDTH_16Bit;
  NRF_I2S->CONFIG.ALIGN = I2S_CONFIG_ALIGN_ALIGN_Left;
  NRF_I2S->CONFIG.FORMAT = I2S_CONFIG_FORMAT_FORMAT_I2S;
  NRF_I2S->CONFIG.CHANNELS = I2S_CONFIG_CHANNELS_CHANNELS_Stereo;
  NRF_I2S->PSEL.MCK = 0xFFFFFFFF;  // MCLK は使わない
  NRF_I2S->PSEL.SCK = (1 << 5) | 13;
  NRF_I2S->PSEL.LRCK = (1 << 5) | 14;
  NRF_I2S->PSEL.SDOUT = (1 << 5) | 15;
  NRF_I2S->PSEL.SDIN = 0xFFFFFFFF;
  NRF_I2S->TXD.PTR = (uint32_t)toneBuf;
  NRF_I2S->RXTXD.MAXCNT = TONE_LEN;  // 同じバッファをくり返し鳴らす
  NRF_I2S->ENABLE = 1;
  NRF_I2S->TASKS_START = 1;
}

// アンプの オン・オフ（D7）で「ピッ」の長さを決める
void beep(int ms) {
  digitalWrite(PIN_AMP_EN, HIGH);
  delay(ms);
  digitalWrite(PIN_AMP_EN, LOW);
}

// ---------- LED ----------
void led(bool r, bool g, bool b) {  // XIAO の LED は LOW で光る
  digitalWrite(LED_RED, r ? LOW : HIGH);
  digitalWrite(LED_GREEN, g ? LOW : HIGH);
  digitalWrite(LED_BLUE, b ? LOW : HIGH);
}

// ---------- 本体 ----------
void setup() {
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(LED_BLUE, OUTPUT);
  led(false, false, false);
  for (int i = 0; i < 3; i++) pinMode(PIN_BTN[i], INPUT_PULLUP);
  pinMode(PIN_AMP_EN, OUTPUT);
  digitalWrite(PIN_AMP_EN, LOW);

  Serial.begin(115200);
  uint32_t t0 = millis();
  while (!Serial && millis() - t0 < 3000) delay(10);
  Serial.println();
  Serial.println("=== board_check (B ban) ===");

  Wire.begin();  // XIAO は D4=SDA、D5=SCL
  Wire.setClock(400000);
  Serial.print("I2C scan:");
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.print(" 0x");
      Serial.print(a, HEX);
    }
  }
  Serial.println();

  dpsOk = dpsBegin();
  Serial.println(dpsOk ? "DPS368: OK" : "DPS368: NG（見つからない）");
  if (dpsOk) {  // 吹かずに 1 秒間の平均を、差の基準にする
    float sum = 0, p;
    int n = 0;
    uint32_t t1 = millis();
    while (millis() - t1 < 1000) {
      if (dpsRead(p)) { sum += p; n++; }
      delay(5);
    }
    baseline = n ? sum / n : 0;
    Serial.print("baseline Pa = ");
    Serial.println(baseline, 1);
  }

  i2sBegin();
  for (int i = 0; i < 3; i++) {  // 起動の「ピッピッピッ」（USB だけでもアンプは動く）
    beep(150);
    delay(150);
  }
}

void loop() {
  static uint32_t lastLed = 0, lastPrint = 0;
  static int ledStep = 0;
  static bool prevBtn[3] = {false, false, false};
  static float pNow = 0;

  if (millis() - lastLed > 300) {
    lastLed = millis();
    ledStep = (ledStep + 1) % 3;
    led(ledStep == 0, ledStep == 1, ledStep == 2);
  }

  for (int i = 0; i < 3; i++) {
    bool on = digitalRead(PIN_BTN[i]) == LOW;
    if (on && !prevBtn[i]) {
      Serial.print("BUTTON SW");
      Serial.println(i + 1);
      beep(150 + 100 * i);  // ボタンごとに長さを変える
    }
    prevBtn[i] = on;
  }

  float p;
  if (dpsOk && dpsRead(p)) pNow = p;

  if (millis() - lastPrint > 100) {  // 1秒に10回
    lastPrint = millis();
    if (dpsOk) {
      float d = pNow - baseline;
      Serial.print("P=");
      Serial.print(pNow, 1);
      Serial.print(" dP=");
      Serial.print(d, 1);
      Serial.print(" T=");
      Serial.print(dpsTempC(), 1);
      Serial.print(" |");
      int bars = constrain((int)(fabsf(d) / 20), 0, 40);  // 20Pa で1目盛り
      for (int i = 0; i < bars; i++) Serial.print(d >= 0 ? '+' : '-');
      Serial.println();
    }
  }
}
