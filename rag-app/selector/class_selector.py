"""
@Project ：rag-app 
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
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        category_system_messages = copy.deepcopy(CATEGORY_SYSTEM_MESSAGES)
        template = Template(category_system_messages[0]['content'])
        category_system_messages[0]['content'] = template.substitute(
            now=now
        )

        category_user_messages = copy.deepcopy(CATEGORY_USER_MESSAGES)
        template = Template(category_user_messages[0]['content'])
        category_user_messages[0]['content'] = template.substitute(
            input_text=question,
            categories=self.select_params
        )

        response_chat = llm.chat(category_system_messages + CATEGORY_FEW_SHOT_MESSAGES + category_user_messages)
        selected_categories = set(response_chat['selected_categories'])

        return selected_categories
