// main.js (Electron 메인 프로세스)
const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
let pyProc = null;
let mainWindow = null;

// 하드웨어 가속 비활성화
app.disableHardwareAcceleration();

// GPU 프로세스 설정
app.commandLine.appendSwitch('disable-gpu');
app.commandLine.appendSwitch('disable-gpu-compositing');
app.commandLine.appendSwitch('disable-gpu-rasterization');

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1100, 
    height: 800,
    webPreferences: {
      preload: __dirname + '/renderer.js',
      nodeIntegration: true, 
      contextIsolation: false
    }
  });
  
  // 메인 창 로드
  mainWindow.loadFile('index.html');

  // Python 백엔드 프로세스 실행
  pyProc = spawn('python3', ['-u', 'agent_backend.py']);

  // Python stdout 수신하여 renderer에 결과 전달
  pyProc.stdout.on('data', (data) => {
    const text = data.toString();
    console.log("[Python]", text);
    mainWindow.webContents.send('agentResult', text);
  });

  pyProc.stderr.on('data', (data) => {
    console.error("[Python Error]", data.toString());
  });

  pyProc.on('error', (err) => {
    console.error("Failed to start Python process:", err);
  });
  
  pyProc.on('close', () => {
    console.log("Python process exited.");
  });
  
  // 창이 닫힐 때 이벤트 처리
  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// 앱 준비되면 창 생성
app.whenReady().then(createWindow);

// Python 프로세스 종료 함수
function terminatePyProc() {
  if (pyProc !== null) {
    console.log('Terminating Python process...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', pyProc.pid, '/f', '/t']);
    } else {
      pyProc.kill();
    }
    pyProc = null;
  }
}

// 앱 종료 시 Python 프로세스도 종료
app.on('will-quit', terminatePyProc);

// ipcMain: 렌더러로부터 명령을 수신하여 Python에 전달
ipcMain.on('userCommand', (event, command) => {
  if (pyProc) {
    pyProc.stdin.write(command + "\n");
  }
});