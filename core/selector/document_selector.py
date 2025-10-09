import copy
import datetime
import json
import os
import uuid

from string import Template
from typing import List, Dict, Sequence
from sqlmodel import select
from selector.base import BaseSelector
from tools.prompt_load import TextFileReader
from web_server.ai.models import Document, Category
from tools.log_tools import selector_logger as logger

# system action
DOCUMENT_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/selector/DOCUMENT_SYSTEM.txt")
    }
]

# few_shot example input output
DOCUMENT_FEW_SHOT_MESSAGES = json.loads(TextFileReader().read_file("prompts/selector/DOCUMENT_FEW_SHOT.txt"))

# user input
DOCUMENT_USER_PROMPT = [
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/selector/DOCUMENT_USER.txt")
    }
]


class DocumentSelector(BaseSelector):
    PARSER_DOCUMENT_GROUP_COUNT = int(os.getenv('PARSER_DOCUMENT_GROUP_COUNT', 10))

    def __init__(self, params):
        super().__init__(params)
        self.all_documents = {}
        self.id_mapping = {}  # 数字ID到原始ID的映射
        self.reverse_mapping = {}  # 原始ID到数字ID的映射
        self.documents = self.get_layer_data()
        self.select_params = []

    def get_layer_data(self) -> Sequence[Dict]:
        kb_id = self.params.kb_id
        session = self.params.session
        statement = select(Document).where(Document.kb_id == kb_id)
        db_documents = session.exec(statement).all()
        documents = []
        # 使用数字ID
        for idx, document in enumerate(db_documents, start=1):
            document_id = document.document_id.__str__()
            num_id = str(idx)

            self.id_mapping[num_id] = document_id
            self.reverse_mapping[document_id] = num_id

            documents.append({
                'document_id': num_id,  # 使用数字ID
                'document_description': document.document_description
            })
            self.all_documents[document_id] = document
        return documents

    def collate_select_params(self, selected_categories: List[Dict] = None):
        session = self.params.session
        for category_id in selected_categories:
            db_category = session.get(Category, uuid.UUID(category_id))
            # 使用数字ID
            for idx, doc in enumerate(db_category.documents, start=len(self.id_mapping) + 1):
                document_id = doc.document_id.__str__()
                num_id = str(idx)

                if document_id not in self.reverse_mapping:  # 避免重复添加
                    self.id_mapping[num_id] = document_id
                    self.reverse_mapping[document_id] = num_id

                self.select_params.append({
                    'document_id': self.reverse_mapping[document_id],  # 使用数字ID
                    'document_description': doc.document_description
                })

        if len(self.select_params) == 0:
            self.select_params = self.documents

        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        document_system_messages = copy.deepcopy(DOCUMENT_SYSTEM_MESSAGES)
        template = Template(document_system_messages[0]['content'])
        document_system_messages[0]['content'] = template.substitute(
            now=now
        )
        logger.debug(f'文档选择器 system prompt:{document_system_messages}')

        document_user_prompt = copy.deepcopy(DOCUMENT_USER_PROMPT)
        template = Template(document_user_prompt[0]['content'])
        document_user_prompt[0]['content'] = template.substitute(
            input_text=question,
            documents=self.select_params
        )
        logger.debug(f'文档选择器 user prompt:{document_user_prompt}')
        response_chat = llm.chat(document_system_messages + DOCUMENT_FEW_SHOT_MESSAGES + document_user_prompt,
                                 count=self.PARSER_DOCUMENT_GROUP_COUNT)
        # 将数字ID转换回原始ID
        selected_num_documents = set(response_chat)
        selected_documents = {self.id_mapping[num_id] for num_id in selected_num_documents if num_id in self.id_mapping}

        documents = []
        for doc in selected_documents.copy():
            if doc in self.all_documents:
                documents.append({
                    'document_id': doc,
                    'document_name': self.all_documents[doc].document_name,
                    'parent_name': [category.category_name for category in self.all_documents[doc].categories]
                })
            else:
                selected_documents.remove(doc)
        return selected_documents, documents
