// 気圧の値から「吐く・止める・吸う」を見分ける
// Hack Day 版（jphacks/sp_2605 の app/server/breath.py、約3Hz）を、50ms ごと（20Hz）の判定に移したもの
#pragma once
#include <Arduino.h>
#include <math.h>

namespace breath {

// しきい値（Pa）。素の基板に直接吹いて最大 +86Pa だったので低め。筒ができたら見直す
// 11/11 夜：吹いた圧が 10〜25Pa と弱く、12Pa では吹き始めが遅れたり、弱い息を取りこぼしたりした → 8Pa に下げた
//   （部屋の気圧の変化は、下の「すばやく上がった・ゆれが大きい」の見分けではじくので、下げても誤反応しにくい）
const float EXHALE_ON = 8.0f;
const float EXHALE_OFF = 5.0f;
// 吐き終わり：その息のいちばん強かった圧の半分を下回ったら終わり（5Pa より大きいとき）。吹くのをやめたあと、
// 息の部屋の空気がゆっくり抜ける間（1〜2秒）も青いまま曲が進んでいたのを短くする（11/11 夜）
const float EXHALE_OFF_REL = 0.5f;
const float WEAK_PA = 12.0f;       // 「弱い」のめやす（なめらかが 0.6 秒で終わりにする）
const float INHALE_ON = -25.0f;
const float INHALE_OFF = -10.0f;
const int END_TICKS = 3;  // 吐き終わりは、OFF を3回（0.15秒）続けて下回ったら

const int SKIP_N = 20;           // 起動・測り直しのあと、最初の20回（1秒）は値が落ち着かないので使わない
const int WARMUP_N = 10;         // その次の10回（0.5秒）の中央値を基準にする
const float FOLLOW = 0.016f;     // 何もしていない間の基準の追いかけ方（Hack Day の 0.1/回 を 20Hz にした）
const float FOLLOW_BAND = 8.0f;  // 基準から ±8Pa 以内のときだけ追いかける

// 5Hz（4回ぶん）の平均値で、ゆっくりした変化を見る
const int SLOW_EVERY = 4;
const int SLOW_N = 60;  // 12秒ぶん
// 吐いていないのに、基準からずれたまま止まっていたら（3秒）、そこを新しい基準にする
// （11/05 の実測：吹いたあと、基準が −3〜−12Pa ずれた）
const int SETTLE_N = 15;
const float SETTLE_SPREAD = 4.0f;
const float SETTLE_MIN_OFFSET = 8.0f;
// 吐いている間に、弱いままほぼ動かない（3秒）のは息ではなく残った圧とみなし、吐き終わりにする
const float EXHALE_STILL_SPREAD = 3.0f;
// 息が12秒以上続き、ほぼ一定のままなら、基準がずれたとみなして測り直す
const uint32_t STUCK_MS = 12000;
const float STUCK_SPREAD = 6.0f;

// 11/11：部屋の気圧の変化（ドア・換気・風）で、吹いていないのに +10〜+30Pa が数秒続き、吐いたことになって青く光った。
//   実測（11/11 の記録）：本物の息はがたがたゆれる（0.1秒おきの 2階差の平均 4.1Pa）。部屋の変化はなめらか（0.6Pa、
//   何もしていない時の 0.5Pa とほぼ同じ）で、上がり方もゆっくり（0.2秒で 8Pa まで。息は 12Pa 以上）
//   ゆれは「2階差」（今 − 2×0.1秒前 + 0.2秒前）で見る。まっすぐ上がる・下がるだけなら 0 になるので、部屋の変化を拾わない
//   → ① 始まり：「すばやく上がった」か「ゆれが大きい」ときだけ、吐き始め・吸い始めにする
//     ② 吐いて（吸って）いる間：なめらかなまま CALM_TICKS 続いたら息ではないとみなし、終わりにしてそこを新しい基準にする
//     ③ 何もしていない間：なめらかなら、基準を早めに追いかける（部屋の変化についていく）
const int HIST_N = 5;              // 直近の気圧を覚えておく数（50ms ごと）
const int RISE_N = 4;              // 「すばやく上がった」を見る長さ（4回 = 0.2秒）
const float RISE_MIN = 12.0f;      // 0.2秒の間に、これ以上上がった（下がった）ら息
const float ROUGH_A = 0.15f;       // ゆれ（2階差の大きさ）の平均のならし方
const float ROUGH_BREATH = 1.5f;   // ゆれがこれ以上なら、上がり方がゆっくりでも息（11/11 夜：2.0 → 1.5。弱い息も拾う。何もしていない時は 0.4〜0.9）
const float ROUGH_CALM = 1.0f;     // ゆれがこれ未満を「なめらか」とする
const int CALM_TICKS = 36;         // なめらかなまま 1.8 秒続いたら、息ではない
const int CALM_TICKS_WEAK = 12;    // 弱い（EXHALE_ON 未満）まま、なめらかが 0.6 秒続いたら、息ではない（吹き終わりに残ったずれ）
const int CALM_DROP = 2;           // なめらかでない回は、数えた回数を 2 減らす（雑音で 1回ゆれただけで 0 に戻さない）
// 11/11 夜：2台目で、起動して最初に吹いたあと、しばらく青いままだった。吹き終わりに 5Pa 以上のずれが残り、
//   雑音でゆれが時々 1.0 を超えるので「なめらか 1.8 秒」がなかなか数え終わらなかった → 上の 2 つを足した
const float FOLLOW_CALM = 0.05f;   // 何もしていない・なめらかな間の基準の追いかけ方（約1秒）

enum State { IDLE, EXHALE, INHALE };

struct Detector {
  bool hasBase = false;
  int skip = SKIP_N;
  float baseline = 0;
  float warm[WARMUP_N];
  int nWarm = 0;

