// 休憩の実験の窓（trial.html）と、アプリ（main.js）のやりとりの口
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('trialApi', {
  onState: (cb) => ipcRenderer.on('app-state', (_e, s) => cb(s)),        // 本体とつながっているか
  onLive: (cb) => ipcRenderer.on('live', (_e, type, d) => cb(type, d)),   // 吹き始め・吹き終わり（深呼吸の間に出す）
  connect: () => ipcRenderer.send('trial-connect'),
  begin: () => ipcRenderer.invoke('trial-begin'),
  pvtStart: (kind) => ipcRenderer.send('trial-pvt-start', kind),          // 反応テストを始めた（kind：pre＝はじめ・post＝過ごしたあと）
  pvtDone: (kind, r) => ipcRenderer.invoke('trial-pvt-done', kind, r),   // 結果を記録。はじめのテストのあとは、くじの結果が返る
  activityStart: () => ipcRenderer.send('trial-act-start'),
  activityEnd: () => ipcRenderer.invoke('trial-act-end'),
  cancel: () => ipcRenderer.send('trial-cancel'),
  close: () => ipcRenderer.send('trial-close'),
});
