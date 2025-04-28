import datetime
import json
from typing import List, Dict, Sequence

from sqlmodel import select

from llm.base import BaseLLM
from selector.base import BaseSelector
from web_server.ai.models import Document, Category

# system action
now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
DOCUMENT_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': f"""
            # Role: 文档选择器（Document Selector）
            
            ## Environment variable
            - 当前时间: {now}
            
            ## Profile
            - author: LangGPT 
            - version: 1.1
            - language: 中文
            - description: 一个跨领域、多文档类型的智能文档选择系统。能够根据用户的自然语言查询，识别最相关的一个或多个文档，文档可来自财务、人事、政策、科技、医疗、教育等多个领域，内容类型丰富（公告、报告、指南、协议、新闻等）。
            
            ## Skills
            - 从用户输入中提取关键词（主题对象、行为、时间、领域术语等）
            - 跨领域进行文档匹配，支持多个类型的文档并存（报告、新闻、政策等）
            - 输出结构化 JSON，便于接入段落选择器或摘要生成器
            - 支持排序返回多份相关文档
            
            ## Rules
            1. 响应格式必须为 JSON，包含 `selected_documents`数组；
            2. 匹配依据为 `document_description`，可包括文档主题、内容、发布时间、用途等；
            3. 支持多文档命中（强相关即可返回），优先包含查询关键词的文档；
            4. 支持文档类型多样性：如年报、会议纪要、通知公告、技术说明、法律文件等；
            5. 禁止生成未在文档描述中出现的信息。
            6.`selected_documents`数组中是`document_id`;
            
            ## Workflows
            1. 解析 input_text，提取关键词（实体名、事件、指标、时间、地域等）；
            2. 遍历文档列表，结合关键词在 `document_description` 中的语义出现情况排序；
            3. 返回最相关的一个或多个文档项；
            4. 格式化输出。
            
            ## OutputFormat
            {{
                "selected_documents": ["document_idxxx"]
            }}
            Warning: 
            -输出不要增加额外内容，严格按照Example Output结构输出。
        """
    }
]

# few_shot example input output
DOCUMENT_FEW_SHOT_MESSAGES = [
    {
        'role': 'user',
        'content': """{
            "input_text": "国家出台的双碳目标政策，以及广东省的实施细则和比亚迪的企业响应有哪些？",
            "documents": [
                {
                    "document_id": "d101",
                    "document_description": "《关于完整准确全面贯彻新发展理念做好碳达峰碳中和工作的意见》（国家发改委，2023年3月发布）。"
                },
                {
                    "document_id": "d102",
                    "document_description": "广东省生态环境厅2023年发布《双碳行动实施细则》，涵盖工业转型与交通减排目标。"
                },
                {
                    "document_id": "d103",
                    "document_description": "比亚迪2023年ESG报告披露了碳排放治理策略与电动车产能规划。"
                },
                {
                    "document_id": "d104",
                    "document_description": "国家能源局2022年氢能指导意见，聚焦能源结构调整。"
                },
                {
                    "document_id": "d105",
                    "document_description": "深圳市住建局绿色建筑标准指南，聚焦建筑节能。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d101","d102","d103"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "GPT-5有哪些安全机制方面的提升？",
            "documents": [
                {
                    "document_id": "d01",
                    "document_description": "OpenAI最新发布的GPT-5模型技术白皮书，涉及模型能力、安全性和训练数据情况。"
                },
                {
                    "document_id": "d02",
                    "document_description": "Transformer模型原理介绍，重点讨论注意力机制和多层结构。"
                },
                {
                    "document_id": "d03",
                    "document_description": "2023年AI伦理与算法治理研讨会记录，包含各方观点与政策建议。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d01"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "2024年深圳的小学入学政策和时间安排是怎样的？",
            "documents": [
                {
                    "document_id": "d10",
                    "document_description": "深圳市教育局2024年义务教育招生政策问答，包括入学条件、材料清单与时间节点。"
                },
                {
                    "document_id": "d11",
                    "document_description": "广州教育局2023年小学招生简章，适用于天河、越秀等区域。"
                },
                {
                    "document_id": "d12",
                    "document_description": "教育部关于优化义务教育阶段招生制度的指导意见（全国适用）。"
                }   
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d10"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "请提供比亚迪2023年财务表现、环境责任和高管变动相关内容。",
            "documents": [
                {
                    "document_id": "d01",
                    "document_description": "比亚迪2023年第四季度财务报告，包含净利润、营收、资产结构等关键财务数据。"
                },
                {
                    "document_id": "d02",
                    "document_description": "比亚迪2023年ESG环境责任报告，聚焦碳排放、资源利用与社会公益项目。"
                },
                {
                    "document_id": "d03",
                    "document_description": "比亚迪2023年高管人事公告，涉及CEO变动与董事会新任命。"
                },
                {
                    "document_id": "d04",
                    "document_description": "比亚迪2022年年度报告，涵盖全年业务与股东信息。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d01","d02","d03"]
        }"""
    }
]

# user input
DOCUMENT_USER_PROMPT = [
    {
        'role': 'user',
    }
]


class DocumentSelector(BaseSelector):
    def __init__(self, params):
        super().__init__(params)
        self.documents = self.get_layer_data()
        self.select_params = []

    def get_layer_data(self) -> Sequence[Dict]:
        kb_id = self.params.kb_id
        session = self.params.session
        statement = select(Document).where(Document.kb_id == kb_id)
        db_documents = session.exec(statement).all()
        documents = []
        for document in db_documents:
            documents.append({
                'document_id': document.category_id,
                'document_description': f'{document.category_description};{document.parent_description}'
            })
        return documents

    def collate_select_params(self, selected_categories: List[Dict] = None):
        session = self.params.session
        for category_id in selected_categories:
            db_category = session.get(Category, category_id)
            self.select_params = [{
                'document_id': doc.document_id,
                'document_description': f'{doc.document_description};{doc.parent_description}'
            } for doc in db_category.documents]

        if len(self.select_params) == 0:
            self.select_params = self.documents

        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        DOCUMENT_USER_PROMPT[0]['content'] = {
            'input_text': question,
            'documents': self.select_params
        }
        response_chat = llm.chat(DOCUMENT_SYSTEM_MESSAGES + DOCUMENT_FEW_SHOT_MESSAGES + DOCUMENT_USER_PROMPT)

        return response_chat[0]