  State state = IDLE;
  int low = 0;
  uint32_t startMs = 0;
  float delta = 0;
  float peak = 0;

  float hist[HIST_N];  // 直近の気圧（hist の最後が 1回前）
  int nHist = 0, histHead = 0;
  float rough = 0;     // ゆれ（2階差の大きさの平均）
  int calm = 0;        // なめらかなまま続いた回数

  float slowAcc = 0;
  int slowCnt = 0;
  float slow[SLOW_N];
  int nSlow = 0, slowHead = 0;

  // 1回の update で起きたこと（終わり→始まりの順）
  bool evEnd = false, evStart = false, evReset = false;
  State endKind = IDLE, startKind = IDLE;
  float endSec = 0, endPeak = 0;

  void pushSlow(float v) {
    slow[slowHead] = v;
    slowHead = (slowHead + 1) % SLOW_N;
    if (nSlow < SLOW_N) nSlow++;
  }
  // 最後の k 個のばらつき（最大−最小）と平均
  void lastStats(int k, float &spread, float &mean) {
    float mn = 1e9, mx = -1e9, sum = 0;
    for (int i = 0; i < k; i++) {
      float v = slow[(slowHead - 1 - i + SLOW_N) % SLOW_N];
      mn = min(mn, v);
      mx = max(mx, v);
      sum += v;
    }
    spread = mx - mn;
    mean = sum / k;
  }

  void start(State kind, uint32_t now) {
    state = kind;
    low = 0;
    startMs = now;
    peak = 0;
    evStart = true;
    startKind = kind;
  }
  void end(uint32_t now) {
    evEnd = true;
    endKind = state;
    endSec = (now - startMs) / 1000.0f;
    endPeak = peak;
    state = IDLE;
    low = 0;
  }
  void reset() {
    hasBase = false;
    skip = SKIP_N;
    nWarm = 0;
    nSlow = 0;
    slowAcc = 0;
    slowCnt = 0;
    state = IDLE;
    low = 0;
    calm = 0;
    nHist = 0;
    evReset = true;
  }
  // k 回前の気圧（k = 1 が 1回前）
  float ago(int k) { return hist[(histHead - k + HIST_N * 2) % HIST_N]; }
  // 直近 RISE_N 回の最小・最大
  void histMinMax(float &mn, float &mx) {
    mn = 1e9;
    mx = -1e9;
    int n = min(nHist, RISE_N);
    for (int k = 1; k <= n; k++) {
      mn = min(mn, ago(k));
      mx = max(mx, ago(k));
    }
  }

