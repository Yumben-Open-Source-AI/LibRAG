"""
@Project ：LibRAG
@File    ：class_selector.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/4/28 上午10:40 
"""
import copy
import datetime
import json
import uuid

from string import Template
from typing import List, Dict, Sequence
from sqlmodel import select
from selector.base import BaseSelector
from tools.log_tools import selector_logger as logger
from tools.prompt_load import TextFileReader
from web_server.ai.models import Domain, Category

CATEGORY_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/selector/CATEGORY_SYSTEM.txt")
    }
]

CATEGORY_FEW_SHOT_MESSAGES = json.loads(TextFileReader().read_file("prompts/selector/CATEGORY_FEW_SHOT.txt"))

CATEGORY_USER_MESSAGES = [
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/selector/CATEGORY_USER.txt")
    }
]


class CategorySelector(BaseSelector):

    def __init__(self, params):
        super().__init__(params)
        self.category_names = {}
        self.id_mapping = {}  # 数字ID到原始ID的映射
        self.reverse_mapping = {}  # 原始ID到数字ID的映射
        self.categories = self.get_layer_data()
        self.select_params = []

    def get_layer_data(self) -> Sequence[Dict]:
        kb_id = self.params.kb_id
        session = self.params.session
        statement = select(Category).where(Category.kb_id == kb_id)
        db_categories = session.exec(statement).all()
        categories = []

        # 使用数字ID
        for idx, category in enumerate(db_categories, start=1):
            category_id = category.category_id.__str__()
            num_id = str(idx)

            self.id_mapping[num_id] = category_id
            self.reverse_mapping[category_id] = num_id

            categories.append({
                'category_id': num_id,  # 使用数字ID
                'category_description': category.category_description
            })
            self.category_names[category_id] = category.category_name

        return categories

    def collate_select_params(self, selected_domains: List[Dict] = None):
        session = self.params.session
        for domain_id in selected_domains:
            db_domain = session.get(Domain, uuid.UUID(domain_id))
            # 使用数字ID
            for idx, category in enumerate(db_domain.sub_categories, start=len(self.id_mapping) + 1):
                category_id = category.category_id.__str__()
                num_id = str(idx)

                if category_id not in self.reverse_mapping:  # 避免重复添加
                    self.id_mapping[num_id] = category_id
                    self.reverse_mapping[category_id] = num_id

                self.select_params.append({
                    'category_id': self.reverse_mapping[category_id],  # 使用数字ID
                    'category_description': category.category_description
                })

        if len(self.select_params) == 0:
            self.select_params = self.categories

        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        category_system_messages = copy.deepcopy(CATEGORY_SYSTEM_MESSAGES)
        template = Template(category_system_messages[0]['content'])
        category_system_messages[0]['content'] = template.substitute(
            now=now
        )
        logger.debug(f'类别选择器 system prompt:{category_system_messages}')

        category_user_messages = copy.deepcopy(CATEGORY_USER_MESSAGES)
        template = Template(category_user_messages[0]['content'])
        category_user_messages[0]['content'] = template.substitute(
            input_text=question,
            categories=self.select_params
        )
        logger.debug(f'类别选择器 user prompt:{category_user_messages}')
        response_chat = llm.chat(category_system_messages + CATEGORY_FEW_SHOT_MESSAGES + category_user_messages)
        # 将数字ID转换回原始ID
        selected_num_categories = set(response_chat['selected_categories'])
        selected_categories = {self.id_mapping[num_id] for num_id in selected_num_categories}

        categories = [{'category_id': category, 'category_name': self.category_names[category]}
                      for category in selected_categories]
        return selected_categories, categories
