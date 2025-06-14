import copy
import datetime
import json
import uuid

from string import Template
from typing import List, Dict
from sqlmodel import select
from selector.base import BaseSelector
from tools.prompt_load import TextFileReader
from web_server.ai.models import Paragraph, Document
from tools.log_tools import selector_logger as logger

# system action
PARAGRAPH_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/selector/PARAGRAPH_SYSTEM.txt")
    }
]

# few shot example input output
PARAGRAPH_FEW_SHOT_MESSAGES = json.loads(TextFileReader().read_file("prompts/selector/PARAGRAPH_FEW_SHOT.txt"))

PARAGRAPH_USER_MESSAGES = [
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/selector/PARAGRAPH_USER.txt")
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
                'paragraph_id': paragraph.paragraph_id.__str__(),
                'paragraph_description': f'{paragraph.parent_description};{paragraph.parent_description}'
            })
        return paragraphs

    def collate_select_params(self, selected_documents: List[Dict] = None):
        session = self.params.session
        for doc_id in selected_documents:
            db_doc = session.get(Document, uuid.UUID(doc_id))
            self.select_params.extend([{
                'paragraph_id': paragraph.paragraph_id.__str__(),
                'paragraph_description': f'{paragraph.summary};{paragraph.parent_description}'
            } for paragraph in db_doc.paragraphs])

        return self

    def start_select(self):
        question = self.params.question
        llm = self.params.llm
        now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        paragraph_system_messages = copy.deepcopy(PARAGRAPH_SYSTEM_MESSAGES)
        template = Template(paragraph_system_messages[0]['content'])
        paragraph_system_messages[0]['content'] = template.substitute(
            now=now
        )
        logger.debug(f'段落选择器 system prompt:{paragraph_system_messages}')

        paragraph_user_messages = copy.deepcopy(PARAGRAPH_USER_MESSAGES)
        template = Template(paragraph_user_messages[0]['content'])
        paragraph_user_messages[0]['content'] = template.substitute(
            input_text=question,
            paragraphs=self.select_params
        )
        logger.debug(f'段落选择器 user prompt:{paragraph_user_messages}')
        response_chat = llm.chat(paragraph_system_messages + PARAGRAPH_FEW_SHOT_MESSAGES + paragraph_user_messages, count=10)
        self.selected_paragraphs = set(response_chat['selected_paragraphs'])

        return self

    def collate_select_result(self) -> List:
        if len(self.selected_paragraphs) == 0:
            return []

        session = self.params.session
        result = []
        for paragraph_id in self.selected_paragraphs:
            result.append(session.get(Paragraph, uuid.UUID(paragraph_id)).dict())

        return result
