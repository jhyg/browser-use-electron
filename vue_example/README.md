# Vue 프론트엔드 통합 가이드

현재 브라우저 에이전트 프로젝트를 Vue 프론트엔드에 통합하는 방법을 설명합니다.

## 1. 백엔드 서버 실행

### 의존성 설치
```bash
pip install -r requirements.txt
```

### 환경 변수 설정
`.env` 파일 생성:
```env
OPENAI_API_KEY=your_openai_api_key_here
```

### 서버 실행
```bash
python main.py
```
