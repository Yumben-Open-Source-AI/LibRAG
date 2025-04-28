"""
@Project ：rag-app 
@File    ：domain_selector.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/4/28 上午10:52 
"""
import datetime
from typing import List, Dict, Sequence

from sqlmodel import select

from selector.base import BaseSelector
from web_server.ai.models import Domain

now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
DOMAIN_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': f"""
        # Role: 领域选择器（Domain Selector）

        ## Environment variable
        - 当前时间: {now}
        
        ## Profile
        - author: LangGPT 
        - version: 1.0
        - language: 中文
        - description: 一个用于智能领域判断的提示词系统，能够解析用户提出的自然语言问题，并根据问题语义判断其所属的一个或多个“知识领域”，支持多选，用于构建多层级知识体系入口。
        
        ## Skills
        - 理解自然语言中的任务目标、对象、行为、专业术语
        - 在提供的领域列表中智能匹配最相关的领域（支持模糊匹配与同义词归类）
        - 多选输出，支持一问多领域的复合任务场景
        - 返回结构化 JSON 数据格式，便于后续分类选择器接入
        
        ## Rules
        1. 输出必须为 JSON 格式，包含`selected_domains`数组；
        2. 每个领域包含 `domain_id` 和 `domain_description`；
        3. 匹配需兼顾语义上下文和关键词覆盖，不仅限于字面关键词；
        4. 允许多选返回，适用于复合型查询；
        5. 不得生成领域以外的信息，禁止虚构领域标签。
        6.`selected_domains`数组中是`domain_id`;
        
        ## Workflows
        1. 接收用户自然语言问题 input_text；
        2. 提取关键词：如行业名、业务行为、专有名词、目标实体等；
        3. 遍历提供的领域描述进行语义匹配；
        4. 返回匹配度高的 一个或多个领域（按相关性排序）；
        5. 输出为结构化 JSON：关键词 + 匹配领域信息。
        
        ## OutputFormat
        {{
            "selected_domains": ["domain_idxxx"]
        }}
        Warning: 
        -输出不要增加额外内容，严格按照Example Output结构输出。
        """
    }
]

DOMAIN_FEW_SHOT_MESSAGES = [
    {
        'role': 'user',
        'content': """{
            "input_text": "请告诉我2023年第四季度比亚迪的净利润和收入变化。",
            "domains": [
                {
                    "domain_id": "finance",
                    "domain_description": "财经金融类领域，包括企业财务分析、市场数据、会计审计、股票、基金等内容。"
                },
                {
                    "domain_id": "tech",
                    "domain_description": "科技与AI领域，包括人工智能、大数据、芯片、算法模型、互联网等技术内容。"
                },
                {
                    "domain_id": "law",
                    "domain_description": "法律政策领域，包括司法判决、法律解释、合规制度、合同协议等法律文书内容。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_domains": ["finance"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "Transformer 和 LSTM 哪种模型更适合自然语言生成？",
            "domains": [
                {
                    "domain_id": "tech",
                    "domain_description": "科技与AI领域，包括人工智能、大数据、芯片、算法模型、互联网等技术内容。"
                },
                {
                    "domain_id": "education",
                    "domain_description": "教育科研领域，包括教学内容、考试制度、教育政策、研究报告等。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_domains": ["tech"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "劳动合同纠纷中，员工是否可以单方面解除合同？",
            "domains": [
                {
                    "domain_id": "law",
                    "domain_description": "法律政策领域，包括司法判决、法律解释、合规制度、合同协议等法律文书内容。"
                },
                {
                    "domain_id": "education",
                    "domain_description": "教育科研领域，包括教学内容、考试制度、教育政策、研究报告等。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_domains": ["law"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "AI技术在中小学教育中的应用效果如何？",
            "domains": [
                {
                    "domain_id": "tech",
                    "domain_description": "科技与AI领域，包括人工智能、大数据、芯片、算法模型、互联网等技术内容。"
                },
                {
                    "domain_id": "education",
                    "domain_description": "教育科研领域，包括教学内容、考试制度、教育政策、研究报告等。"
                },
                {
                    "domain_id": "medical",
                    "domain_description": "医疗健康领域，涵盖药品研发、医疗器械、疾病诊断、健康数据等相关信息。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_domains": ["law"]
        }"""
    }
]

DOMAIN_USER_MESSAGES = [
    {
        'role': 'user'
    }
]


class DomainSelector(BaseSelector):

    def __init__(self, param):
        super().__init__(param)
        self.select_params = []

    def collate_select_params(self, params: List[Dict] = None):
        kb_id = self.params.kb_id
        statement = select(Domain).where(Domain.kb_id == kb_id)
        db_domains = self.params.session.exec(statement).all()
        for domain in db_domains:
            self.select_params.append({
                'domain_id': domain.domain_id,
                'domain_description': domain.domain_description,
            })
        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        DOMAIN_USER_MESSAGES[0]['content'] = {
            'input_text': question,
            'domains': self.select_params
        }
        response_chat = llm.chat(DOMAIN_SYSTEM_MESSAGES + DOMAIN_FEW_SHOT_MESSAGES + DOMAIN_USER_MESSAGES)
        selected_domains = set(response_chat[0]['selected_domains'])

        return selected_domains
