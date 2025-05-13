"""
@Project ：rag-app 
@File    ：class_selector.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/4/28 上午10:40 
"""
import datetime
import uuid
from typing import List, Dict, Sequence

from sqlmodel import select

from selector.base import BaseSelector
from web_server.ai.models import Domain, Category

now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
CATEGORY_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': f"""
        # Role: 分类选择器（Category Selector）
        
        ## Environment variable
        - 当前时间: {now}
        
        ## Profile
        - author: LangGPT 
        - version: 1.0
        - language: 中文
        - description: 一个智能分类判断引擎，能够基于用户提出的自然语言问题，分析其意图并匹配最相关的预设分类标签，支持多分类输出，用于文档系统中的分类层选择。
        
        ## Skills
        - 从自然语言问题中提取语义意图（如内容对象、行为、时间等）
        - 在提供的分类描述列表中进行语义匹配与排序
        - 返回结构化 JSON 格式结果，支持多分类匹配
        
        ## Rules
        1. 响应格式为 JSON，包含 `selected_categories` 数组；
        2. 每个分类有 `category_id` 与 `category_description`，系统应从描述中识别其涵盖范围；
        3. 可多选分类，但不得返回与用户问题不相关的分类；
        4. 匹配以语义为主，不拘泥词面，支持泛义/同义词识别；
        5. 用户查询中若含复合意图，应合理拆分并匹配对应多个分类。
        6. `selected_categories` 数组中是`category_id`;
        
        ## Workflows
        1. 输入包括 `input_text`（用户问题）与 `categories`（分类描述列表）；
        2. 解析 input_text 并提取关键词（如对象、动词、领域关键词等）；
        3. 匹配最相关的一个或多个分类；
        4. 输出关键词与命中的分类结构。
        
        ## OutputFormat
        {{
            "selected_categories": ["category_idxxx"]
        }}
        Warning: 
        -输出不要增加额外内容，严格按照Example Output结构输出。
        """
    }
]

CATEGORY_FEW_SHOT_MESSAGES = [
    {
        'role': 'user',
        'content': """{
            "input_text": "请分析比亚迪2023年第四季度的净利润和总资产变动情况。",
            "categories": [
                {
                    "category_id": "cat01",
                    "category_description": "盈利能力分析：包含净利润、ROE、利润率等指标。"
                },
                {
                    "category_id": "cat02",
                    "category_description": "资产结构分析：包括总资产、流动/非流动资产构成与变化等。"
                },
                {
                    "category_id": "cat03",
                    "category_description": "股东结构：涉及控股股东变动、前十大股东情况等。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_categories": ["cat01","cat02"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "请帮我找出2023年新能源汽车相关的补贴政策调整内容。",
            "categories": [
                {
                    "category_id": "cat10",
                    "category_description": "财政补贴政策：涵盖补贴标准、适用范围、拨付流程等。"
                },
                {
                    "category_id": "cat11",
                    "category_description": "税收优惠政策：如购置税减免、增值税返还等内容。"
                },
                {
                    "category_id": "cat12",
                    "category_description": "市场准入政策：涉及产品认证、销售许可等要求。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_categories": ["cat10"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
            "input_text": "这起案件中，被告提出了哪些抗辩理由？法院是否采纳了这些抗辩？",
            "categories": [
                {
                    "category_id": "cat21",
                    "category_description": "被告抗辩：涉及抗辩类型、抗辩证据及其逻辑。"
                },
                {
                    "category_id": "cat22",
                    "category_description": "法院裁判理由：法院对事实、证据和法律适用的解释。"
                },
                {
                    "category_id": "cat23",
                    "category_description": "案件背景事实：案情描述、基本信息和当事人关系。"
                }
            ]
        }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_categories": ["cat21","cat22"]
        }"""
    },
    {
        'role': 'user',
        'content': """{
                "input_text": "本研究主要探讨深度神经网络在语音识别任务中的收敛速度与泛化能力。",
                "categories": [
                    {
                        "category_id": "cat30",
                        "category_description": "模型性能评估：包括收敛速度、泛化能力、准确率等分析。"
                    },
                    {
                        "category_id": "cat31",
                        "category_description": "网络架构设计：涉及DNN、CNN、Transformer等结构优化。"
                    },
                    {
                        "category_id": "cat32",
                        "category_description": "数据集与实验设置：样本数量、训练验证划分、超参数等。"
                    }
                ]
            }"""
    },
    {
        'role': 'assistant',
        'content': """{
            "selected_categories": ["cat30"]
        }"""
    }
]

CATEGORY_USER_MESSAGES = [
    {
        'role': 'user'
    }
]


class CategorySelector(BaseSelector):

    def __init__(self, params):
        super().__init__(params)
        self.categories = self.get_layer_data()
        self.select_params = []

    def get_layer_data(self) -> Sequence[Dict]:
        kb_id = self.params.kb_id
        session = self.params.session
        statement = select(Category).where(Category.kb_id == kb_id)
        db_categories = session.exec(statement).all()
        categories = []
        for category in db_categories:
            categories.append({
                'category_id': category.category_id.__str__(),
                'category_description': category.category_description
            })
        return categories

    def collate_select_params(self, selected_domains: List[Dict] = None):
        session = self.params.session
        for domain_id in selected_domains:
            db_domain = session.get(Domain, uuid.UUID(domain_id))
            self.select_params.extend([{
                'category_id': category.category_id.__str__(),
                'category_description': category.category_description
            } for category in db_domain.sub_categories])

        if len(self.select_params) == 0:
            self.select_params = self.categories

        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        CATEGORY_USER_MESSAGES[0]['content'] = str({
            'input_text': question,
            'categories': self.select_params
        })
        response_chat = llm.chat(CATEGORY_SYSTEM_MESSAGES + CATEGORY_FEW_SHOT_MESSAGES + CATEGORY_USER_MESSAGES)
        selected_categories = set(response_chat[0]['selected_categories'])

        return selected_categories
