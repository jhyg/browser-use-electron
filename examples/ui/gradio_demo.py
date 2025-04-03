import os
import sys
sys.path.insert(0, os.path.abspath("."))
import asyncio
from dataclasses import dataclass
from typing import List, Optional

# Third-party imports
import gradio as gr
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from rich.console import Console
from rich.panel import Panel
from rich.text import Text
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from pynput import mouse, keyboard
import time
from datetime import datetime
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
import pyautogui

# Local module imports
from browser_use import Agent
from browser_use.agent.task_improver_prompt import get_task_improvement_prompt

load_dotenv()


@dataclass
class ActionResult:
	is_done: bool
	extracted_content: Optional[str]
	error: Optional[str]
	include_in_memory: bool


@dataclass
class AgentHistoryList:
	all_results: List[ActionResult]
	all_model_outputs: List[dict]


def parse_agent_history(history_str: str) -> None:
	console = Console()

	# Split the content into sections based on ActionResult entries
	sections = history_str.split('ActionResult(')

	for i, section in enumerate(sections[1:], 1):  # Skip first empty section
		# Extract relevant information
		content = ''
		if 'extracted_content=' in section:
			content = section.split('extracted_content=')[1].split(',')[0].strip("'")

		if content:
			header = Text(f'Step {i}', style='bold blue')
			panel = Panel(content, title=header, border_style='blue')
			console.print(panel)
			console.print()


async def improve_user_task(task: str, api_key: str) -> str:
	os.environ['OPENAI_API_KEY'] = api_key
	llm = ChatOpenAI(model='gpt-4o')
	
	recording_content = ""
	try:
		with open('user_recording.txt', 'r', encoding='utf-8') as f:
			recording_content = f.read()
	except Exception as e:
		print(f"Warning: Could not read recording file: {str(e)}")
  
	improved_task = llm.invoke(get_task_improvement_prompt(task, recording_content))
	return str(improved_task.content)


async def run_browser_task(
	task: str,
	api_key: str,
	model: str = 'gpt-4o',
	headless: bool = True,
) -> str:
	if not api_key.strip():
		return 'Please provide an API key'

	os.environ['OPENAI_API_KEY'] = api_key
	try:
		# improved_task = await improve_user_task(task, api_key)

		sensitive_data = {
			'github_username': 'wkdwo8703@gmail.com',
			'github_password': '@'
		}
  
		agent = Agent(
			task=task,
			# task=improved_task,
			llm=ChatOpenAI(model=model),
			sensitive_data=sensitive_data
		)
		result = await agent.run()
		return str(result)
	except Exception as e:
		return f'Error: {str(e)}'


class BrowserRecorder:
	def __init__(self, url: str, output_file: str):
		self.url = url
		self.output_file = 'user_recording.txt'
		self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
		self.recording = False
		self.step_number = 1

	def start_recording(self):
		self.driver.get(self.url)
		time.sleep(3)
		self.recording = True
		
		self.driver.execute_script("""
			window.recordedActions = [];
			window.lastClickTime = 0;
			window.lastInputValue = '';
			window.mouseDownTime = 0;
			window.initialMousePosition = null;
			
			// 마우스 다운 시 초기 위치와 시간 기록
			document.addEventListener('mousedown', function(e) {
				window.mouseDownTime = Date.now();
				window.initialMousePosition = {x: e.clientX, y: e.clientY};
				window.dragStart = {
					element: e.target.cloneNode().outerHTML,
					x: e.clientX,
					y: e.clientY
				};
			}, true);

			// 마우스 업 시 동작 판단 및 기록
			document.addEventListener('mouseup', function(e) {
				const mouseUpTime = Date.now();
				const timeDiff = mouseUpTime - window.mouseDownTime;
				const moveDistance = window.initialMousePosition ? 
					Math.hypot(e.clientX - window.initialMousePosition.x, e.clientY - window.initialMousePosition.y) : 0;
				
				// 드래그 앤 드롭 (이동 거리가 5px 이상일 때)
				if (moveDistance > 3) {
					window.recordedActions.push({
						type: 'drag_and_drop',
						source: window.dragStart.element,
						target: {x: e.clientX, y: e.clientY}
					});
				}
				// 더블클릭 (300ms 이내의 두 번째 클릭)
				else if (timeDiff < 300 && window.lastClickTime && (mouseUpTime - window.lastClickTime < 300)) {
					window.recordedActions.push({
						type: 'doubleclick',
						element: e.target.cloneNode().outerHTML,
						x: e.clientX,
						y: e.clientY
					});
					window.lastClickTime = 0;  // 더블클릭 후 타이머 리셋
				}
				// 일반 클릭
				else if (moveDistance <= 5) {
					window.recordedActions.push({
						type: 'click',
						element: e.target.cloneNode().outerHTML,
						x: e.clientX,
						y: e.clientY
					});
					window.lastClickTime = mouseUpTime;
				}
				
				// 상태 리셋
				window.initialMousePosition = null;
				window.dragStart = null;
			}, true);

			// 입력 이벤트 (최종 값만 기록)
			document.addEventListener('input', function(e) {
				window.lastInputValue = e.target.value;
				clearTimeout(window.inputTimeout);
				window.inputTimeout = setTimeout(function() {
					if (window.lastInputValue !== '') {
						window.recordedActions.push({
							type: 'input',
							element: e.target.cloneNode().outerHTML,
							value: window.lastInputValue
						});
						window.lastInputValue = '';
					}
				}, 1000);
			}, true);
		""")
		
		return "Recording started. Browser window opened. Press 'Stop Recording' when finished."

	def stop_recording(self):
		if not self.recording:
			return "No recording in progress"
			
		self.recording = False
		recorded_actions = self.driver.execute_script("return window.recordedActions;")
		
		with open(self.output_file, 'w', encoding='utf-8') as f:
			f.write(f"url: {self.url}\n\n")
			
			for action in recorded_actions:
				if action['type'] == 'drag_and_drop':
					f.write(f"{self.step_number}. {action['type']}\n")
					f.write(f"- Source: {action['source']}\n")
					f.write(f"- Target: ({action['target']['x']}, {action['target']['y']})\n")
					self.step_number += 1

				elif action['type'] == 'click':
					f.write(f"{self.step_number}. {action['type']}\n")
					f.write(f"- Element: {action['element']}\n")
					f.write(f"- Position: ({action['x']}, {action['y']})\n")
					self.step_number += 1

				elif action['type'] == 'input':
					f.write(f"{self.step_number}. {action['type']}\n")
					f.write(f"- Element: {action['element']}\n")
					f.write(f"- Value: {action['value']}\n")
					self.step_number += 1

		self.driver.quit()
		return f"Recording stopped. Steps saved to {self.output_file}"

	def _get_element_description(self, element_info):
		"""요소에 대한 읽기 쉬운 설명 생성"""
		if element_info['text']:
			return f"{element_info['tag']} with text '{element_info['text']}'"
		elif element_info['alt']:
			return f"image with alt '{element_info['alt']}'"
		elif element_info['title']:
			return f"{element_info['tag']} with title '{element_info['title']}'"
		elif element_info['src']:
			return f"image from '{element_info['src'].split('/')[-1]}'"
		elif element_info['id']:
			return f"{element_info['tag']} with id '{element_info['id']}'"
		elif element_info['class']:
			return f"{element_info['tag']} with class '{element_info['class']}'"
		return element_info['tag']

	def _get_element_locator(self, element_info):
		"""요소를 찾기 위한 가장 적절한 locator 반환"""
		if element_info['id']:
			return f"(By.ID, '{element_info['id']}')"
		elif element_info['class']:
			return f"(By.CLASS_NAME, '{element_info['class'].split()[0]}')"
		elif element_info['text']:
			return f"(By.XPATH, \"//*[contains(text(), '{element_info['text']}')]\")"
		return f"(By.TAG_NAME, '{element_info['tag']}')"

