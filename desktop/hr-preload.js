// 11/14：心拍数の窓（hr.html）と、アプリ（main.js）のやりとりの口
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('hrApi', {
  status: (s) => ipcRenderer.send('hr-status', s), // { text, bpm, name, base }
  drag: (cmd) => ipcRenderer.send('hr-drag', cmd), // つかんで動かす（start・end）
  log: (type, data) => ipcRenderer.send('log', type, data),
  onScale: (cb) => ipcRenderer.on('hr-scale', (_e, s) => cb(s)),
  size: (step) => ipcRenderer.send('hr-size-step', step), // 11/15：窓の −・＋ ボタン（1 段小さく・大きく）
  btns: (rects) => ipcRenderer.send('hr-btns', rects),     // 11/15：ボタンの場所（アプリの側でも押したかを見るため）
});
