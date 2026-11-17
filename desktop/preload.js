// ページ（web/retro.html）から、アプリ（main.js）へ知らせる口
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('shinkokyuApp', {
  // 通知領域のアイコンの絵（たまり具合）と、マウスを乗せたときの文
  setTrayIcon: (dataUrl, tooltip) => ipcRenderer.send('tray-icon', dataUrl, tooltip),
  // 今の様子（操作パネルに出す・戻ってきたかの判断に使う）
  sendState: (s) => ipcRenderer.send('state', s),
  // メッセージの窓の場所（画面のピクセル。なければ null）。アプリがマウスの位置を見て、窓の上だけ押せるようにする
  msgRect: (r) => ipcRenderer.send('msg-rect', r),
  // 煙を表示に切りかえる（休憩の通知を押したとき）
  showSmoke: () => ipcRenderer.send('show-smoke'),
  setGaugeIcon: (dataUrl) => ipcRenderer.send('gauge-icon', dataUrl), // 右下の煙メーター用の雲の絵
  // 休みどきの理由（つづけて作業した時間・ふだんとのちがい）
  reason: () => ipcRenderer.invoke('reason'),
  // 記録に1行足す（息・通知・吹き終わり）
  log: (type, data) => ipcRenderer.send('log', type, data),
  // 吹き始め・吹き終わりを、休憩の実験の窓へ（記録はしない）
  live: (type, data) => ipcRenderer.send('live', type, data),
  // 一服のお誘い（本体の曲送りボタンの長押し）
  invite: (via) => ipcRenderer.send('invite', via),
  // 声を録る・終える（本体の音量＋と−の同時押し。11/11）
  talk: () => ipcRenderer.send('talk'),
});
