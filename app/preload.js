const { contextBridge, ipcRenderer } = require('electron');
contextBridge.exposeInMainWorld('adf', {
  call: (args) => ipcRenderer.invoke('adf', args),
  read: (rel) => ipcRenderer.invoke('read', rel),
  pick: () => ipcRenderer.invoke('pick'),
  info: () => ipcRenderer.invoke('info'),
});
