import json
import datetime
from typing import List, Dict

from llm.base import BaseLLM
from selector.base import BaseSelector

# system action
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
PARAGRAPH_SYSTEM_PROMPT = [
    {
        'role': 'system',
        'content': f"""
            ### 当前时间
            {now}
            ### 工作描述
            您是一个智能文档匹配引擎，能够理解用户输入的查询，并在预定义的文档列表中匹配最相关的文档。您的任务是分析用户输入，从中提取关键词，并基于文档描述选择最符合的文档。
            ### 任务
            1. **关键词提取**：从用户输入中提取有助于匹配的关键词。
            2. **文档匹配**：根据提取的关键词，匹配与之最相关的文档。
            3. **格式化输出**：仅返回 JSON 格式的数据，包括提取的关键词和匹配的文档。
            ### 输入格式
            - `input_text`：用户输入的一段自由文本，表示用户的查询需求。
            - `documents`：可选的文档列表，每个文档包含：
              - `document_id`（文档唯一标识）
              - `document_description`（文档描述信息）
            - `classification_instructions`（可选）：额外的匹配指令（如有）。
            ### 约束
            - **仅返回 JSON 格式的响应**，不得包含额外的文本解释。
            - **不得生成虚假信息**，仅基于已有的 `documents` 进行匹配。
        """
    }
]

PARAGRAPH_FEW_SHOT_PROMPT = [
    {
        'role': 'user',
        ''
    }
]


class ParagraphSelector(BaseSelector):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.paragraphs = self.get_layer_data()
        self.selected_paragraphs = None

    def get_layer_data(self) -> List[Dict]:
        with open('data/byd_info.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        return data

    def start_select(self):
        response_chat = self.llm.chat(PARAGRAPH_SYSTEM_PROMPT)
        content, total_token = response_chat
        self.selected_paragraphs = self.llm.literal_eval(content)
        return self
