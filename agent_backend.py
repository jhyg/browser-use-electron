# -*- coding: utf-8 -*-
# agent_backend.py (Python 에이전트 백엔드)
import sys, asyncio
from browser_use import Agent, Browser, BrowserConfig
from langchain_openai import ChatOpenAI
import os

# 브라우저 인스턴스 전역 설정
browser = None
browser_context = None

# 간단한 LLM 및 에이전트 생성 함수
async def run_agent(task):
    global browser, browser_context
    
    # API 키 설정
    os.environ['OPENAI_API_KEY'] = 'sk-'  
    
    # 첫 실행시에만 브라우저 초기화
    if browser is None:
        print("브라우저 세션 초기화 중...", flush=True)
        browser = Browser(
            config=BrowserConfig(
                headless=False,
                disable_security=True
            )
        )
        print("브라우저 초기화 완료", flush=True)
        
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
        print(f"에이전트 실행 오류: {str(e)}", flush=True)

# 메인: 명령을 지속적으로 읽어 처리
async def main():
    print("에이전트 준비 완료. 명령을 입력하세요.", flush=True)
    
    try:
        # stdin을 라인 단위로 읽어서 처리
        for line in sys.stdin:
            task = line.strip()
            if not task:
                continue  # 빈 명령 무시
            
            print(f"수행 중: {task}", flush=True)
            try:
                await run_agent(task)
                print("<END_OF_TASK>", flush=True)  # 작업 완료 표시 (구분자)
            except Exception as e:
                print(f"ERROR: {e}", flush=True)
    except KeyboardInterrupt:
        print("프로그램이 중단되었습니다.", flush=True)

# asyncio 이벤트루프 실행
if __name__ == "__main__":
    asyncio.run(main())