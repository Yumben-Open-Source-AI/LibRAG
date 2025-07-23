import copy
import datetime
from string import Template
from llm.llmchat import LlmChat
from parser.base import BaseParser
from tools.prompt_load import TextFileReader
from web_server.ai.models import Document, Category

DOCUMENT_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/parse/DOCUMENT_SYSTEM.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/parse/DOCUMENT_USER.txt")
    }
]


class DocumentParser(BaseParser):
    def __init__(self, llm: LlmChat, kb_id, session):
        super().__init__(llm, kb_id, session)
        self.document = None

    @staticmethod
    def tidy_up_data(paragraphs):
        for paragraph in paragraphs:
            # TODO 代码整理
            del paragraph['paragraph_name']
            del paragraph['content']
            del paragraph['keywords']
            del paragraph['position']
            del paragraph['meta_data']
        return paragraphs

    def parse(self, **kwargs):
        path = kwargs.get('path')
        paragraphs = self.tidy_up_data(kwargs.get('paragraphs'))
        parse_messages = copy.deepcopy(DOCUMENT_PARSE_MESSAGES)
        content = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = content.substitute(paragraphs=paragraphs, path=path)
        self.document = self.llm.chat(parse_messages)
        self.document['kb_id'] = self.kb_id
        self.document['parse_strategy'] = kwargs.get('parse_strategy')
        self.document['meta_data']['最后更新时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.document = Document(**self.document)
        return self.document

    def storage_parser_data(self, parent: Category):
        self.document.categories.append(parent)
        self.session.add(self.document)

    def rebuild_parser_data(self, parent: Category):
        import uuid
        if not isinstance(parent.category_id, uuid.UUID):
            try:
                parent.category_id = uuid.UUID(str(parent.category_id))
            except ValueError:
                raise ValueError(f"异常category_id: {parent.category_id}")
        # 解绑旧类别
        self.document.categories = []
        self.document.categories.append(parent)
        self.session.add(self.document)
