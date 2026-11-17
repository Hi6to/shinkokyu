// songs/*.json から make_songs.py で作ったファイル。手で直さない
#pragma once
#include <stdint.h>

struct Note { uint8_t midi; uint8_t q; };  // q = 拍数×4
struct Phrase { const Note *notes; uint8_t n; };
struct Song { const char *id; uint16_t bpm; const Phrase *phrases; uint8_t n; };

const Note amazing_grace_p0[] = {{62, 4}, {67, 8}, {71, 2}, {67, 2}, {71, 8}, {69, 4}, {67, 8}, {64, 4}, {62, 8}};
const Note amazing_grace_p1[] = {{62, 4}, {67, 8}, {71, 2}, {67, 2}, {71, 8}, {69, 4}, {74, 12}};
const Note amazing_grace_p2[] = {{71, 4}, {74, 8}, {71, 2}, {67, 2}, {71, 8}, {69, 4}, {67, 8}, {64, 4}, {62, 8}};
const Note amazing_grace_p3[] = {{62, 4}, {67, 8}, {71, 2}, {67, 2}, {71, 8}, {69, 4}, {67, 12}};
const Phrase amazing_grace_phrases[] = {{amazing_grace_p0, 9}, {amazing_grace_p1, 7}, {amazing_grace_p2, 9}, {amazing_grace_p3, 7}};

const Note ode_to_joy_p0[] = {{71, 4}, {71, 4}, {72, 4}, {74, 4}, {74, 4}, {72, 4}, {71, 4}, {69, 4}};
const Note ode_to_joy_p1[] = {{67, 4}, {67, 4}, {69, 4}, {71, 4}, {71, 6}, {69, 2}, {69, 8}};
const Note ode_to_joy_p2[] = {{71, 4}, {71, 4}, {72, 4}, {74, 4}, {74, 4}, {72, 4}, {71, 4}, {69, 4}};
const Note ode_to_joy_p3[] = {{67, 4}, {67, 4}, {69, 4}, {71, 4}, {69, 6}, {67, 2}, {67, 8}};
const Phrase ode_to_joy_phrases[] = {{ode_to_joy_p0, 8}, {ode_to_joy_p1, 7}, {ode_to_joy_p2, 8}, {ode_to_joy_p3, 7}};

const Song SONGS[] = {{"amazing_grace", 100, amazing_grace_phrases, 4}, {"ode_to_joy", 100, ode_to_joy_phrases, 4}};
const int SONG_COUNT = 2;
