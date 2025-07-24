# -*- coding: utf-8 -*-
# main.py (FastAPI 백엔드 서버)
import asyncio
import os
import sys
import logging
import threading
import time
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from browser_use import Agent, Browser, BrowserConfig, BrowserContext, ChatOpenAI
from dotenv import load_dotenv
import json

# UTF-8 인코딩 강제 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# FastAPI 앱 생성
app = FastAPI(title="Browser Agent API", version="1.0.0")

# CORS 설정 (Vue 프론트엔드에서 접근 가능하도록)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실제 배포시에는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 브라우저 인스턴스
browser = None
browser_context = None

# 활성 WebSocket 연결들 (실시간 로그 전송용)
active_websockets = set()

# 태스크 관리를 위한 전역 변수들
current_task_thread = None
task_stop_flag = threading.Event()
task_result = None
task_error = None
task_status = "idle"  # idle, running, stopping, completed, error
current_agent = None

# stdout을 WebSocket으로 리디렉션하는 클래스
class WebSocketWriter:
    def __init__(self, original_stdout):
        self.original_stdout = original_stdout
    
    def write(self, text):
        # 원본 stdout에도 출력 (콘솔에서 보기 위해)
        self.original_stdout.write(text)
        self.original_stdout.flush()
        
        # WebSocket으로도 전송
        if text.strip():
            for ws in active_websockets.copy():
                try:
                    asyncio.create_task(ws.send_text(json.dumps({
                        "type": "log",
                        "content": text.strip(),
                        "level": "INFO",
                        "timestamp": asyncio.get_event_loop().time()
                    })))
                except Exception:
                    active_websockets.discard(ws)
    
    def flush(self):
        self.original_stdout.flush()
    
    def isatty(self):
        return self.original_stdout.isatty()

# stdout 교체
original_stdout = sys.stdout
sys.stdout = WebSocketWriter(original_stdout)

# 로깅도 WebSocket으로 전송하는 핸들러
class WebSocketLogHandler(logging.Handler):
    def emit(self, record):
        try:
            log_message = self.format(record)
            for ws in active_websockets.copy():
                try:
                    asyncio.create_task(ws.send_text(json.dumps({
                        "type": "log",
                        "content": log_message,
                        "level": record.levelname,
                        "timestamp": asyncio.get_event_loop().time()
                    })))
                except Exception:
                    active_websockets.discard(ws)
        except Exception:
            pass

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(original_stdout),  # 콘솔 출력용
        WebSocketLogHandler()  # WebSocket 전송용
    ]
)

# 요청 모델
class CommandRequest(BaseModel):
    command: str

def clean_text(text):
    """입력 텍스트에서 surrogates와 문제가 되는 문자들을 제거"""
    if not text:
        return ""
    
    cleaned = ""
    for char in text:
        try:
            char.encode('utf-8')
            cleaned += char
        except UnicodeEncodeError:
            continue
    
    return cleaned.strip()

async def init_browser():
    """브라우저 초기화"""
    global browser, browser_context
    
    if browser is None:
        print("Initializing browser session...", flush=True)
        browser = Browser(
            config=BrowserConfig(
                headless=False,
                disable_security=True,
                keep_alive=True
            )
        )
        print("Browser initialization complete", flush=True)
        
        # BrowserContext 생성 (새 버전에서는 BrowserSession과 동일)
        browser_context = browser
    
    return browser, browser_context



