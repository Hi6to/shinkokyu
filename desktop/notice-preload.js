// 右の吹き出し（notice.html）と、アプリ（main.js）のやりとりの口
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('noticeApi', {
  onToast: (cb) => ipcRenderer.on('toast', (_e, n) => cb(n)), // 吹き出しを1つ出す
  empty: () => ipcRenderer.send('notice-empty'),              // 全部消えた（窓をかくしてよい）
  onMouse: (cb) => ipcRenderer.on('mouse', () => cb()),
  rects: (r) => ipcRenderer.send('notice-rects', r),              // 吹き出しのある場所。アプリが、その上にマウスがある間だけ押せるようにする（右上の ×。11/13）
  onCloseAt: (cb) => ipcRenderer.on('close-at', (_e, pt) => cb(pt)), // 11/13：アプリが見た「× の所を押した」（窓の中の位置）。その吹き出しを消す
  onClear: (cb) => ipcRenderer.on('toast-clear', () => cb()),   // 全部消す（大きさを変えたとき）         // マウスが動いた（読み終わった吹き出しを消す。11/11）
});
