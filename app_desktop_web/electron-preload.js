import { contextBridge, ipcRenderer } from "electron";


contextBridge.exposeInMainWorld("desktopApp", {
  getBootstrapConfig() {
    return ipcRenderer.sendSync("desktop:get-bootstrap-config");
  },
});
