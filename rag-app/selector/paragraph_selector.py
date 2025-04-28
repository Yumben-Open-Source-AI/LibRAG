import json
import datetime
from typing import List, Dict

from sqlmodel import select

from llm.base import BaseLLM
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
            "input_text": "2023年新能源汽车补贴申请流程与审核标准",
            "paragraphs": [
                {
                    "paragraph_id": "p01",
                    "paragraph_description": "2023年新能源补贴政策更新，包含申请条件、审核标准及适用车型。"
                },
                {
                    "paragraph_id": "p02",
                    "paragraph_description": "补贴申报流程说明，包括企业登录、资料提交、平台初审等步骤。"
                },
                {
                    "paragraph_id": "p03",
                    "paragraph_description": "技术标准部分，规定新能源车需满足电池密度、安全性等指标。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": ["p01","p02"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "实验设计和评估指标",
            "paragraphs": [
                {
                    "paragraph_id": "r01",
                    "paragraph_description": "实验方法部分描述了训练数据来源、模型结构及对比模型。"
                },
                {
                    "paragraph_id": "r02",
                    "paragraph_description": "评估指标包括F1分数、准确率、召回率，评估在三个数据集上的表现。"
                },
                {
                    "paragraph_id": "r03",
                    "paragraph_description": "引言介绍了背景、研究动机和贡献。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": ["r01","r02"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "双减政策”实施成效和教师满意度",
            "paragraphs": [
                {
                    "paragraph_id": "edu01",
                    "paragraph_description": "‘双减’政策背景说明及政策条文要点摘要。"
                },
                {
                    "paragraph_id": "edu02",
                    "paragraph_description": "调研数据部分显示家长满意度提升，但部分教师仍有备课负担。"
                },
                {
                    "paragraph_id": "edu03",
                    "paragraph_description": "调查问卷分析：教师群体对政策实施后的教学节奏、工作压力的反馈。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": ["edu02","edu03"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "比亚迪什么时候召开了董事会会议，并披露了哪些议案？",
            "paragraphs": [
                {
                    "paragraph_id": "a01",
                    "paragraph_description": "这是比亚迪财务报告第一页，主要内容是财务摘要与声明信息。"
                },
                {
                    "paragraph_id": "a02",
                    "paragraph_description": "本段内容为比亚迪2024年3月董事会会议内容，包含会议时间、议案主题、披露媒体。"
                },
                {
                    "paragraph_id": "a03",
                    "paragraph_description": "股东信息页面，介绍股东持股比例、质押情况等。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_paragraphs": ["a02"]
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
                'paragraph_id': paragraph.paragraph_id,
                'paragraph_description': f'{paragraph.category_description};{paragraph.parent_description}'
            })
        return paragraphs

    def collate_select_params(self, selected_documents: List[Dict] = None):
        session = self.params.session
        for doc_id in selected_documents:
            db_doc = session.get(Document, doc_id)
            self.select_params = [{
                'paragraph_id': paragraph.paragraph_id,
                'paragraph_description': f'{paragraph.summary};{paragraph.parent_description}'
            } for paragraph in db_doc.paragraphs]

        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        PARAGRAPH_USER_MESSAGES[0]['content'] = {
            'input_text': question,
            'paragraphs': self.select_params
        }
        response_chat = llm.chat(PARAGRAPH_SYSTEM_MESSAGES + PARAGRAPH_FEW_SHOT_MESSAGES + PARAGRAPH_USER_MESSAGES)
        self.selected_paragraphs = set(response_chat[0]['selected_paragraphs'])

        return self

    def collate_select_result(self) -> List:
        if len(self.selected_paragraphs) == 0:
            return []

        session = self.params.session
        result = []
        for paragraph_id in self.selected_paragraphs:
            result.append(session.get(Paragraph, paragraph_id).dict())

        return result
