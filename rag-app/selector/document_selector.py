import datetime
import json
import uuid
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
            "input_text": "苹果公司2024年第二季度的营收情况如何？",
            "documents": [
                {
                    "document_id": "d201",
                    "document_description": "Apple Inc. 2024财年第一季度（Q1）财报，发布日期：2024年2月。"
                },
                {
                    "document_id": "d202",
                    "document_description": "Apple Inc. 2024财年第二季度（Q2）财报，发布日期：2024年5月，披露营收、净利润等关键指标。"
                },
                {
                    "document_id": "d203",
                    "document_description": "Apple Inc. 2023年度可持续发展报告，聚焦环保与供应链。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d202"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "国家医保局2024年发布的药品目录调整相关政策和实施指南有哪些？",
            "documents": [
                {
                    "document_id": "d301",
                    "document_description": "国家医保局《2024年药品目录调整方案》（2024年3月）"
                },
                {
                    "document_id": "d302",
                    "document_description": "国家医保局《药品目录调整实施细则（2024）》详细说明落地流程，发布日期：2024年4月。"
                },
                {
                    "document_id": "d303",
                    "document_description": "2023年药品目录调整回顾报告，国家医保局政策解读。"
                },
                {
                    "document_id": "d304",
                    "document_description": "国家卫健委2024年医疗服务价格指导意见。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d301","d302"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "深圳市2025年1月发布的住房租赁政策最新通知是什么？",
            "documents": [
                {
                    "document_id": "d401",
                    "document_description": "深圳市住房和建设局《关于调整住房租赁扶持政策》的通知，发布日期：2025年1月10日。"
                },
                {
                    "document_id": "d402",
                    "document_description": "深圳市住房租赁市场分析报告（2024年第四季度）。"
                },
                {
                    "document_id": "d403",
                    "document_description": "广东省住房租赁管理办法（2023年修订版）。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d401"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "我想了解ISO 27001与ISO 27701之间的主要差异，有没有对比分析报告？",
            "documents": [
                {
                    "document_id": "d501",
                    "document_description": "《ISO 27001信息安全管理体系实施指南》，2023年版。"
                },
                {
                    "document_id": "d502",
                    "document_description": "《ISO 27701隐私信息管理体系实施指南》，2023年版。"
                },
                {
                    "document_id": "d503",
                    "document_description": "《ISO 27001与ISO 27701差异对比白皮书》，2024年发布，系统比较两大标准要求差异。"
                },
                {
                    "document_id": "d504",
                    "document_description": "《企业信息安全年度报告2024》。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d503"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "教育部发布的中小学人工智能课程标准以及2024年下半年的配套教师培训手册请提供。",
            "documents": [
                {
                    "document_id": "d601",
                    "document_description": "《中小学人工智能课程标准（试行稿）》，教育部，2024年5月发布。"
                },
                {
                    "document_id": "d602",
                    "document_description": "《中小学人工智能教师培训手册》，教育部教师司，2024年9月发布，适用于2024下半年培训班。"
                },
                {
                    "document_id": "d603",
                    "document_description": "《中小学信息技术课程标准（2017版）》。"
                },
                {
                    "document_id": "d604",
                    "document_description": "《AI+教育白皮书》，某研究院2023年发布。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_documents": ["d601", "d602"]
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
                'document_id': document.document_id.__str__(),
                'document_description': document.document_description
            })
        return documents

    def collate_select_params(self, selected_categories: List[Dict] = None):
        session = self.params.session
        for category_id in selected_categories:
            db_category = session.get(Category, uuid.UUID(category_id))
            self.select_params.extend([{
                'document_id': doc.document_id.__str__(),
                'document_description': doc.document_description
            } for doc in db_category.documents])

        if len(self.select_params) == 0:
            self.select_params = self.documents

        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        DOCUMENT_USER_PROMPT[0]['content'] = str({
            'input_text': question,
            'documents': self.select_params
        })
        response_chat = llm.chat(DOCUMENT_SYSTEM_MESSAGES + DOCUMENT_FEW_SHOT_MESSAGES + DOCUMENT_USER_PROMPT, count=10)
        selected_documents = set(response_chat)

        return selected_documents