def run_agent_sync(task: str):
    """동기 에이전트 실행 함수 (스레드에서 실행됨)"""
    global browser, browser_context, task_result, task_error, task_status, task_stop_flag, current_agent
    
    try:
        task_status = "running"
        task_result = None
        task_error = None
        
        print(f"🚀 Starting task: {task}", flush=True)
        
        # API 키 설정
        load_dotenv()
        
        # 중지 플래그 확인
        if task_stop_flag.is_set():
            print("❌ Task was stopped before execution", flush=True)
            task_status = "stopped"
            return
        
        # 모델 및 에이전트 생성
        model = ChatOpenAI(model='gpt-4.1')
        agent = Agent(
            task=task,
            llm=model,
            browser=browser
        )
        
        # 전역 에이전트 참조 저장
        current_agent = agent
        
        print("🤖 Agent is working...", flush=True)
        
        # 에이전트 실행을 별도 함수로 래핑
        def run_browser_agent():
            import asyncio
            
            async def agent_runner():
                try:
                    # 중지 모니터링 태스크 생성
                    async def monitor_stop_flag():
                        while not task_stop_flag.is_set():
                            await asyncio.sleep(0.1)
                        # 중지 플래그가 설정되면 에이전트 중지
                        if current_agent and hasattr(current_agent, 'state'):
                            current_agent.state.stopped = True
                            print("🛑 Agent stop flag set", flush=True)
                    
                    # 모니터링 태스크 시작
                    monitor_task = asyncio.create_task(monitor_stop_flag())
                    
                    # 에이전트 실행과 모니터링을 동시에 실행
                    agent_task = asyncio.create_task(agent.run())
                    
                    # 둘 중 하나가 완료되면 결과 반환
                    done, pending = await asyncio.wait(
                        [agent_task, monitor_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    # 대기 중인 태스크들 취소
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass
                    
                    # 에이전트 태스크가 완료되었는지 확인
                    if agent_task in done:
                        history = await agent_task
                        result = history.final_result()
                        return result if result else "No result"
                    else:
                        return "Task was stopped by user"
                    
                except Exception as e:
                    return f"Agent error: {str(e)}"
            
            # 새로운 이벤트 루프에서 실행
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                return loop.run_until_complete(agent_runner())
            finally:
                loop.close()
        
        # 에이전트 실행
        task_result = run_browser_agent()
        
        if task_stop_flag.is_set():
            task_status = "stopped"
            task_result = "Task was stopped by user"
        else:
            task_status = "completed"
            print("✅ Task completed", flush=True)
        
    except Exception as e:
        print(f"❌ Agent execution error: {str(e)}", flush=True)
        task_error = str(e)
        task_status = "error"
    finally:
        # 에이전트 참조 정리
        current_agent = None

async def run_agent(task: str):
    """에이전트 실행 - 스레드 기반으로 제어 가능"""
    global current_task_thread, task_stop_flag, task_result, task_error, task_status
    
    # 이미 실행 중인 태스크가 있으면 중지
    if current_task_thread and current_task_thread.is_alive():
        print("⚠️ Another task is running. Stopping it first...", flush=True)
        await stop_current_task()
    
    # 중지 플래그 초기화
    task_stop_flag.clear()
    task_status = "starting"
    
    # 새 스레드에서 에이전트 실행
    current_task_thread = threading.Thread(
        target=run_agent_sync,
        args=(task,),
        daemon=True
    )
    current_task_thread.start()
    
    # 스레드 완료 대기
    while current_task_thread.is_alive():
        await asyncio.sleep(0.1)
        
        # 중지 요청이 있으면 대기 중단
        if task_stop_flag.is_set():
            break
    
    # 결과 반환
    if task_error:
        return f"Error: {task_error}"
    elif task_result:
        return task_result
    else:
        return "No result"

async def stop_current_task():
    """현재 실행 중인 태스크 중지"""
    global current_task_thread, task_stop_flag, task_status, current_agent
    
    if current_task_thread and current_task_thread.is_alive():
        print("🛑 Stopping current task...", flush=True)
        task_status = "stopping"
        
        # 1. browser-use 에이전트 직접 중지
        if current_agent and hasattr(current_agent, 'state'):
            current_agent.state.stopped = True
            print("🛑 Agent state.stopped = True", flush=True)
        
        # 2. 중지 플래그 설정
        task_stop_flag.set()
        print("🛑 Stop flag set", flush=True)
        
        # 스레드가 종료될 때까지 잠시 대기
        for i in range(50):  # 최대 5초 대기
            if not current_task_thread.is_alive():
                break
            await asyncio.sleep(0.1)
            
            # 진행 상황 표시
            if i % 10 == 0:
                print(f"⏳ Waiting for task to stop... ({i/10:.1f}s)", flush=True)
        
        if current_task_thread.is_alive():
            print("⚠️ Task thread did not stop gracefully", flush=True)
            # 강제 종료를 위한 추가 시도
            try:
                import threading
                if hasattr(threading, '_shutdown'):
                    print("🔄 Attempting force cleanup...", flush=True)
            except:
                pass
        else:
            print("✅ Task stopped successfully", flush=True)
        
        return True
    else:
        print("ℹ️ No active task to stop", flush=True)
        return False

async def check_and_install_playwright():
    """Playwright 브라우저 설치 확인 및 설치"""
    try:
        import subprocess
        import os
        from pathlib import Path
        import glob
        
        print("Checking Playwright browsers...", flush=True)
        
        # 고정된 브라우저 설치 경로 설정
        browser_path = Path.home() / ".browser-use-agent" / "browsers"
        browser_path.mkdir(parents=True, exist_ok=True)
        
        # PLAYWRIGHT_BROWSERS_PATH 환경 변수 설정
        os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(browser_path)
        
        # 모든 브라우저 종류 확인 (chromium, firefox, webkit 포함)
        browser_found = False
        
        # 가능한 모든 브라우저 패턴 확인
        patterns = [
            "chromium-*/chrome-win/chrome.exe",
            "chromium-*/chrome-win/chrome.exe",
            "firefox-*/firefox.exe",
            "webkit-*/Playwright.exe",
            "winldd-*/PrintDeps.exe",  # winldd 브라우저 추가
        ]
        
        for pattern in patterns:
            matches = glob.glob(str(browser_path / pattern))
            if matches:
                browser_found = True
                print(f"✅ Found browser: {matches[0]}", flush=True)
                break
        
        if not browser_found:
            print("Installing Playwright browsers (this may take a few minutes)...", flush=True)
            print(f"Browser installation path: {browser_path}", flush=True)
            
            # Playwright의 Python API를 사용해서 브라우저 설치
            try:
                from playwright._impl._driver import compute_driver_executable, get_driver_env
                from playwright._impl._api_types import BrowserType
                
                # Playwright 설치 시도
                install_result = subprocess.run(
                    [sys.executable, "-m", "playwright", "install"],
                    capture_output=True,
                    text=True,
                    timeout=600,  # 10분 제한
                    env=os.environ.copy()
                )
                
                if install_result.returncode == 0:
                    print("✅ Playwright browsers installed successfully!", flush=True)
                else:
                    print(f"⚠️ Playwright installation warning: {install_result.stderr}", flush=True)
                    print("Trying alternative installation...", flush=True)
                    
                    # 대체 설치 방법 시도
                    alt_install_result = subprocess.run(
                        [sys.executable, "-m", "playwright", "install", "chromium"],
                        capture_output=True,
                        text=True,
                        timeout=600,
                        env=os.environ.copy()
                    )
                    
                    if alt_install_result.returncode == 0:
                        print("✅ Chromium browser installed successfully!", flush=True)
                    else:
                        print("Falling back to system Chrome...", flush=True)
                        setup_system_chrome()
                        
            except Exception as install_error:
                print(f"⚠️ Browser installation failed: {str(install_error)}", flush=True)
                print("Falling back to system Chrome...", flush=True)
                setup_system_chrome()
        else:
            print("✅ Playwright browsers already installed", flush=True)
            
    except subprocess.TimeoutExpired:
        print("⚠️ Playwright installation timed out", flush=True)
        print("Trying system Chrome as fallback...", flush=True)
        setup_system_chrome()
    except Exception as e:
        print(f"⚠️ Playwright setup error: {str(e)}", flush=True)
        print("Trying system Chrome as fallback...", flush=True)
        setup_system_chrome()

def setup_system_chrome():
    """시스템 Chrome 설정"""
    try:
        from pathlib import Path
        import os
        
        # 시스템 Chrome 경로 확인
        system_chrome_paths = [
            "C:/Program Files/Google/Chrome/Application/chrome.exe",
            "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
            Path.home() / "AppData/Local/Google/Chrome/Application/chrome.exe"
        ]
        
        for chrome_path in system_chrome_paths:
            if Path(chrome_path).exists():
                print(f"✅ Found system Chrome at: {chrome_path}", flush=True)
                os.environ["PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"] = str(chrome_path)
                return True
        
        print("⚠️ No system Chrome found, browser functionality may be limited", flush=True)
        return False
    except Exception as e:
        print(f"⚠️ System Chrome setup error: {str(e)}", flush=True)
        return False

@app.on_event("startup")
async def startup_event():
    """서버 시작시 Playwright 설치 확인 및 브라우저 초기화"""
    print("Starting Browser Agent API Server...", flush=True)
    
    # Playwright 브라우저 설치 확인 및 설치
    await check_and_install_playwright()
    
    # 브라우저 초기화
    await init_browser()
    print("Browser Agent API Server is ready!", flush=True)

@app.on_event("shutdown")
async def shutdown_event():
    """서버 종료시 브라우저 정리"""
    global browser
    if browser:
        await browser.close()
        print("Browser closed", flush=True)

@app.get("/")
async def root():
    """서버 상태 확인"""
    return {"message": "Browser Agent API Server is running"}

@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {"status": "healthy", "browser_ready": browser is not None}

@app.get("/api/task/status")
async def get_task_status():
    """현재 태스크 상태 조회"""
    global task_status, current_task_thread
    
    is_running = current_task_thread is not None and current_task_thread.is_alive()
    
    return {
        "status": task_status,
        "is_running": is_running,
        "can_stop": is_running and task_status in ["running", "starting"]
    }

@app.post("/api/task/stop")
async def stop_task():
    """현재 태스크 중지"""
    stopped = await stop_current_task()
    
    return {
        "success": stopped,
        "message": "Task stopped successfully" if stopped else "No active task to stop",
        "status": task_status
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket을 통한 실시간 로그 스트리밍"""
    await websocket.accept()
    
    # WebSocket을 활성 연결 목록에 추가
    active_websockets.add(websocket)
    
    try:
        # 연결 확인 메시지
        await websocket.send_text(json.dumps({
            "type": "info",
            "content": "Agent ready. Please enter commands.",
            "timestamp": asyncio.get_event_loop().time()
        }))
        
        while True:
            # 클라이언트로부터 명령 수신
            data = await websocket.receive_text()
            print(f"🔍 Raw WebSocket message received: {data}", flush=True)
            
            try:
                command_data = json.loads(data)
                print(f"🔍 Parsed command_data: {command_data}", flush=True)
            except json.JSONDecodeError as e:
                print(f"❌ JSON parsing error: {e}", flush=True)
                continue
            
            # 메시지 타입 확인
            message_type = command_data.get("type", "")
            print(f"🔍 Message type: '{message_type}'", flush=True)
            
            if message_type == "stop_request":
                # 태스크 중지 요청 처리
                print("📨 Received stop request from client", flush=True)
                print(f"🔍 Current task status: {task_status}", flush=True)
                print(f"🔍 Thread alive: {current_task_thread.is_alive() if current_task_thread else False}", flush=True)
                print(f"🔍 Agent exists: {current_agent is not None}", flush=True)
                
                stopped = await stop_current_task()
                
                # 중지 결과 전송
                await websocket.send_text(json.dumps({
                    "type": "stop_result",
                    "content": "Task stopped successfully" if stopped else "No active task to stop",
                    "success": stopped,
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
                # 작업 완료 마커
                await websocket.send_text(json.dumps({
                    "type": "end",
                    "content": "<TASK_STOPPED>",
                    "timestamp": asyncio.get_event_loop().time()
                }))
                
                continue
            
            # 일반 명령 처리
            command = clean_text(command_data.get("prompt", ""))
            
            if not command:
                continue
            
            # 현재 태스크 상태 전송
            await websocket.send_text(json.dumps({
                "type": "task_status",
                "content": f"Starting task: {command}",
                "status": "starting",
                "timestamp": asyncio.get_event_loop().time()
            }))
                
            # 에이전트 실행 - 모든 로그가 자동으로 WebSocket으로 전송됨
            result = await run_agent(command)
            
            # 최종 결과 전송
            await websocket.send_text(json.dumps({
                "type": "result",
                "content": result,
                "status": task_status,
                "timestamp": asyncio.get_event_loop().time()
            }))
            
            # 작업 완료 마커
            await websocket.send_text(json.dumps({
                "type": "end",
                "content": "<END_OF_TASK>",
                "timestamp": asyncio.get_event_loop().time()
            }))
                
    except WebSocketDisconnect:
        print("WebSocket disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        # WebSocket을 활성 연결 목록에서 제거
        active_websockets.discard(websocket)

@app.post("/api/execute")
async def execute_command(request: CommandRequest):
    """HTTP POST로 명령 실행"""
    command = clean_text(request.command)
    
    if not command:
        raise HTTPException(status_code=400, detail="Command is required")
    
    try:
        result = await run_agent(command)
        return {
            "success": True,
            "result": result,
            "command": command
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8999, log_level="info") 