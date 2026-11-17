// 音の合成と、曲の進み方（シーケンサー）
// - I2S（MAX98357A）に、割り込みで2つのバッファを交互に渡す（128フレーム≒8ms）
// - 曲を進めるのも、音（声部）を変えるのも、割り込みの中だけ。外からは volatile のフラグで頼む
// - 電子音っぽさを減らすため、部屋の響き（残響）を足す。粒は間隔と大きさを少しばらつかせる
#pragma once
#include <Arduino.h>
#include <math.h>
#include "songs.h"

namespace synth {

const float FS = 32000000.0f / 31.0f / 64.0f;  // ≒16129Hz
const int BUF_FRAMES = 128;
uint32_t buf[2][BUF_FRAMES];
volatile uint8_t cur = 0;

int16_t sineTab[256], fluteTab[256];

uint32_t rngState = 2463534242u;
inline uint32_t rnd() {  // xorshift
  rngState ^= rngState << 13;
  rngState ^= rngState >> 17;
  rngState ^= rngState << 5;
  return rngState;
}
inline float rndf() { return (rnd() >> 8) * (1.0f / 16777216.0f); }  // 0〜1

float coefFor(float sec) { return 1.0f - expf(-1.0f / (sec * FS)); }

// ---------- 声部 ----------
struct Voice {
  uint32_t phase;
  float inc, incTarget, incCoef;  // 高さ（泡は少し下から上がる）
  float amp, target, coef;        // 大きさ：amp は target に向かって coef の速さで近づく
  float vib, vibTarget;           // ゆらぎ（ビブラート）の深さ
  float breathNoise;              // 息の音（笛）
  float tick, tickCoef;           // 弾いた瞬間の「カッ」（オルゴール）
  float nLP;                      // 雑音を丸める
  const int16_t *tab;
};
const int NV = 12;
Voice v[NV];

float incFor(float freq) { return freq / FS * 4294967296.0f; }

int freeVoice() {
  int best = 0;
  float bestLevel = 1e9;
  for (int i = 0; i < NV; i++) {  // いちばん静かな声部を使う
    float level = v[i].amp + v[i].target + v[i].tick;
    if (level < bestLevel) {
      bestLevel = level;
      best = i;
    }
  }
  return best;
}

int startVoice(float freq, const int16_t *tab, float amp0, float target, float coef) {
  int i = freeVoice();
  Voice &x = v[i];
  x.phase = 0;
  x.inc = x.incTarget = incFor(freq);
  x.incCoef = 0;
  x.amp = amp0;
  x.target = target;
  x.coef = coef;
  x.vib = x.vibTarget = 0;
  x.breathNoise = 0;
  x.tick = 0;
  x.tickCoef = 0;
  x.nLP = 0;
  x.tab = tab;
  return i;
}

// ---------- 残響（小さな部屋の響き。Schroeder 型：くし形4つ＋オールパス2つ） ----------
const int CL0 = 563, CL1 = 607, CL2 = 653, CL3 = 701, AL0 = 83, AL1 = 211;
float revBuf[CL0 + CL1 + CL2 + CL3 + AL0 + AL1];
struct Delay {
  float *b;
  int len, idx;
  float lp;
};
Delay comb[4], allp[2];
const float COMB_FB = 0.76f, COMB_DAMP = 0.35f, REV_WET = 0.28f;

float reverb(float in) {
  float out = 0;
  for (int k = 0; k < 4; k++) {
    Delay &c = comb[k];
    float y = c.b[c.idx];
    c.lp = y * (1 - COMB_DAMP) + c.lp * COMB_DAMP;
    c.b[c.idx] = in + c.lp * COMB_FB;
    if (++c.idx >= c.len) c.idx = 0;
    out += y;
  }
  out *= 0.25f;
  for (int k = 0; k < 2; k++) {
    Delay &a = allp[k];
    float b = a.b[a.idx];
    float y = b - out;
    a.b[a.idx] = out + b * 0.5f;
    if (++a.idx >= a.len) a.idx = 0;
    out = y;
  }
  return out;
}

// ---------- モードと、外からの頼みごと ----------
enum Mode { FLUTE, BUBBLE, MUSICBOX, FX, MODE_COUNT };
const char *MODE_NAME[MODE_COUNT] = {"flute", "bubble", "musicbox", "fx"};

volatile bool exhaling = false;      // 吐いている間だけ true（メインが入れる）
volatile float breathLevel = 1.0f;   // 息の強さに合わせた大きさ（0.3〜1）。弱まると音も小さくなる
volatile uint8_t mode = FLUTE;
volatile float gain = 0.6f;          // 音量
volatile bool reqRestart = false;    // 曲の最初に戻して、3秒試しに鳴らす
volatile bool reqReset = false;      // 曲の最初に戻すだけ（鳴らさない。PC の煙の画面から頼まれたとき）
volatile bool reqNextSong = false;   // 次の曲にして、3秒試しに鳴らす
volatile bool reqBlip = false;       // 「ぽっ」（音量を変えたとき）
volatile float reqBell = 0;          // おりん（大きさ。0 なら鳴らさない）

// ---------- 音の作り方 ----------
const float FLUTE_AMP = 0.30f;
const float GRAIN_AMP = 0.36f;
const float FX_FREQ = 1200.0f;    // 効果音だけのモードの高さ
const float BELL_FREQ = 1568.0f;  // おりん：G6
float F_ATTACK, F_RELEASE, VIB_COEF, BUBBLE_DECAY, BUBBLE_GLIDE, BOX_DECAY, BOX_HI_DECAY, TICK_DECAY;
uint32_t LFO_INC;
uint32_t lfoPhase = 0;

int toneVoice = -1;

void releaseTone() {
  if (toneVoice >= 0) {
    v[toneVoice].target = 0;
    v[toneVoice].coef = F_RELEASE;
    toneVoice = -1;
  }
}

void bubble(float f, float level) {  // 泡：少し低いところから本来の高さへ上がり、すぐ消える「ポコッ」
  int i = startVoice(f * 0.88f, sineTab, GRAIN_AMP * level, 0, BUBBLE_DECAY);
  v[i].incTarget = incFor(f);
  v[i].incCoef = BUBBLE_GLIDE;
}

void musicbox(float f, float level) {  // オルゴール：金属の歯を弾いた音。高い部分音（6.27倍）はすぐ消える
  int i = startVoice(f, sineTab, 0.30f * level, 0, BOX_DECAY);
  v[i].tick = 0.10f * level;
  v[i].tickCoef = TICK_DECAY;
  if (f * 6.27f < 7800) startVoice(f * 6.27f, sineTab, 0.05f * level, 0, BOX_HI_DECAY);
}

void flute(float f) {
  releaseTone();
  int i = startVoice(f, fluteTab, 0, FLUTE_AMP * breathLevel, F_ATTACK);
  v[i].vibTarget = 0.004f;  // 約7セントのゆらぎを、ゆっくりかける
  v[i].breathNoise = 0.06f;
  toneVoice = i;
}

void bell(float scale) {  // おりん：基音・2倍・2.76倍（8kHz を超える部分音は入れない）
  startVoice(BELL_FREQ, sineTab, 0.30f * scale, 0, coefFor(1.6f));
  startVoice(BELL_FREQ * 2.0f, sineTab, 0.10f * scale, 0, coefFor(0.9f));
  startVoice(BELL_FREQ * 2.76f, sineTab, 0.07f * scale, 0, coefFor(0.5f));
}

// ---------- 曲の進み方（割り込みの中だけで書き換える） ----------
volatile int songIdx = 0, phraseIdx = 0, noteIdx = 0;
volatile bool phraseDone = false;  // 曲を吹き終えて、息が終わるのを待っている
volatile bool songDone = false;    // 最後のフレーズまで吹き終えた（メインが読んで消す）
volatile uint8_t curMidi = 0;      // 今鳴らしている音（MIDI の番号、本体で鳴らす高さ）。0 は鳴っていない
uint32_t notePos = 0, grainLeft = 0, previewLeft = 0;
bool sounding = false;

const Song &song() { return SONGS[songIdx]; }
float beatSamples() { return 60.0f / song().bpm * FS; }
uint32_t noteLen(const Note &nt) { return (uint32_t)(nt.q * beatSamples() / 4); }
float noteFreq(const Note &nt) { return 440.0f * powf(2.0f, (nt.midi + 12 - 69) / 12.0f); }  // 1オクターブ上げる

// 粒の間隔（少しばらつかせる）
uint32_t grainInterval() {
  float base = (mode == MUSICBOX) ? 0.15f : 0.075f;  // 泡・効果音は約75ms（ポポポポ）
  return (uint32_t)(base * (0.85f + 0.3f * rndf()) * FS);
}

void grain(const Note &nt) {
  float level = breathLevel * (0.8f + 0.2f * rndf());  // 大きさも少しばらつかせる
  if (mode == BUBBLE) bubble(noteFreq(nt), level);
  else if (mode == MUSICBOX) musicbox(noteFreq(nt), level);
  else bubble(FX_FREQ * (0.96f + 0.08f * rndf()), level);
}

void soundNote(const Note &nt) {
  curMidi = nt.midi + 12;
  if (mode == FLUTE) flute(noteFreq(nt));
  else grain(nt);
  grainLeft = grainInterval();
}

void resetPos() {
  releaseTone();
  sounding = false;
  curMidi = 0;
  phraseIdx = 0;
  noteIdx = 0;
  notePos = 0;
  phraseDone = false;
}

void tick(uint32_t n) {
  if (reqBlip) {
    reqBlip = false;
    bubble(1760.0f, 1.0f);
  }
  if (reqBell > 0) {
    bell(reqBell);
    reqBell = 0;
  }
  if (reqNextSong) {
    reqNextSong = false;
    songIdx = (songIdx + 1) % SONG_COUNT;
    reqRestart = true;
  }
  if (reqRestart) {
    reqRestart = false;
    resetPos();
    previewLeft = (uint32_t)(3 * FS);
  }
  if (reqReset) {
    reqReset = false;
    resetPos();
    previewLeft = 0;
  }

  bool preview = previewLeft > 0;
  if (preview) {
    previewLeft = previewLeft > n ? previewLeft - n : 0;
    if (previewLeft == 0) {  // 試しに鳴らし終えたら、最初に戻しておく
      resetPos();
      return;
    }
  }

  if (!(exhaling || preview)) {
    if (sounding) {  // 息が止まったら音を止める。次の息で同じ音の続きから
      releaseTone();
      sounding = false;
      curMidi = 0;
    }
    if (phraseDone) {  // フレーズを吹き終えた息が終わったら、次のフレーズへ
      phraseDone = false;
      phraseIdx = (phraseIdx + 1) % song().n;
      noteIdx = 0;
      notePos = 0;
    }
    return;
  }
  if (phraseDone) return;

  // 笛の大きさは息の強さについていく（弱まると小さくなる）
  if (toneVoice >= 0) v[toneVoice].target = FLUTE_AMP * (preview ? 1.0f : breathLevel);

  const Phrase &ph = song().phrases[phraseIdx];
  const Note &nt = ph.notes[noteIdx];
  if (!sounding) {
    soundNote(nt);
    sounding = true;
  }
  notePos += n;
  uint32_t len = noteLen(nt);

  if (notePos >= len) {
    notePos -= len;
    noteIdx++;
    if (noteIdx >= ph.n) {  // フレーズの終わり
      noteIdx = 0;
      if (phraseIdx == song().n - 1) {  // 曲の終わり：おりんを鳴らし、その息が終わるまで待つ
        notePos = 0;
        phraseDone = true;
        releaseTone();
        sounding = false;
        curMidi = 0;
        bell(1.0f);
        songDone = true;
      } else {  // 吹き続けていれば、そのまま次のフレーズへ（11/05 Hi6to：フレーズごとに止めない）
        phraseIdx = phraseIdx + 1;
        soundNote(song().phrases[phraseIdx].notes[0]);
      }
    } else {
      soundNote(ph.notes[noteIdx]);
    }
  } else if (mode != FLUTE) {
    if (grainLeft > n) {
      grainLeft -= n;
    } else if (len - notePos > grainInterval() / 3) {  // 粒を続ける（音の終わりぎわは鳴らさない）
      grain(nt);
      grainLeft = grainInterval();
    }
  }
}

// ---------- バッファを埋める ----------
const float SOFT_K = 24000.0f;  // ここまでの大きさは、そのまま出す（11/12）
void render(uint32_t *out) {
  tick(BUF_FRAMES);
  float g = gain;
  for (int i = 0; i < BUF_FRAMES; i++) {
    lfoPhase += LFO_INC;
    float lfo = sineTab[lfoPhase >> 24] * (1.0f / 32767);
    float s = 0;
    for (int k = 0; k < NV; k++) {
      Voice &x = v[k];
      if (x.target == 0 && x.amp < 1e-4f && x.tick < 1e-4f) {
        x.amp = 0;
        x.tick = 0;
        continue;
      }
      x.amp += (x.target - x.amp) * x.coef;
      x.inc += (x.incTarget - x.inc) * x.incCoef;
      float inc = x.inc;
      if (x.vibTarget > 0) {
        x.vib += (x.vibTarget - x.vib) * VIB_COEF;
        inc *= 1.0f + x.vib * lfo;
      }
      x.phase += (uint32_t)inc;
      s += x.tab[x.phase >> 24] * x.amp;
      if (x.breathNoise > 0 || x.tick > 0) {
        float w = (int32_t)rnd() * (1.0f / 2147483648.0f);
        x.nLP += (w - x.nLP) * 0.35f;
        s += x.nLP * 32767 * (x.breathNoise * x.amp + x.tick);
        x.tick *= 1.0f - x.tickCoef;
      }
    }
    s += REV_WET * reverb(s);
    // 11/12：やわらかく頭を抑える（音量 9・10 で音が重なっても、バリバリ割れない）。SOFT_K まではそのまま、その上は 32767 にゆっくり近づく
    float y = s * g, ay = fabsf(y);
    if (ay > SOFT_K) { float e = (ay - SOFT_K) / (32767.0f - SOFT_K); y = copysignf(SOFT_K + (32767.0f - SOFT_K) * e / (1.0f + e), y); }
    int32_t o = (int32_t)y;
    if (o > 32767) o = 32767;
    if (o < -32767) o = -32767;
    out[i] = ((uint32_t)(uint16_t)o << 16) | (uint16_t)o;  // 左右に同じ音
  }
}

void begin() {
  for (int i = 0; i < 256; i++) {
    float t = 2 * PI * i / 256;
    sineTab[i] = (int16_t)(32767 * sinf(t));
    // 笛っぽい音：基音に、2〜4倍の音を少し足す
    float f = sinf(t) + 0.35f * sinf(2 * t) + 0.15f * sinf(3 * t) + 0.06f * sinf(4 * t);
    fluteTab[i] = (int16_t)(32767 * f / 1.45f);
  }
  F_ATTACK = coefFor(0.010f);      // 立ち上がり 約30ms（やわらかく）
  F_RELEASE = coefFor(0.020f);     // 離す 約60ms（残響が後を引き取る）
  VIB_COEF = coefFor(0.30f);       // ゆらぎは0.3秒ほどかけて深くなる
  BUBBLE_DECAY = coefFor(0.045f);  // 泡は短く
  BUBBLE_GLIDE = coefFor(0.008f);
  BOX_DECAY = coefFor(0.35f);
  BOX_HI_DECAY = coefFor(0.05f);
  TICK_DECAY = coefFor(0.0015f);
  LFO_INC = (uint32_t)(5.0f / FS * 4294967296.0f);  // ゆらぎは1秒に5回
  for (int i = 0; i < NV; i++) v[i] = Voice{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, sineTab};

  float *p = revBuf;
  const int cl[4] = {CL0, CL1, CL2, CL3}, al[2] = {AL0, AL1};
  for (int k = 0; k < 4; k++) {
    comb[k] = Delay{p, cl[k], 0, 0};
    p += cl[k];
  }
  for (int k = 0; k < 2; k++) {
    allp[k] = Delay{p, al[k], 0, 0};
    p += al[k];
  }

  render(buf[0]);
  cur = 0;

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
  NRF_I2S->PSEL.MCK = 0xFFFFFFFF;       // MCLK は使わない
  NRF_I2S->PSEL.SCK = (1 << 5) | 13;    // D8 = P1.13 BCLK
  NRF_I2S->PSEL.LRCK = (1 << 5) | 14;   // D9 = P1.14 LRCLK
  NRF_I2S->PSEL.SDOUT = (1 << 5) | 15;  // D10 = P1.15 DIN
  NRF_I2S->PSEL.SDIN = 0xFFFFFFFF;
  NRF_I2S->TXD.PTR = (uint32_t)buf[0];
  NRF_I2S->RXTXD.MAXCNT = BUF_FRAMES;

  NRF_I2S->EVENTS_TXPTRUPD = 0;
  NRF_I2S->INTENSET = I2S_INTENSET_TXPTRUPD_Msk;
  NVIC_SetPriority(I2S_IRQn, 6);  // 0・1・4 は Bluetooth（SoftDevice）用なので使わない
  NVIC_ClearPendingIRQ(I2S_IRQn);
  NVIC_EnableIRQ(I2S_IRQn);

  NRF_I2S->ENABLE = 1;
  NRF_I2S->TASKS_START = 1;
}

}  // namespace synth

// I2S が次のバッファの場所を読み取ったら呼ばれる。もう片方を次に渡して、埋める
extern "C" void I2S_IRQHandler(void) {
  if (NRF_I2S->EVENTS_TXPTRUPD) {
    NRF_I2S->EVENTS_TXPTRUPD = 0;
    (void)NRF_I2S->EVENTS_TXPTRUPD;
    synth::cur ^= 1;
    NRF_I2S->TXD.PTR = (uint32_t)synth::buf[synth::cur];
    synth::render(synth::buf[synth::cur]);
  }
}
