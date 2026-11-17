// IMA ADPCM：16bit の声を 4bit に縮める（4分の1。Bluetooth で話しながら送れる量にする）
// PC 側（desktop/sense-mic.js）は、同じ表で元にもどす
#pragma once
#include <stdint.h>

namespace adpcm {

const int16_t STEP[89] = {
  7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45,
  50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157, 173, 190, 209, 230, 253, 279, 307,
  337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066,
  2272, 2499, 2749, 3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899,
  15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794, 32767};
const int8_t INDEX[16] = {-1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8};

struct State {
  int32_t pred = 0;
  int index = 0;
};

// 1サンプルを 4bit にする（State を進める）
inline uint8_t encode(int16_t s, State &st) {
  int step = STEP[st.index];
  int32_t diff = (int32_t)s - st.pred;
  uint8_t code = 0;
  if (diff < 0) { code = 8; diff = -diff; }
  int32_t delta = step >> 3;
  if (diff >= step) { code |= 4; diff -= step; delta += step; }
  step >>= 1;
  if (diff >= step) { code |= 2; diff -= step; delta += step; }
  step >>= 1;
  if (diff >= step) { code |= 1; delta += step; }
  st.pred += (code & 8) ? -delta : delta;
  if (st.pred > 32767) st.pred = 32767;
  if (st.pred < -32768) st.pred = -32768;
  st.index += INDEX[code];
  if (st.index < 0) st.index = 0;
  if (st.index > 88) st.index = 88;
  return code;
}

}  // namespace adpcm
