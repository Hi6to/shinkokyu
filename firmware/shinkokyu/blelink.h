// Bluetooth（BLE）で PC の Chrome に1行ずつ文字を送る（S01）
// - Nordic UART Service（NUS）を使う。Chrome の Web Bluetooth でそのまま読める
// - 名前は「Shinkokyu-XXXX」（XXXX は本体ごとに違う。2台を見分けるため）
#pragma once
#include <bluefruit.h>

namespace blelink {

BLEUart uart;
char name[24];
volatile bool connected = false;

void onConnect(uint16_t conn) { connected = true; }
void onDisconnect(uint16_t conn, uint8_t reason) { connected = false; }

void begin() {
  Bluefruit.autoConnLed(false);  // 青い LED は「吐いている」の表示に使う
  Bluefruit.configPrphBandwidth(BANDWIDTH_MAX);
  Bluefruit.begin();
  Bluefruit.setTxPower(4);
  snprintf(name, sizeof(name), "Shinkokyu-%04X", (unsigned)(NRF_FICR->DEVICEADDR[0] & 0xFFFF));
  Bluefruit.setName(name);
  Bluefruit.Periph.setConnInterval(6, 12);  // 7.5〜15ms ごとにやりとりする（遅れを小さく）
  Bluefruit.Periph.setConnectCallback(onConnect);
  Bluefruit.Periph.setDisconnectCallback(onDisconnect);

  uart.begin();

  Bluefruit.Advertising.addFlags(BLE_GAP_ADV_FLAGS_LE_ONLY_GENERAL_DISC_MODE);
  Bluefruit.Advertising.addTxPower();
  Bluefruit.Advertising.addService(uart);
  Bluefruit.ScanResponse.addName();
  Bluefruit.Advertising.restartOnDisconnect(true);
  Bluefruit.Advertising.setInterval(32, 244);  // はじめの30秒は 20ms ごと、そのあと 152ms ごとに知らせる
  Bluefruit.Advertising.setFastTimeout(30);
  Bluefruit.Advertising.start(0);

  // 音の高さと速さを正確に保つため、水晶の 32MHz を動かし続ける（Bluetooth を始めると切り替わることがある）
  sd_clock_hfclk_request();
}

bool ready() { return connected && uart.notifyEnabled(); }

// PC から届いた1行を読む（なければ false）。例：「RESTART」
bool readLine(char *out, int size) {
  static char buf[48];
  static int n = 0;
  while (uart.available()) {
    char c = uart.read();
    if (c == 10 || c == 13) {  // 改行
      if (n == 0) continue;
      buf[n] = 0;
      strncpy(out, buf, size - 1);
      out[size - 1] = 0;
      n = 0;
      return true;
    }
    if (n < (int)sizeof(buf) - 1) buf[n++] = c;
  }
  return false;
}

void send(const char *line) {
  if (!ready()) return;
  char b[96];
  int n = snprintf(b, sizeof(b), "%s\n", line);
  uart.write((const uint8_t *)b, min(n, (int)sizeof(b) - 1));
}

}  // namespace blelink
