# -*- coding: utf-8 -*-
# main.py (FastAPI 백엔드 서버)
import asyncio
import os
import sys
import logging
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from browser_use import Agent, Browser, BrowserConfig
from browser_use.browser.context import BrowserContext
from langchain_openai import ChatOpenAI
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
                disable_security=True
            )
        )
        print("Browser initialization complete", flush=True)
        
        # BrowserContext 생성
        browser_context = BrowserContext(browser=browser)
    
    return browser, browser_context

async def run_agent(task: str):
    """에이전트 실행 - stdout이 자동으로 WebSocket으로 전송됨"""
    global browser, browser_context
    
    try:
        # API 키 설정
        load_dotenv()
        
        # 브라우저 초기화
        browser, browser_context = await init_browser()
        
        # 모델 및 에이전트 생성
        model = ChatOpenAI(model='gpt-4o')
        agent = Agent(
            task=task,
            llm=model,
            browser=browser,
            browser_context=browser_context
        )
        
        # 에이전트 실행 - 모든 출력이 자동으로 WebSocket으로 전송됨
        history = await agent.run()
        result = history.final_result()
        
        # 결과 반환
        if result:
            return result
        else:
            return "No result"
            
    except Exception as e:
        print(f"Agent execution error: {str(e)}")
        return f"Error: {str(e)}"

@app.on_event("startup")
async def startup_event():
    """서버 시작시 브라우저 초기화"""
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
            command_data = json.loads(data)
            command = clean_text(command_data.get("command", ""))
            
            if not command:
                continue
                
            # 에이전트 실행 - 모든 로그가 자동으로 WebSocket으로 전송됨
            result = await run_agent(command)
            
            # 최종 결과 전송
            await websocket.send_text(json.dumps({
                "type": "result",
                "content": result,
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