const { ipcRenderer } = require('electron');

window.onload = function() {
  const input = document.getElementById('commandInput');
  const output = document.getElementById('outputArea');
  const sendBtn = document.getElementById('sendBtn');
  const connectionStatus = document.getElementById('connectionStatus');
  const taskStatus = document.getElementById('taskStatus');

  // 로딩 표시
  connectionStatus.textContent = "상태: 초기화 중...";
  
  // 버튼 클릭 또는 Enter 키로 명령 전송
  function sendCommand() {
    const cmd = input.value;
    if (cmd && cmd.trim() !== "") {
      // 명령 스타일링
      appendToOutput(`<div class="log-entry command">> ${cmd}</div>`);
      
      ipcRenderer.send('userCommand', cmd);
      input.value = "";  // 입력창 비우기
      
      // 명령 전송 후 상태 업데이트
      taskStatus.textContent = "작업: 실행 중...";
      sendBtn.disabled = true;
    }
  }
  
  sendBtn.onclick = sendCommand;
  input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') sendCommand();
  });

  // 출력 영역에 텍스트 추가 (HTML 지원)
  function appendToOutput(html) {
    output.innerHTML += html;
    output.scrollTop = output.scrollHeight;
  }

  // Python 에이전트로부터 결과 수신하여 출력
  ipcRenderer.on('agentResult', (event, data) => {
    // END_OF_TASK 마커 확인
    if (data.includes("<END_OF_TASK>")) {
      taskStatus.textContent = "작업: 완료";
      sendBtn.disabled = false;
      
      // 마커 제거하고 나머지 결과만 출력
      data = data.replace("<END_OF_TASK>", "");
      
      if (data.trim()) {
        appendToOutput(`<div class="log-entry result">${formatOutput(data)}</div>`);
      }
    } 
    // 에러 확인
    else if (data.startsWith("ERROR:") || data.includes("에이전트 실행 오류")) {
      taskStatus.textContent = "작업: 오류 발생";
      sendBtn.disabled = false;
      appendToOutput(`<div class="log-entry error">${formatOutput(data)}</div>`);
    }
    // 일반 결과
    else if (data.trim()) {
      appendToOutput(`<div class="log-entry">${formatOutput(data)}</div>`);
    }
  });
  
  // 에이전트 준비 메시지가 오면 상태 업데이트
  ipcRenderer.on('agentResult', (event, data) => {
    if (data.includes("에이전트 준비 완료")) {
      connectionStatus.textContent = "상태: 연결됨";
      sendBtn.disabled = false;
    }
    else if (data.includes("브라우저 초기화 완료")) {
      connectionStatus.textContent = "상태: 브라우저 준비됨";
    }
  });
  
  // 출력 텍스트 포맷팅 (URL 링크화, 줄바꿈 유지)
  function formatOutput(text) {
    // URL을 링크로 변환
    text = text.replace(
      /(https?:\/\/[^\s]+)/g, 
      '<a href="$1" target="_blank">$1</a>'
    );
    
    // 줄바꿈 유지
    return text.replace(/\n/g, '<br>');
  }
};