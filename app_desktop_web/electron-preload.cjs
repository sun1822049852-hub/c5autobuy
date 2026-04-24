const { contextBridge, ipcRenderer } = require("electron");


contextBridge.exposeInMainWorld("desktopApp", {
  getBootstrapConfig() {
    return ipcRenderer.sendSync("desktop:get-bootstrap-config");
  },
  subscribeBootstrapConfig(listener) {
    if (typeof listener !== "function") {
      return () => {};
    }
    const handler = (_event, payload) => {
      listener(payload);
    };
    ipcRenderer.on("desktop:bootstrap-config-updated", handler);
    return () => {
      ipcRenderer.removeListener("desktop:bootstrap-config-updated", handler);
    };
  },
  logRendererDiagnostic(payload) {
    ipcRenderer.send("desktop:log-renderer-diagnostic", payload);
  },
});
