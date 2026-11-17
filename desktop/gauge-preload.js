// 右下の煙メーター（gauge.html）と、アプリ（main.js）のやりとりの口
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('gaugeApi', {
  onState: (cb) => ipcRenderer.on('state', (_e, s) => cb(s)), // たまり具合と雲の絵
  onLive: (cb) => ipcRenderer.on('live', (_e, type, data) => cb(type, data)), // 吹き始め・吹き終わり・息の強さ（火の子が明るくなる／火の粉が散る）
  onGrow: (cb) => ipcRenderer.on('grow', (_e, g) => cb(g)),          // 戻ったとき：育った様子を見せる（前の姿 → 今の姿）
  openPanel: () => ipcRenderer.send('gauge', 'panel'),
  hide: () => ipcRenderer.send('gauge', 'hide'),
  toggleSmoke: () => ipcRenderer.send('gauge', 'smoke'), // 画面全体の煙を出す／隠す
  drag: (cmd) => ipcRenderer.send('gauge-drag', cmd), // つかんで動かす（start・end。動かすのはアプリの側）
  shake: (kind) => ipcRenderer.send('gauge-shake', kind), // 窓ごとゆらす（rumble・boom。残り火を吸いこむ演出。11/11）
  rise: (d) => ipcRenderer.send('gauge-rise', d), // もやもやの薪が燃えきった：火の粉を画面のいちばん上までのぼらせる（{ prep } で窓を用意、{ ps } で火の粉を渡す。11/12）
});
