# -*- coding: utf-8 -*-
# agent_backend.py (Python 에이전트 백엔드)
import sys, asyncio, os
from browser_use import Agent, Browser, BrowserConfig
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import logging

# UTF-8 인코딩 강제 설정
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['PYTHONUTF8'] = '1'

# 로깅 설정 (이모지 제거)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

def clean_text(text):
    """입력 텍스트에서 surrogates와 문제가 되는 문자들을 제거"""
    if not text:
        return ""
    
    # Surrogates 제거
    cleaned = ""
    for char in text:
        try:
            # 문자를 UTF-8로 인코딩해보고 실패하면 제거
            char.encode('utf-8')
            cleaned += char
        except UnicodeEncodeError:
            continue
    
    return cleaned.strip()

# 브라우저 인스턴스 전역 설정
browser = None
browser_context = None

# 간단한 LLM 및 에이전트 생성 함수
async def run_agent(task):
    global browser, browser_context
    
    # API 키 설정
    load_dotenv()  # .env 파일에서 환경 변수 로드
    
    # 첫 실행시에만 브라우저 초기화
    if browser is None:
        print("Initializing browser session...", flush=True)
        browser = Browser(
            config=BrowserConfig(
                headless=False,
                disable_security=True
            )
        )
        print("Browser initialization complete", flush=True)
        
        # BrowserContext 직접 생성
        from browser_use.browser.context import BrowserContext
        browser_context = BrowserContext(browser=browser)
    
    # 매번 새 에이전트 생성하지만 브라우저와 컨텍스트는 재사용
    model = ChatOpenAI(model='gpt-4o')
    agent = Agent(
        task=task, 
        llm=model,
        browser=browser,
        browser_context=browser_context
    )
    
    # 작업 실행
    try:
        history = await agent.run()
        result = history.final_result()
        # 결과가 있다면 출력, 없으면 "No result" 출력
        if result:
            print(result, flush=True)
        else:
            print("No result", flush=True)
    except Exception as e:
        print(f"Agent execution error: {str(e)}", flush=True)

# 메인: 명령을 지속적으로 읽어 처리
async def main():
    print("Agent ready. Please enter commands.", flush=True)
    
    try:
        # stdin을 라인 단위로 읽어서 처리 (UTF-8 인코딩 강제)
        import io
        sys.stdin = io.TextIOWrapper(sys.stdin.buffer, encoding='utf-8')
        
        for line in sys.stdin:
            # 입력 텍스트 정리
            task = clean_text(line.strip())
            if not task:
                continue  # 빈 명령 무시
            
            print(f"Executing: {task}", flush=True)
            try:
                await run_agent(task)
                print("<END_OF_TASK>", flush=True)  # 작업 완료 표시 (구분자)
            except Exception as e:
                print(f"ERROR: {str(e)}", flush=True)
    except KeyboardInterrupt:
        print("Program interrupted.", flush=True)
    except UnicodeDecodeError as e:
        print(f"Unicode decode error: {str(e)}", flush=True)

# asyncio 이벤트루프 실행
if __name__ == "__main__":
    asyncio.run(main())