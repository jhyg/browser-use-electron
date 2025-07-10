// main.js (헤드리스 일렉트론 앱 - main.py 실행용)
const { app, Tray, Menu, nativeImage } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
let pyProc = null;
let tray = null;

// 하드웨어 가속 비활성화
app.disableHardwareAcceleration();

// 백그라운드 실행 허용
app.commandLine.appendSwitch('--disable-background-timer-throttling');
app.commandLine.appendSwitch('--disable-backgrounding-occluded-windows');
app.commandLine.appendSwitch('--disable-renderer-backgrounding');

// 커스텀 프로토콜 등록 (browser-use-agent://)
const PROTOCOL_NAME = 'browser-use-agent';
if (process.defaultApp) {
  if (process.argv.length >= 2) {
    app.setAsDefaultProtocolClient(PROTOCOL_NAME, process.execPath, [path.resolve(process.argv[1])]);
  }
} else {
  app.setAsDefaultProtocolClient(PROTOCOL_NAME);
}

// 시스템 트레이 아이콘 생성
function createTray() {
  // 간단한 트레이 아이콘 생성
  const icon = nativeImage.createFromDataURL('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==');
  tray = new Tray(icon);
  
  // 트레이 메뉴 생성
  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Browser-Use Agent',
      enabled: false
    },
    {
      type: 'separator'
    },
    {
      label: 'Status: Running',
      enabled: false
    },
    {
      label: 'Port: 8999',
      enabled: false
    },
    {
      type: 'separator'
    },
    {
      label: 'Open in Browser',
      click: () => {
        require('electron').shell.openExternal('http://localhost:8999');
      }
    },
    {
      type: 'separator'
    },
    {
      label: 'Quit',
      click: () => {
        app.quit();
      }
    }
  ]);
  
  tray.setToolTip('Browser-Use Agent - Running on port 8999');
  tray.setContextMenu(contextMenu);
}

// Python 백엔드 프로세스 시작
function startPythonBackend() {
  console.log('Starting Python backend (main.py)...');
  
  // main.py 경로 설정 (개발 환경 vs 빌드 환경)
  let pythonScript;
  if (app.isPackaged) {
    // 빌드된 앱에서는 resources/app 폴더에서 찾기
    pythonScript = path.join(process.resourcesPath, 'app', 'main.py');
  } else {
    // 개발 환경에서는 현재 디렉토리
    pythonScript = path.join(__dirname, 'main.py');
  }
  
  // 파일 존재 확인
  if (!fs.existsSync(pythonScript)) {
    console.error(`Python script not found at: ${pythonScript}`);
    // 대체 경로들 시도
    const alternatives = [
      path.join(__dirname, 'main.py'),
      path.join(process.resourcesPath, 'main.py'),
      path.join(process.cwd(), 'main.py')
    ];
    
    for (const alt of alternatives) {
      if (fs.existsSync(alt)) {
        pythonScript = alt;
        console.log(`Found Python script at: ${pythonScript}`);
        break;
      }
    }
  }
  
  console.log(`Python script path: ${pythonScript}`);
  
  // main.py 실행 (UTF-8 인코딩 강제)
  pyProc = spawn('python', ['-u', pythonScript], {
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUNBUFFERED: '1',
      PYTHONUTF8: '1'
    },
    stdio: 'inherit' // 콘솔에 직접 출력
  });

  pyProc.on('error', (err) => {
    console.error("Failed to start Python backend:", err);
  });
  
  pyProc.on('close', (code) => {
    console.log(`Python backend exited with code ${code}`);
    if (code !== 0) {
      app.quit();
    }
  });
}

// Python 프로세스 종료 함수
function terminatePyProc() {
  if (pyProc !== null) {
    console.log('Terminating Python backend...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', pyProc.pid, '/f', '/t']);
    } else {
      pyProc.kill('SIGTERM');
    }
    pyProc = null;
  }
}

// 앱 준비되면 백엔드 시작
app.whenReady().then(() => {
  // 트레이 아이콘 생성
  createTray();
  
  // Python 백엔드 시작
  startPythonBackend();
  
  console.log('Browser-Use Agent started in background');
  console.log('Backend running on http://localhost:8999');
  
  // 첫 실행 시 프로토콜 URL 처리
  if (process.platform === 'win32') {
    const protocolUrl = process.argv.find(arg => arg.startsWith('browser-use-agent://'));
    if (protocolUrl) {
      handleProtocolUrl(protocolUrl);
    }
  }
});

// macOS/Linux에서 프로토콜 URL 처리
app.on('open-url', (event, url) => {
  event.preventDefault();
  handleProtocolUrl(url);
});

// 모든 윈도우가 닫혀도 앱 종료하지 않음 (백그라운드 실행)
app.on('window-all-closed', () => {
  // 백그라운드 실행 유지
});

// 앱 종료 시 Python 프로세스도 종료
app.on('will-quit', terminatePyProc);

// 앱이 활성화될 때 (macOS)
app.on('activate', () => {
  // 백그라운드 실행만 목적이므로 윈도우 생성 안함
});

// 프로토콜 URL 처리 함수
function handleProtocolUrl(url) {
  console.log(`Protocol URL received: ${url}`);
  
  if (tray) {
    tray.displayBalloon({
      title: 'Browser-Use Agent',
      content: 'Agent is starting up...'
    });
  }
  
  // URL에서 매개변수 추출 (예: browser-use-agent://start?param=value)
  const urlObj = new URL(url);
  console.log(`Protocol: ${urlObj.protocol}`);
  console.log(`Host: ${urlObj.hostname}`);
  console.log(`Search: ${urlObj.search}`);
}

// 두 번째 인스턴스 실행 방지
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  app.quit();
} else {
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    // 이미 실행 중인 인스턴스가 있다면 알림
    console.log('Browser-Use Agent is already running');
    
    // 커스텀 프로토콜 URL 처리
    const protocolUrl = commandLine.find(arg => arg.startsWith('browser-use-agent://'));
    if (protocolUrl) {
      handleProtocolUrl(protocolUrl);
    }
    
    // 트레이 아이콘 클릭 효과
    if (tray) {
      tray.displayBalloon({
        title: 'Browser-Use Agent',
        content: 'Already running on port 8999'
      });
    }
  });
}