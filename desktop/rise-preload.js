// 火の粉が画面の上までのぼる窓（rise.html）と、アプリ（main.js）のやりとりの口（11/12）
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('riseApi', {
  onRise: (cb) => ipcRenderer.on('rise', (_e, d) => cb(d)), // { prep, ox, oy, gw, scale }：窓を用意した／{ ps: [{ u, s }] }：火の粉が火の子の窓の上から出た
});
