import datetime
import uuid

from typing import List, Dict
from sqlmodel import select
from selector.base import BaseSelector
from web_server.ai.models import Paragraph, Document

# system action
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
PARAGRAPH_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': f"""
            # Role: 段落选择器（Paragraph Selector）
            
            ## Environment variable
            - 当前时间: {now}
            
            ## Profile
            - author: LangGPT 
            - version: 1.1
            - language: 中文
            - description: 一个智能文档段落匹配器，基于用户查询意图提取关键词，并在结构化文档段落中匹配最相关的一个或多个段落，支持多段落联合返回，适用于多来源、多类型段落匹配任务。
            
            ## Skills
            - 提取用户问题中的语义关键词（对象、行为、时间、指标等）
            - 匹配多个语义相关度较高的段落（支持多选）
            - 排序输出匹配度前几的段落
            - 返回标准化 JSON 数据结构，便于下游使用
            
            ## Rules
            1. 所有返回必须为 JSON 格式，包含`selected_paragraphs`数组；
            2. 匹配依据包括关键词覆盖、内容上下文、指标匹配度；
            3. 支持多段落匹配返回，特别是在多个段落分别包含用户关心的信息时；
            4. 禁止返回与问题无关段落，不生成虚假信息；
            5. 输出段落数应保持数据准确，并按相关性排序；
            6.`selected_paragraphs`数组中是`paragraph_id`；
            7. 可通过`paragraph_description`中的段落来源描述进行辅助选择；
            
            ## Workflows
            1. 解析 input_text，提取查询关键词（如公司名、时间、指标、行为）；
            2. 遍历 paragraphs，结合 `paragraph_description` 判断相关性；
            3. 筛选并排序多个相关段落；
            4. 返回结构化结果：命中段落id列表。
            
            ## OutputFormat
            {{
                "selected_paragraphs": ["paragraph_idxxx"]
            }}
            Warning: 
            -输出不要增加额外内容，严格按照Example Output结构输出。
        """
    }
]

# few shot example input output
PARAGRAPH_FEW_SHOT_MESSAGES = [
    {
        'role': 'user',
        'content': """{
            "input_text": "比亚迪 2024 年氢燃料电池业务收入是多少？",
            "paragraphs": [
                {
                    "paragraph_id": "p001",
                    "paragraph_description": "报告披露 2024 年电动汽车营业收入 4800 亿元；段落来源描述:<比亚迪 2024 年年度报告。>"
                },
                {
                    "paragraph_id": "p002",
                    "paragraph_description": "报告披露 2024 年动力电池出货量数据；段落来源描述:<比亚迪 2024 年年度报告。>"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": []
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "请给出比亚迪 2024 年四个季度各自的营业收入。",
            "paragraphs": [
                {
                    "paragraph_id": "Q1‑revenue",
                    "paragraph_description": "2024Q1 营业收入 1200 亿元；段落来源描述:<比亚迪 2024 年第一季度报告 第 2 页。>"
                },
                {
                    "paragraph_id": "Q2‑revenue",
                    "paragraph_description": "2024Q2 营业收入 1350 亿元；段落来源描述:<比亚迪 2024 年半年度报告 第 3 页。>"
                },
                {
                    "paragraph_id": "Q3‑revenue",
                    "paragraph_description": "2024Q3 营业收入 1420 亿元；段落来源描述:<比亚迪 2024 年第三季度报告 第 2 页。>"
                },
                {
                    "paragraph_id": "Q4‑revenue",
                    "paragraph_description": "2024Q4 营业收入 1600 亿元；段落来源描述:<比亚迪 2024 年年度报告 第 4 页。>"
                },
                {
                    "paragraph_id": "distractor‑cost",
                    "paragraph_description": "2024Q3 营业**成本** 1100 亿元；段落来源描述:<比亚迪 2024 年第三季度报告。>"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": ["Q1‑revenue", "Q2‑revenue", "Q3‑revenue", "Q4‑revenue"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "Tesla 2023 Q3 total revenue (USD) 是多少？",
            "paragraphs": [
                {
                    "paragraph_id": "uuid‑123e4567-e89b-12d3-a456-426614174000",
                    "paragraph_description": "2023Q3 revenue reached USD 23.35 bn；段落来源描述:<Tesla Inc. 2023 Q3 Update 2023‑10‑18。>"
                },
                {
                    "paragraph_id": "rev‑2023Q2",
                    "paragraph_description": "2023Q2 revenue USD 24.93 bn；段落来源描述:<Tesla Inc. 2023 Q2 Update。>"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": ["uuid‑123e4567-e89b-12d3-a456-426614174000"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "2025 年第一季度营业收入同比增长率是多少？",
            "paragraphs": [
                {
                    "paragraph_id": "rev‑growth",
                    "paragraph_description": "2025Q1 营业收入同比增长 18%；段落来源描述:<某公司 2025 年第一季度报告 第 5 页。>"
                },
                {
                    "paragraph_id": "cost‑growth",
                    "paragraph_description": "2025Q1 营业**成本**同比增长 16%；段落来源描述:<某公司 2025 年第一季度报告 第 6 页。>"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": ["rev‑growth"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "列出 2023 药品目录细则附录 B 中申请材料清单及提交时限的段落。",
            "paragraphs": [
                {
                    "paragraph_id": "segA12",
                    "paragraph_description": "附录 B 要求企业提交 8 项材料并在 30 日内完成；段落来源描述:<国家医保局《药品目录调整实施细则（2023）》2023‑04‑10。>"
                },
                {
                    "paragraph_id": "segA13",
                    "paragraph_description": "附录 B 列出申请材料清单（无时限说明）；段落来源描述:<国家医保局《药品目录调整实施细则（2023）》2023‑04‑10。>"
                },
                {
                    "paragraph_id": "segC01",
                    "paragraph_description": "附录 C 规定申报窗口开放 45 日；段落来源描述:<国家医保局《药品目录调整实施细则（2023）》2023‑04‑10。>"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": ["segA12"]
        }"""
    }
]

PARAGRAPH_USER_MESSAGES = [
    {
        'role': 'user'
    }
]


class ParagraphSelector(BaseSelector):
    def __init__(self, params):
        super().__init__(params)
        self.categories = self.get_layer_data()
        self.select_params = []
        self.selected_paragraphs = None

    def get_layer_data(self):
        kb_id = self.params.kb_id
        session = self.params.session
        statement = select(Paragraph).where(Paragraph.kb_id == kb_id)
        db_paragraphs = session.exec(statement).all()
        paragraphs = []
        for paragraph in db_paragraphs:
            paragraphs.append({
                'paragraph_id': paragraph.paragraph_id.__str__(),
                'paragraph_description': f'{paragraph.parent_description};{paragraph.parent_description}'
            })
        return paragraphs

    def collate_select_params(self, selected_documents: List[Dict] = None):
        session = self.params.session
        for doc_id in selected_documents:
            db_doc = session.get(Document, uuid.UUID(doc_id))
            self.select_params.extend([{
                'paragraph_id': paragraph.paragraph_id.__str__(),
                'paragraph_description': f'{paragraph.summary};{paragraph.parent_description}'
            } for paragraph in db_doc.paragraphs])

        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        PARAGRAPH_USER_MESSAGES[0]['content'] = str({
            'input_text': question,
            'paragraphs': self.select_params
        })
        response_chat = llm.chat(PARAGRAPH_SYSTEM_MESSAGES + PARAGRAPH_FEW_SHOT_MESSAGES + PARAGRAPH_USER_MESSAGES, count=10)
        self.selected_paragraphs = set(response_chat)

        return self

    def collate_select_result(self) -> List:
        if len(self.selected_paragraphs) == 0:
            return []

        session = self.params.session
        result = []
        for paragraph_id in self.selected_paragraphs:
            result.append(session.get(Paragraph, uuid.UUID(paragraph_id)).dict())

        return result
