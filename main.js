// main.js (헤드리스 일렉트론 앱 - main.py 실행용)
const { app, Tray, Menu, nativeImage } = require('electron');
const { spawn, exec } = require('child_process');
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

function setupProtocolHandler() {
  if (process.defaultApp) {
    if (process.argv.length >= 2) {
      app.setAsDefaultProtocolClient(PROTOCOL_NAME, process.execPath, [path.resolve(process.argv[1])]);
    }
  } else {
    app.setAsDefaultProtocolClient(PROTOCOL_NAME);
  }
}

// 플랫폼별 프로토콜 핸들러 등록
function registerProtocolHandler() {
  if (process.platform === 'darwin') {
    // macOS에서는 앱이 빌드될 때 Info.plist에 정의되므로 별도 등록 불필요
    console.log('🍎 macOS: Protocol handler will be registered via Info.plist');
    return;
  } else if (process.platform === 'win32') {
    registerWindowsProtocolHandler();
  } else if (process.platform === 'linux') {
    registerLinuxProtocolHandler();
  }
}

// Windows 레지스트리에 프로토콜 핸들러 등록
function registerWindowsProtocolHandler() {
  try {
    const exePath = process.execPath.replace(/\\/g, '\\\\');
    console.log(`🪟 Windows: Registering protocol handler for: ${exePath}`);
    
    const commands = [
      {
        cmd: `reg delete "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent" /f`,
        desc: "기존 등록 정리",
        allowFail: true
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
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\shell\\open\\command" /f`,
        desc: "command 키 생성"
      },
      {
        cmd: `reg add "HKEY_CURRENT_USER\\Software\\Classes\\browser-use-agent\\shell\\open\\command" /ve /d "\\"${exePath}\\" \\"%1\\"" /f`,
        desc: "실행 명령어 설정"
      }
    ];
    
    let currentIndex = 0;
    function executeNextCommand() {
      if (currentIndex >= commands.length) {
        console.log('🎉 Windows: 프로토콜 핸들러 등록 완료!');
        return;
      }
      
      const cmdObj = commands[currentIndex];
      console.log(`📝 ${currentIndex + 1}/${commands.length}: ${cmdObj.desc}...`);
      
      const result = spawn('cmd', ['/c', cmdObj.cmd], { 
        stdio: 'pipe',
        windowsHide: true 
      });
      
      result.on('close', (code) => {
        if (code === 0) {
          console.log(`✅ ${cmdObj.desc} - 성공`);
        } else if (cmdObj.allowFail) {
          console.log(`⚠️ ${cmdObj.desc} - 실패했지만 무시 (코드: ${code})`);
        } else {
          console.log(`❌ ${cmdObj.desc} - 실패 (코드: ${code})`);
        }
        
        currentIndex++;
        setTimeout(executeNextCommand, 100);
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
    }
    
    executeNextCommand();
    
  } catch (error) {
    console.error('❌ Windows: Failed to register protocol handler:', error);
  }
}

// Linux 프로토콜 핸들러 등록
function registerLinuxProtocolHandler() {
  console.log('🐧 Linux: Protocol handler registration (desktop file based)');
  // Linux에서는 .desktop 파일을 통해 처리됨
}

// 시스템 트레이 아이콘 생성
function createTray() {
  // 플랫폼별 아이콘 크기 조정
  let iconSize;
  if (process.platform === 'darwin') {
    iconSize = 16; // macOS는 16x16
  } else if (process.platform === 'win32') {
    iconSize = 16; // Windows는 16x16
  } else {
    iconSize = 24; // Linux는 24x24
  }
  
  // 간단한 트레이 아이콘 생성 (더 선명한 아이콘)
  const iconData = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAABHNCSVQICAgIfAhkiAAAAAlwSFlzAAAAdgAAAHYBTnsmCAAAABl0RVh0U29mdHdhcmUAd3d3Lmlua3Njape.org5vuPBoAAAFYSURBVDiNpZM9SwNBEIafgwQLwUKwsLGwsLBQsLCwsLGwsLCwsLGwsLCwsLCwsLGwsLCwsLCwsLGwsLCwsLCwsLGwsLCwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsLCwsLCwsLCwsLGwsA';
  const icon = nativeImage.createFromDataURL(iconData);
  // macOS에서는 템플릿 이미지로 설정 (setSize는 일부 버전에서 지원하지 않음)
  if (process.platform === 'darwin') {
    try {
      icon.setTemplateImage(true);
    } catch (e) {
      console.log('템플릿 이미지 설정 건너뜀');
    }
  }
  
  tray = new Tray(icon);
  
  // 플랫폼별 트레이 메뉴
  const menuTemplate = [
    {
      label: 'Browser-Use Agent',
      enabled: false
    },
    {
      type: 'separator'
    },
    {
      label: '상태: 실행 중',
      enabled: false
    },
    {
      label: '포트: 8999',
      enabled: false
    },
    {
      type: 'separator'
    },
    {
      label: '브라우저에서 열기',
      click: () => {
        require('electron').shell.openExternal('http://localhost:8999');
      }
    },
    {
      type: 'separator'
    },
    {
      label: process.platform === 'darwin' ? '종료' : 'Quit',
      click: () => {
        app.quit();
      }
    }
  ];
  
  const contextMenu = Menu.buildFromTemplate(menuTemplate);
  tray.setToolTip('Browser-Use Agent - 포트 8999에서 실행 중');
  tray.setContextMenu(contextMenu);
  
  // macOS에서는 클릭 이벤트 추가
  if (process.platform === 'darwin') {
    tray.on('click', () => {
      tray.popUpContextMenu();
    });
  }
}

// 알림 기능 제거됨 - 콘솔 로그만 사용

// Python 실행 파일 찾기 (크로스 플랫폼)
function findPython() {
  const pythonCommands = process.platform === 'win32' 
    ? ['python', 'python3', 'py']
    : ['python3', 'python'];
  
  return new Promise((resolve) => {
    let index = 0;
    
    function tryNext() {
      if (index >= pythonCommands.length) {
        resolve(null);
        return;
      }
      
      const cmd = pythonCommands[index];
      exec(`${cmd} --version`, (error) => {
        if (!error) {
          resolve(cmd);
        } else {
          index++;
          tryNext();
        }
      });
    }
    
    tryNext();
  });
}

// Python 백엔드 프로세스 시작
async function startPythonBackend() {
  console.log('🐍 Python 백엔드 시작 중...');
  
  // Python 실행 파일 찾기
  const pythonCmd = await findPython();
  if (!pythonCmd) {
    console.error('❌ Python이 설치되지 않았습니다!');
    console.error('⚠️ Python 3.7 이상을 설치해주세요.');
    return;
  }
  
  console.log(`✅ Python 실행 파일: ${pythonCmd}`);
  
  // main.py 경로 설정
  let pythonScript;
  let pythonCwd;
  
  if (app.isPackaged) {
    // 빌드된 앱에서 경로 찾기 (asarUnpack 사용)
    const possiblePaths = [
      path.join(process.resourcesPath, 'app.asar.unpacked', 'main.py'),  // asarUnpack으로 해제된 파일
      path.join(process.resourcesPath, 'app', 'main.py'),
      path.join(process.resourcesPath, 'main.py'),
      path.join(__dirname, 'main.py')
    ];
    
    for (const testPath of possiblePaths) {
      console.log(`🔍 Checking Python script at: ${testPath}`);
      if (fs.existsSync(testPath)) {
        pythonScript = testPath;
        pythonCwd = path.dirname(testPath);
        console.log(`✅ Found Python script at: ${pythonScript}`);
        break;
      }
    }
  } else {
    // 개발 환경
    pythonScript = path.join(__dirname, 'main.py');
    pythonCwd = __dirname;
  }
  
  if (!pythonScript || !fs.existsSync(pythonScript)) {
    console.error('❌ main.py 파일을 찾을 수 없습니다!');
    console.error(`시도한 경로들:`);
    console.error(`- ${pythonScript}`);
    console.error('⚠️ Python 백엔드 파일을 찾을 수 없습니다.');
    return;
  }
  
  console.log(`📂 Python 스크립트: ${pythonScript}`);
  console.log(`📁 작업 디렉토리: ${pythonCwd}`);
  
  // 환경 변수 설정 (크로스 플랫폼)
  const pythonEnv = {
    ...process.env,
    PYTHONIOENCODING: 'utf-8',
    PYTHONUNBUFFERED: '1',
    PYTHONUTF8: '1'
  };
  
  // macOS에서 PATH 설정
  if (process.platform === 'darwin') {
    pythonEnv.PATH = `/usr/local/bin:/opt/homebrew/bin:${process.env.PATH}`;
  }
  
  // Python 프로세스 실행
  pyProc = spawn(pythonCmd, ['-u', pythonScript], {
    env: pythonEnv,
    cwd: pythonCwd,
    stdio: 'inherit',
    windowsHide: process.platform === 'win32'
  });

  pyProc.on('error', (err) => {
    console.error("❌ Python 백엔드 시작 실패:", err);
    console.error(`⚠️ Python 백엔드 시작 실패: ${err.message}`);
  });
  
  pyProc.on('close', (code) => {
    console.log(`🐍 Python 백엔드가 코드 ${code}로 종료되었습니다`);
    if (code !== 0) {
      console.error('⚠️ Python 백엔드가 예상치 못하게 종료되었습니다.');
      app.quit();
    }
  });
  
  // 백엔드 시작 성공 로그
  setTimeout(() => {
    console.log('✅ 백엔드가 성공적으로 시작되었습니다! http://localhost:8999');
  }, 2000);
}

// Python 프로세스 종료 함수
function terminatePyProc() {
  if (pyProc !== null) {
    console.log('🛑 Python 백엔드 종료 중...');
    if (process.platform === 'win32') {
      spawn('taskkill', ['/pid', pyProc.pid, '/f', '/t']);
    } else {
      pyProc.kill('SIGTERM');
      // 강제 종료가 필요한 경우 대비
      setTimeout(() => {
        if (pyProc && !pyProc.killed) {
          pyProc.kill('SIGKILL');
        }
      }, 5000);
    }
    pyProc = null;
  }
}

// 앱 준비되면 백엔드 시작
app.whenReady().then(async () => {
  // 프로토콜 핸들러 설정
  setupProtocolHandler();
  
  // 트레이 아이콘 생성
  createTray();
  
  // Python 백엔드 시작
  await startPythonBackend();
  
  // 플랫폼별 프로토콜 핸들러 등록
  registerProtocolHandler();

  console.log('🚀 Browser-Use Agent가 백그라운드에서 시작되었습니다');
  console.log('🌐 백엔드: http://localhost:8999');
  
  // 첫 실행 시 프로토콜 URL 처리 (Windows)
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
  console.log(`🔗 macOS/Linux: Protocol URL received: ${url}`);
  handleProtocolUrl(url);
});

// 모든 윈도우가 닫혀도 앱 종료하지 않음 (백그라운드 실행)
app.on('window-all-closed', () => {
  // 백그라운드 실행 유지
});

// 앱 종료 시 Python 프로세스도 종료
app.on('will-quit', terminatePyProc);
app.on('before-quit', terminatePyProc);

// 앱이 활성화될 때 (macOS)
app.on('activate', () => {
  // 백그라운드 실행만 목적이므로 윈도우 생성 안함
});

// 프로토콜 URL 처리 함수
function handleProtocolUrl(url) {
  console.log(`🔗 Protocol URL 수신: ${url}`);
  console.log('🚀 Agent가 준비되었습니다 (백그라운드 실행)');
  
  try {
    const urlObj = new URL(url);
    console.log(`📋 Protocol: ${urlObj.protocol}`);
    console.log(`🏠 Host: ${urlObj.hostname}`);
    console.log(`🔍 Search: ${urlObj.search}`);
    
    // URL 파라미터 처리 로직 추가 가능
  } catch (error) {
    console.error('❌ URL 파싱 오류:', error);
  }
}

// 두 번째 인스턴스 실행 방지
const gotTheLock = app.requestSingleInstanceLock();

if (!gotTheLock) {
  console.log('⚠️ Browser-Use Agent가 이미 실행 중입니다');
  app.quit();
} else {
  app.on('second-instance', (event, commandLine, workingDirectory) => {
    console.log('⚠️ Browser-Use Agent가 이미 실행 중입니다');
    
    // 커스텀 프로토콜 URL 처리
    const protocolUrl = commandLine.find(arg => arg.startsWith('browser-use-agent://'));
    if (protocolUrl) {
      handleProtocolUrl(protocolUrl);
    }
    
    // 이미 실행 중 로그
    console.log('⚠️ Browser-Use Agent가 이미 포트 8999에서 실행 중입니다 (백그라운드)');
  });
}