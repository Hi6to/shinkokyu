// 気圧センサー DPS368（I2C 0x77）。board_check と同じ設定
// 気圧：1秒に32回・8回の平均、温度：1秒に1回
#pragma once
#include <Arduino.h>
#include <Wire.h>

namespace dps {

uint8_t ADDR = 0x77;  // 11/12 夜：見つからなければ 0x76 も試す（センサーの SDO の足が GND 側だと 0x76 になる）
const float KP = 7864320.0f;  // 8回の平均（PM_PRC=3）のときの倍率
const float KT = 524288.0f;   // 1回（TMP_PRC=0）のときの倍率

int32_t c0, c1, c00, c10, c01, c11, c20, c21, c30;
int32_t tmpRaw = 0;

int32_t signExtend(int32_t v, int bits) {
  if (v & ((int32_t)1 << (bits - 1))) v -= (int32_t)1 << bits;
  return v;
}

uint8_t readReg(uint8_t reg) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(ADDR, (uint8_t)1);
  return Wire.available() ? Wire.read() : 0xFF;
}

void readRegs(uint8_t reg, uint8_t *buf, uint8_t n) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.endTransmission(false);
  Wire.requestFrom(ADDR, n);
  for (uint8_t i = 0; i < n && Wire.available(); i++) buf[i] = Wire.read();
}

void writeReg(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(ADDR);
  Wire.write(reg);
  Wire.write(val);
  Wire.endTransmission();
}

int32_t read24(uint8_t reg) {
  uint8_t b[3];
  readRegs(reg, b, 3);
  return signExtend(((int32_t)b[0] << 16) | ((int32_t)b[1] << 8) | b[2], 24);
}

bool begin() {
  Wire.beginTransmission(0x77);
  if (Wire.endTransmission() == 0) ADDR = 0x77;
  else {
    Wire.beginTransmission(0x76);
    if (Wire.endTransmission() != 0) return false;
    ADDR = 0x76;
  }

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
  // 最初の温度が出るまで待つ。11/05、出る前の気圧を基準にしたら、約1秒後に値が 17Pa 跳ねて「吐いた」と取り違えた
  t0 = millis();
  while (!(readReg(0x08) & 0x20) && millis() - t0 < 1500) delay(10);
  tmpRaw = read24(0x03);
  return true;
}

// 新しい気圧が出ていれば true。p に Pa を入れる
bool read(float &p) {
  uint8_t st = readReg(0x08);
  if (st == 0xFF || (st & 0xC0) != 0xC0) return false;  // 11/12：返事がない（線が外れた・センサーが落ちた）ときは、値にしない（0xFF を読んだまま、おかしな値を使っていた）
  if (st & 0x20) tmpRaw = read24(0x03);
  if (!(st & 0x10)) return false;
  float ps = read24(0x00) / KP;
  float ts = tmpRaw / KT;
  p = c00 + ps * (c10 + ps * (c20 + ps * c30)) + ts * c01 + ts * ps * (c11 + ps * c21);
  return true;
}

float tempC() { return c0 * 0.5f + c1 * (tmpRaw / KT); }

}  // namespace dps