async def handle_recording(url: str, output_file: str, action: str, recorder_state) -> tuple:
	# recorder_state가 None이면 빈 딕셔너리로 초기화
	if recorder_state is None:
		recorder_state = {}
		
	if action == "Start":
		if not url.strip():
			return "Please enter a URL first", recorder_state
			
		try:
			recorder = BrowserRecorder(url, output_file)
			result = recorder.start_recording()
			recorder_state = {"recorder": recorder}
			return result, recorder_state
		except Exception as e:
			return f"Error starting recording: {str(e)}", recorder_state
			
	elif action == "Stop":
		try:
			if isinstance(recorder_state, dict) and recorder_state.get('recorder'):
				result = recorder_state['recorder'].stop_recording()
				recorder_state = {}
				return result, recorder_state
		except Exception as e:
			return f"Error stopping recording: {str(e)}", recorder_state
			
	return "No recording in progress", recorder_state


def create_ui():
	with gr.Blocks(title='Browser Use GUI') as interface:
		gr.Markdown('# Browser Use Task Automation')

		with gr.Tab("Task Automation"):
			with gr.Row():
				with gr.Column():
					api_key = gr.Textbox(label='OpenAI API Key', placeholder='sk-...', type='password')
					task = gr.Textbox(
						label='Task Description',
						placeholder='E.g., Find flights from New York to London for next week',
						lines=3,
					)
					model = gr.Dropdown(
						choices=['gpt-4o', 'gpt-3.5-turbo'], label='Model', value='gpt-4o'
					)
					headless = gr.Checkbox(label='Run Headless', value=True)
					submit_btn = gr.Button('Run Task')

				with gr.Column():
					output = gr.Textbox(label='Output', lines=10, interactive=False)

			submit_btn.click(
				fn=lambda *args: asyncio.run(run_browser_task(*args)),
				inputs=[task, api_key, model, headless],
				outputs=output,
			)

		with gr.Tab("Record Browser Actions"):
			recorder_state = gr.State(value=None)
			
			with gr.Row():
				with gr.Column():
					url_input = gr.Textbox(
						label="URL to Record",
						placeholder="Enter the URL (e.g., https://example.com)"
					)
					record_btn = gr.Button("Start/Stop Recording")
				
				with gr.Column():
					recording_output = gr.Textbox(
						label="Recording Status",
						lines=10,
						interactive=False
					)
			
			record_btn.click(
				fn=lambda url, state: asyncio.run(handle_recording(
					url=url,
					output_file="user_recording.txt",
					action="Stop" if state and state.get('recorder') else "Start",
					recorder_state=state
				)),
				inputs=[url_input, recorder_state],
				outputs=[recording_output, recorder_state]
			)

	return interface


if __name__ == '__main__':
	demo = create_ui()
	demo.launch()