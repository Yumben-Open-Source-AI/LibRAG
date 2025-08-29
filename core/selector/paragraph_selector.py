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
        self.id_mapping = {}  # 数字ID到原始ID的映射
        self.reverse_mapping = {}  # 原始ID到数字ID的映射
        self.categories = self.get_layer_data()
        self.select_params = []
        self.selected_paragraphs = None

    def get_layer_data(self):
        kb_id = self.params.kb_id
        session = self.params.session
        statement = select(Paragraph).where(Paragraph.kb_id == kb_id)
        db_paragraphs = session.exec(statement).all()
        paragraphs = []
        # 使用数字ID
        for idx, paragraph in enumerate(db_paragraphs, start=1):
            paragraph_id = paragraph.paragraph_id.__str__()
            num_id = str(idx)

            self.id_mapping[num_id] = paragraph_id
            self.reverse_mapping[paragraph_id] = num_id

            paragraphs.append({
                'paragraph_id': num_id,  # 使用数字ID
                'paragraph_description': f'{paragraph.parent_description};{paragraph.parent_description}'
            })
        return paragraphs

    def collate_select_params(self, selected_documents: List[Dict] = None):
        session = self.params.session
        for doc_id in selected_documents:
            db_doc = session.get(Document, uuid.UUID(doc_id))
            # 使用数字ID
            for idx, paragraph in enumerate(db_doc.paragraphs, start=len(self.id_mapping) + 1):
                paragraph_id = paragraph.paragraph_id.__str__()
                num_id = str(idx)

                if paragraph_id not in self.reverse_mapping:  # 避免重复添加
                    self.id_mapping[num_id] = paragraph_id
                    self.reverse_mapping[paragraph_id] = num_id

                self.select_params.append({
                    'paragraph_id': self.reverse_mapping[paragraph_id],  # 使用数字ID
                    'paragraph_description': f'{paragraph.summary};{paragraph.parent_description}'
                })

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
        response_chat = llm.chat(paragraph_system_messages + PARAGRAPH_FEW_SHOT_MESSAGES + paragraph_user_messages, count=40)
        # 将数字ID转换回原始ID
        selected_num_paragraphs = set(response_chat)
        self.selected_paragraphs = {self.id_mapping[num_id] for num_id in selected_num_paragraphs if
                                    num_id in self.id_mapping}

        return self

    def collate_select_result(self) -> List:
        documents = {}
        if len(self.selected_paragraphs) == 0:
            return []

        session = self.params.session
        result = []
        for paragraph_id in self.selected_paragraphs:
            try:
                paragraph_uuid = uuid.UUID(paragraph_id)
                target_paragraph = session.get(Paragraph, paragraph_uuid).dict()
                document_id = target_paragraph['parent_id']
                if document_id not in documents:
                    # 新增文档名称
                    document = session.get(Document, document_id).dict()
                    documents[document_id] = document['file_path'].split('/')[-1]
                target_paragraph['document_name'] = documents[document_id]

                if not self.params.has_source_text:
                    del target_paragraph['source_text']
                result.append(target_paragraph)
            except Exception as e:
                logger.error(str(e) + '段落选择器异常输出选择', exc_info=True)
                pass

        return result
