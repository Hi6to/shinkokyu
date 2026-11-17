// 操作パネル（panel.html）と、アプリ（main.js）のやりとりの口
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('panelApi', {
  send: (cmd, arg) => ipcRenderer.send('panel', cmd, arg),
  onState: (cb) => ipcRenderer.on('state', (_e, s) => cb(s)),
  // 声を煙のラベルにする
  voiceStart: (via) => ipcRenderer.send('voice-start', via),
  voiceCancel: (why) => { ipcRenderer.send('voice-cancel', why && why.why); if (why) ipcRenderer.send('log', 'voice_cancel', why); }, // 取りやめ（理由と音の大きさの数字だけ記録する）
  voiceStopping: () => ipcRenderer.send('voice-stopping'), // 11/15：おわりを押した（声の基板から残りが届くのを待っている）。画面にすぐ出す
  log: (type, data) => ipcRenderer.send('log', type, data),
  voice: (wav, meta) => ipcRenderer.invoke('voice-wav', wav, meta),
  voiceLevel: (v) => ipcRenderer.send('voice-level', v), // 話している間の声の大きさ（0〜1）。右下の火の子が声に合わせてゆれる（11/12）
  onVoice: (cb) => ipcRenderer.on('voice', (_e, cmd) => cb(cmd)),
  onBtList: (cb) => ipcRenderer.on('bt-list', (_e, list) => cb(list)), // 見つかった本体の一覧（null は探し終わった。11/12）
});
