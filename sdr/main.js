const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const dgram = require('dgram');
const server = dgram.createSocket('udp4');
let win;

 // Spawn the external Python app executable
 const pythonApp = spawn('./sdr_script', []);

 pythonApp.stdout.on('data', (data) => {
     console.log(`stdout: ${data}`);
 });

 pythonApp.stderr.on('data', (data) => {
     console.error(`stderr: ${data}`);
 });

 pythonApp.on('close', (code) => {
     console.log(`child process exited with code ${code}`);
     win.webContents.send('python-exit', 'SDR Error: Please Restart');
 });

server.on('error', (err) => {
  console.log(`Server error:\n${err.stack}`);
  server.close();
});

server.on('message', (msg, rinfo) => {
  console.log(`Server got: ${msg} from ${rinfo.address}:${rinfo.port}`);
  if (win) {
    console.log("test");
    win.webContents.send('udp-message', msg.toString());
  }
});

server.on('listening', () => {
  const address = server.address();
  console.log(`Server listening ${address.address}:${address.port}`);
});

server.bind(5006); // UDP port

function createWindow () {
  // Create the browser window.
  win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  win.loadFile('index.html').then(() => {
    // Only send messages after the window has loaded
    win.webContents.send('test-channel', 'Hello from main process');
});
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
      app.quit();
  }
});

app.on('quit', () => {
  // Kill the Python process when the Electron app is about to quit
  if (pythonApp && !pythonApp.killed) {
      pythonApp.kill();
  }
});