  void update(float pa, uint32_t now) {
    evEnd = evStart = evReset = false;
    if (!hasBase) {
      if (skip > 0) {
        skip--;
        delta = 0;
        return;
      }
      warm[nWarm++] = pa;
      if (nWarm >= WARMUP_N) {  // 中央値
        for (int i = 1; i < nWarm; i++)
          for (int j = i; j > 0 && warm[j - 1] > warm[j]; j--) {
            float t = warm[j];
            warm[j] = warm[j - 1];
            warm[j - 1] = t;
          }
        baseline = warm[nWarm / 2];
        hasBase = true;
      }
      delta = 0;
      return;
    }
    delta = pa - baseline;

    // ゆれ（2階差）と、すばやい変化
    if (nHist >= 4) rough += ROUGH_A * (fabsf(pa - 2.0f * ago(2) + ago(4)) - rough);
    float hMin = pa, hMax = pa;
    if (nHist > 0) histMinMax(hMin, hMax);
    hist[histHead] = pa;
    histHead = (histHead + 1) % HIST_N;
    if (nHist < HIST_N) nHist++;
    bool rough_ = rough >= ROUGH_BREATH;
    bool riseFast = (pa - hMin) >= RISE_MIN;
    bool dropFast = (hMax - pa) >= RISE_MIN;
    calm = (rough < ROUGH_CALM) ? calm + 1 : max(0, calm - CALM_DROP);

    // 吐いて（吸って）いる間に、なめらかなまま続いたら、部屋の気圧の変化（か、吹き終わりに残ったずれ）とみなす
    bool weak = fabsf(delta) < WEAK_PA;
    if (state != IDLE && (calm >= CALM_TICKS || (weak && calm >= CALM_TICKS_WEAK))) {
      end(now);
      baseline = pa;
      delta = 0;
      nSlow = 0;
      calm = 0;
      return;
    }

    slowAcc += pa;
    if (++slowCnt >= SLOW_EVERY) {
      float v = slowAcc / slowCnt;
      slowAcc = 0;
      slowCnt = 0;
      pushSlow(v);
      if (nSlow >= SETTLE_N) {
        float spread, mean;
        lastStats(SETTLE_N, spread, mean);
        float d = v - baseline;
        if (state != EXHALE && spread < SETTLE_SPREAD && fabsf(d) >= SETTLE_MIN_OFFSET) {
          if (state == INHALE) end(now);
          baseline = mean;
          delta = pa - baseline;
        } else if (state == EXHALE && spread < EXHALE_STILL_SPREAD && d < EXHALE_ON) {
          end(now);
          baseline = mean;
          delta = pa - baseline;
          nSlow = 0;
        }
      }
      if (state != IDLE && now - startMs > STUCK_MS && nSlow >= SLOW_N) {
        float spread, mean;
        lastStats(SLOW_N, spread, mean);
        if (spread < STUCK_SPREAD) {
          reset();
          return;
        }
      }
    }

    if (state == IDLE) {
      if (delta >= EXHALE_ON && (riseFast || rough_)) start(EXHALE, now);
      else if (delta <= INHALE_ON && (dropFast || rough_)) start(INHALE, now);
      else if (rough < ROUGH_CALM) baseline += FOLLOW_CALM * delta;   // なめらか：部屋の変化についていく
      else if (fabsf(delta) < FOLLOW_BAND) baseline += FOLLOW * delta;
    } else if (state == EXHALE) {
      if (delta < max(EXHALE_OFF, EXHALE_OFF_REL * peak)) {
        low++;
        // 吸い始めたらすぐ切り替える。それ以外は、少し続けて弱まったら吐き終わり
        if (delta <= INHALE_ON || low >= END_TICKS) {
          end(now);
          if (delta <= INHALE_ON) start(INHALE, now);
        }
      } else {
        low = 0;
      }
    } else if (state == INHALE && delta > INHALE_OFF) {
      end(now);
      if (delta >= EXHALE_ON && (riseFast || rough_)) start(EXHALE, now);
    }
    if (state != IDLE && fabsf(delta) > fabsf(peak)) peak = delta;
  }
};

}  // namespace breath
