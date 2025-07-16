import asyncio
from browser_use import Agent, Browser, BrowserConfig
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

async def test_genspark():
    try:
        # OpenAI 모델 설정
        llm = ChatOpenAI(model="gpt-4o", temperature=0.1)
        
        # 브라우저 설정
        browser_config = BrowserConfig(
            headless=False,
            disable_security=True
        )
        
        # 브라우저 생성
        browser = Browser(config=browser_config)
        
        # 에이전트 생성
        agent = Agent(
            task="""
            1. https://www.genspark.ai/ 사이트에 접속하세요
            2. "무엇이든 물어보고 만들어보세요" 버튼을 찾아 클릭하세요
            3. 입력창에 "성과급 신청서 pptx 생성"을 입력하세요
            4. 생성된 pptx 파일을 다운로드하세요
            5. 다운로드된 파일의 경로를 알려주세요
            
            각 단계에서 화면의 요소들을 정확히 인식하고 있는지 상세히 설명해주세요.
            만약 요소를 찾지 못한다면 그 이유를 자세히 설명해주세요.
            """,
            llm=llm,
            browser=browser
        )
        
        # 에이전트 실행
        result = await agent.run()
        print("=== 작업 완료 ===")
        print(f"결과: {result}")
        
        # 브라우저 닫기
        await browser.close()
        
    except Exception as e:
        print(f"오류 발생: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_genspark()) 