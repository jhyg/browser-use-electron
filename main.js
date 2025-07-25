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

// Windows 레지스트리에 프로토콜 핸들러 등록
function registerProtocolHandler() {
  if (process.platform !== 'win32') return;
  
  try {
    const exePath = process.execPath.replace(/\\/g, '\\\\'); // 백슬래시 이스케이프
    console.log(`🔧 Registering protocol handler for: ${exePath}`);
    
    // 레지스트리 명령어들 (순서가 중요함)
    const commands = [
      {
        cmd: `reg delete "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent" /f`,
        desc: "기존 등록 정리",
        allowFail: true // 처음 실행시엔 없을 수 있음
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent" /f`,
        desc: "기본 키 생성"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent" /ve /d "URL:Browser Use Agent Protocol" /f`,
        desc: "프로토콜 기본 설명"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent" /v "URL Protocol" /d "" /f`,
        desc: "URL 프로토콜 플래그"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\DefaultIcon" /f`,
        desc: "DefaultIcon 키 생성"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\DefaultIcon" /ve /d "\\"${exePath}\\",0" /f`,
        desc: "기본 아이콘 설정"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\shell" /f`,
        desc: "shell 키 생성"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\shell\\open" /f`,
        desc: "open 키 생성"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\shell\\open\\command" /f`,
        desc: "command 키 생성"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\shell\\open\\command" /ve /d "\\"${exePath}\\" \\"%1\\"" /f`,
        desc: "실행 명령어 설정"
      }
    ];
    
    // 순차적으로 실행 (동기적으로)
    let currentIndex = 0;
    
    function executeNextCommand() {
      if (currentIndex >= commands.length) {
        console.log('🎉 프로토콜 핸들러 등록 완료!');
        // 등록 확인
        verifyRegistration(exePath);
        return;
      }
      
      const cmdObj = commands[currentIndex];
      console.log(`📝 ${currentIndex + 1}/${commands.length}: ${cmdObj.desc}...`);
      
      try {
        const result = spawn('cmd', ['/c', cmdObj.cmd], { 
          stdio: 'pipe',
          windowsHide: true 
        });
        
        let output = '';
        let errorOutput = '';
        
        result.stdout.on('data', (data) => {
          output += data.toString();
        });
        
        result.stderr.on('data', (data) => {
          errorOutput += data.toString();
        });
        
        result.on('close', (code) => {
          if (code === 0) {
            console.log(`✅ ${cmdObj.desc} - 성공`);
          } else if (cmdObj.allowFail) {
            console.log(`⚠️ ${cmdObj.desc} - 실패했지만 무시 (코드: ${code})`);
          } else {
            console.log(`❌ ${cmdObj.desc} - 실패 (코드: ${code})`);
            if (errorOutput) {
              console.log(`   오류: ${errorOutput.trim()}`);
            }
          }
          
          currentIndex++;
          // 다음 명령어 실행
          setTimeout(executeNextCommand, 100); // 100ms 대기
        });
        
        result.on('error', (error) => {
          if (cmdObj.allowFail) {
            console.log(`⚠️ ${cmdObj.desc} - 오류 무시: ${error.message}`);
          } else {
            console.log(`❌ ${cmdObj.desc} - 오류: ${error.message}`);
          }
          currentIndex++;
          setTimeout(executeNextCommand, 100);
        });
        
      } catch (error) {
        console.error(`❌ ${cmdObj.desc} - 예외 발생:`, error);
        currentIndex++;
        setTimeout(executeNextCommand, 100);
      }
    }
    
    // 첫 번째 명령어 실행 시작
    executeNextCommand();
    
  } catch (error) {
    console.error('❌ Failed to register protocol handler:', error);
  }
}

// 등록 확인 함수
function verifyRegistration(exePath) {
  console.log('🔍 레지스트리 등록 확인 중...');
  
  const verifyCmd = 'reg query "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\shell\\open\\command"';
  
  try {
    const result = spawn('cmd', ['/c', verifyCmd], { 
      stdio: 'pipe',
      windowsHide: true 
    });
    
    let output = '';
    result.stdout.on('data', (data) => {
      output += data.toString();
    });
    
    result.on('close', (code) => {
      if (code === 0 && output.includes(exePath.replace(/\\\\/g, '\\'))) {
        console.log('✅ 프로토콜 핸들러 등록 확인됨!');
        console.log('🌟 브라우저에서 browser-use-agent:// 링크 사용 가능');
      } else {
        console.log('⚠️ 프로토콜 핸들러 등록 확인 실패');
        console.log('   수동 등록이 필요할 수 있습니다.');
      }
    });
    
  } catch (error) {
    console.log('⚠️ 등록 확인 중 오류:', error.message);
  }
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
  
  // Python 프로세스의 작업 디렉토리 설정
  let pythonCwd;
  if (app.isPackaged) {
    pythonCwd = path.join(process.resourcesPath, 'app');
  } else {
    pythonCwd = __dirname;
  }
  
  console.log(`Python working directory: ${pythonCwd}`);
  
  // main.py 실행 (UTF-8 인코딩 강제)
  pyProc = spawn('python', ['-u', pythonScript], {
    env: {
      ...process.env,
      PYTHONIOENCODING: 'utf-8',
      PYTHONUNBUFFERED: '1',
      PYTHONUTF8: '1'
    },
    cwd: pythonCwd, // 작업 디렉토리 명시적 설정
    stdio: 'inherit', // 콘솔에 직접 출력
    windowsHide: true
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
  
  // Windows 레지스트리에 프로토콜 핸들러 등록
  registerProtocolHandler();

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