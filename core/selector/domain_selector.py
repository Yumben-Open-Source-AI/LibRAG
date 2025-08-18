"""
@Project ：LibRAG
@File    ：domain_selector.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/4/28 上午10:52 
"""
import copy
import datetime
import json

from string import Template
from typing import List, Dict
from sqlmodel import select
from selector.base import BaseSelector
from tools.prompt_load import TextFileReader
from web_server.ai.models import Domain
from tools.log_tools import selector_logger as logger

DOMAIN_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/selector/DOMAIN_SYSTEM.txt")
    }
]

DOMAIN_FEW_SHOT_MESSAGES = json.loads(TextFileReader().read_file("prompts/selector/DOMAIN_FEW_SHOT.txt"))

DOMAIN_USER_MESSAGES = [
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/selector/DOMAIN_USER.txt")
    }
]


class DomainSelector(BaseSelector):

    def __init__(self, param):
        super().__init__(param)
        self.domain_names = {}
        self.select_params = []
        # 添加数字ID映射
        self.id_mapping = {}  # 存储数字ID到原始ID的映射
        self.reverse_mapping = {}  # 存储原始ID到数字ID的映射

    def collate_select_params(self, params: List[Dict] = None):
        kb_id = self.params.kb_id
        statement = select(Domain).where(Domain.kb_id == kb_id)
        db_domains = self.params.session.exec(statement).all()

        for idx, domain in enumerate(db_domains, start=1):
            domain_id = domain.domain_id.__str__()
            num_id = str(idx)  # 使用数字ID

            self.id_mapping[num_id] = domain_id
            self.reverse_mapping[domain_id] = num_id

            self.select_params.append({
                'domain_id': num_id,  # 使用数字ID
                'domain_description': domain.domain_description,
            })
            self.domain_names[domain_id] = domain.domain_name
        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        domain_system_messages = copy.deepcopy(DOMAIN_SYSTEM_MESSAGES)
        template = Template(domain_system_messages[0]['content'])
        domain_system_messages[0]['content'] = template.substitute(
            now=now
        )
        logger.debug(f'领域选择器 system prompt:{domain_system_messages}')

        domain_user_messages = copy.deepcopy(DOMAIN_USER_MESSAGES)
        template = Template(domain_user_messages[0]['content'])
        domain_user_messages[0]['content'] = template.substitute(
            input_text=question,
            domains=self.select_params
        )
        logger.debug(f'领域选择器 user prompt:{domain_user_messages}')
        response_chat = llm.chat(domain_system_messages + DOMAIN_FEW_SHOT_MESSAGES + domain_user_messages)
        # 将数字ID转换回原始ID
        selected_num_domains = set(response_chat['selected_domains'])
        selected_domains = {self.id_mapping[num_id] for num_id in selected_num_domains}

        domains = [{'domain_id': domain, 'domain_name': self.domain_names[domain]} for domain in selected_domains]
        return selected_domains, domains
