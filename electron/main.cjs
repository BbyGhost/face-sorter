const { app, BrowserWindow, dialog, ipcMain } = require('electron');
const path = require('path');
function createWindow() {
  const win = new BrowserWindow({ width: 1200, height: 800, minWidth: 900, minHeight: 620,
    backgroundColor: '#101216', webPreferences: { preload: path.join(__dirname, 'preload.cjs'), contextIsolation: true } });
  win.loadURL(process.env.VITE_DEV_SERVER_URL || `file://${path.join(__dirname, '../dist/index.html')}`);
}
app.whenReady().then(() => { createWindow(); ipcMain.handle('pick-folder', async () => (await dialog.showOpenDialog({ properties: ['openDirectory'] })).filePaths[0] || null); });
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
