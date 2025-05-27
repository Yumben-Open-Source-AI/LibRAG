import copy
import datetime
import json
import uuid

from string import Template
from typing import List, Dict, Sequence
from sqlmodel import select
from selector.base import BaseSelector
from tools.prompt_load import TextFileReader
from web_server.ai.models import Document, Category

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
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        document_system_messages = copy.deepcopy(DOCUMENT_SYSTEM_MESSAGES)
        template = Template(document_system_messages[0]['content'])
        document_system_messages[0]['content'] = template.substitute(
            now=now
        )

        document_user_prompt = copy.deepcopy(DOCUMENT_USER_PROMPT)
        template = Template(document_user_prompt[0]['content'])
        document_user_prompt[0]['content'] = template.substitute(
            input_text=question,
            documents=self.select_params
        )

        response_chat = llm.chat(document_system_messages + DOCUMENT_FEW_SHOT_MESSAGES + document_user_prompt, count=10)
        selected_documents = set(response_chat)

        return selected_documents
