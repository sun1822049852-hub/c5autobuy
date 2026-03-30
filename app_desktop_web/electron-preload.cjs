const { contextBridge, ipcRenderer } = require("electron");


contextBridge.exposeInMainWorld("desktopApp", {
  getBootstrapConfig() {
    return ipcRenderer.sendSync("desktop:get-bootstrap-config");
  },
  logRendererDiagnostic(payload) {
    ipcRenderer.send("desktop:log-renderer-diagnostic", payload);
  },
});
