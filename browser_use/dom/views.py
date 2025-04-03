from dataclasses import dataclass
from functools import cached_property
from typing import TYPE_CHECKING, Dict, List, Optional

from browser_use.dom.history_tree_processor.view import CoordinateSet, HashedDomElement, ViewportInfo
from browser_use.utils import time_execution_sync

# Avoid circular import issues
if TYPE_CHECKING:
	from .views import DOMElementNode


@dataclass(frozen=False)
class DOMBaseNode:
	is_visible: bool
	# Use None as default and set parent later to avoid circular reference issues
	parent: Optional['DOMElementNode']


@dataclass(frozen=False)
class DOMTextNode(DOMBaseNode):
	text: str
	type: str = 'TEXT_NODE'

	def has_parent_with_highlight_index(self) -> bool:
		current = self.parent
		while current is not None:
			# stop if the element has a highlight index (will be handled separately)
			if current.highlight_index is not None:
				return True

			current = current.parent
		return False

	def is_parent_in_viewport(self) -> bool:
		if self.parent is None:
			return False
		return self.parent.is_in_viewport

	def is_parent_top_element(self) -> bool:
		if self.parent is None:
			return False
		return self.parent.is_top_element


@dataclass(frozen=False)
class DOMElementNode(DOMBaseNode):
	"""
	xpath: the xpath of the element from the last root node (shadow root or iframe OR document if no shadow root or iframe).
	To properly reference the element we need to recursively switch the root node until we find the element (work you way up the tree with `.parent`)
	"""

	tag_name: str
	xpath: str
	attributes: Dict[str, str]
	children: List[DOMBaseNode]
	is_interactive: bool = False
	is_top_element: bool = False
	is_in_viewport: bool = False
	shadow_root: bool = False
	highlight_index: Optional[int] = None
	viewport_coordinates: Optional[CoordinateSet] = None
	page_coordinates: Optional[CoordinateSet] = None
	viewport_info: Optional[ViewportInfo] = None

	def __repr__(self) -> str:
		tag_str = f'<{self.tag_name}'

		# Add attributes
		for key, value in self.attributes.items():
			tag_str += f' {key}="{value}"'
		tag_str += '>'

		# Add extra info
		extras = []
		if self.is_interactive:
			extras.append('interactive')
		if self.is_top_element:
			extras.append('top')
		if self.shadow_root:
			extras.append('shadow-root')
		if self.highlight_index is not None:
			extras.append(f'highlight:{self.highlight_index}')
		if self.is_in_viewport:
			extras.append('in-viewport')

		if extras:
			tag_str += f' [{", ".join(extras)}]'

		return tag_str

	@cached_property
	def hash(self) -> HashedDomElement:
		from browser_use.dom.history_tree_processor.service import (
			HistoryTreeProcessor,
		)

		return HistoryTreeProcessor._hash_dom_element(self)

	def get_all_text_till_next_clickable_element(self, max_depth: int = -1) -> str:
		text_parts = []

		def collect_text(node: DOMBaseNode, current_depth: int) -> None:
			if max_depth != -1 and current_depth > max_depth:
				return

			# Skip this branch if we hit a highlighted element (except for the current node)
			if isinstance(node, DOMElementNode) and node != self and node.highlight_index is not None:
				return

			if isinstance(node, DOMTextNode):
				text_parts.append(node.text)
			elif isinstance(node, DOMElementNode):
				for child in node.children:
					collect_text(child, current_depth + 1)

		collect_text(self, 0)
		return '\n'.join(text_parts).strip()

	@time_execution_sync('--clickable_elements_to_string')
	def clickable_elements_to_string(self, include_attributes: list[str] = []) -> str:
		formatted_text = []
		
		def find_icon_class(node: DOMElementNode) -> str:
			"""재귀적으로 i 태그를 찾아 클래스를 반환"""
			if node.tag_name == 'i':
				return node.attributes.get('class', '')
			
			for child in node.children:
				if isinstance(child, DOMElementNode):
					icon_class = find_icon_class(child)
					if icon_class:
						return icon_class
			return ''
		
		def process_node(node: DOMBaseNode, depth: int) -> None:
			if isinstance(node, DOMElementNode):
				if node.highlight_index is not None:
					attributes_str = ''
					
					# 이미지 태그 처리
					if node.tag_name == 'img':
						src = node.attributes.get('src', '')
						attributes_str = f' src="{src}"'
					
					# g 태그 처리 (생성된 노드 그룹)
					elif node.tag_name == 'g':
						node_id = node.attributes.get('id', '')
						# g 태그 내의 모든 text 내용 찾기
						type_text = ''
						label_text = ''
						for child in node.children:
							if isinstance(child, DOMElementNode) and child.tag_name == 'text':
								text_content = child.get_all_text_till_next_clickable_element().strip()
								if '<<' in text_content:  # type 텍스트
									type_text = text_content.replace('<<', '').replace('>>', '').strip()
								else:  # 라벨 텍스트
									label_text = text_content
						
						if type_text or label_text:
							attributes_str = f' id="{node_id}"'
							if type_text:
								attributes_str += f' type="{type_text}"'
							if label_text:
								attributes_str += f' label="{label_text}"'

					# rect 태그 처리 추가
					elif node.tag_name == 'rect':
						node_id = node.attributes.get('id', '')
						x = node.attributes.get('x', '')
						y = node.attributes.get('y', '')
						attributes_str = f' id="{node_id}"'
						if x and y:
							attributes_str += f' x="{x}" y="{y}"'
					
					# 버튼 태그 처리
					elif node.tag_name == 'button':
						icon_class = find_icon_class(node)
						if icon_class:
							attributes_str += f' icon="{icon_class}"'
					
					# input 태그 처리
					elif node.tag_name == 'input':
						input_id = node.attributes.get('id', '')
						input_type = node.attributes.get('type', '')
						# 상위 label 찾기
						parent = node.parent
						while parent:
							for child in parent.children:
								if (isinstance(child, DOMElementNode) and 
									child.tag_name == 'label' and 
									child.attributes.get('for') == input_id):
									label_text = child.get_all_text_till_next_clickable_element()
									attributes_str = f' label="{label_text}"'
									break
							if attributes_str:
								break
							parent = parent.parent
					
					# 다른 요청된 속성들 추가
					if include_attributes:
						attributes_str += ' ' + ' '.join(
							f'{key}="{value}"' 
							for key, value in node.attributes.items() 
							if key in include_attributes
						)
					
					element_text = f'[{node.highlight_index}]<{node.tag_name}{attributes_str}>'
					formatted_text.append(element_text)

				for child in node.children:
					process_node(child, depth + 1)
			elif isinstance(node, DOMTextNode):
				if not node.has_parent_with_highlight_index() and node.is_parent_top_element() and node.is_visible:
					formatted_text.append(f'[]{node.text}')

		process_node(self, 0)
		
		result = '\n'.join(formatted_text)
		print("\n=== String Passed to LLM ===")
		# print(result) dom_element_string
		
		return result

	def get_file_upload_element(self, check_siblings: bool = True) -> Optional['DOMElementNode']:
		# Check if current element is a file input
		if self.tag_name == 'input' and self.attributes.get('type') == 'file':
			return self

		# Check children
		for child in self.children:
			if isinstance(child, DOMElementNode):
				result = child.get_file_upload_element(check_siblings=False)
				if result:
					return result

		# Check siblings only for the initial call
		if check_siblings and self.parent:
			for sibling in self.parent.children:
				if sibling is not self and isinstance(sibling, DOMElementNode):
					result = sibling.get_file_upload_element(check_siblings=False)
					if result:
						return result

		return None


SelectorMap = dict[int, DOMElementNode]


@dataclass
class DOMState:
	element_tree: DOMElementNode
	selector_map: SelectorMap
