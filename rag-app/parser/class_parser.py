import copy
import uuid
import datetime
from string import Template

from sqlmodel import select
from llm.llmchat import LlmChat
from parser.base import BaseParser
from tools.prompt_load import TextFileReader
from web_server.ai.models import Category, Domain

CATEGORY_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/parse/CATEGORY_SYSTEM.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/parse/CATEGORY_USER.txt")
    }
]


class CategoryParser(BaseParser):
    def __init__(self, llm: LlmChat, kb_id, session):
        super().__init__(llm, kb_id, session)
        self.category = None
        self.known_categories = []
        self.new_classification = 'true'

    def parse(self, **kwargs):
        document = kwargs.get('document')
        parse_type = kwargs.get('parse_type', 'default')
        ext_categories = kwargs.get('ext_categories', [])
        known_categories = self.__get_known_categories()
        if parse_type == 'rebuild':
            known_categories = self.tidy_up_known_categories(ext_categories)
        parse_params = {
            'document_name': document.document_name,
            'document_description': document.document_description,
            'known_categories': known_categories,
        }
        parse_messages = copy.deepcopy(CATEGORY_PARSE_MESSAGES)
        content = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = content.substitute(parse_info=str(parse_params))
        self.category = self.llm.chat(parse_messages)
        self.new_classification = self.category['new_classification']
        if self.new_classification == 'true':
            self.category['kb_id'] = self.kb_id
            del self.category['category_id']
            self.category = Category(**self.category)
        else:
            db_category = self.session.get(Category, uuid.UUID(self.category['category_id']))
            if parse_type == 'rebuild':
                for category in ext_categories:
                    if category.category_id.__str__() == self.category['category_id']:
                        db_category = category

            if not db_category:
                raise ValueError('new_classification judge is wrong, db category does not exist')
            db_category.meta_data = self.category['meta_data']
            db_category.category_description = self.category['category_description']
            self.category = db_category
        self.category.meta_data['最后更新时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return self.category

    def storage_parser_data(self, parent: Domain):
        if self.new_classification == 'true':
            self.category.parent_id = parent.domain_id
        self.session.add(self.category)

    def rebuild_parser_data(self, parent: Domain):
        if self.new_classification == 'true':
            self.category.parent_id = parent.domain_id

    @staticmethod
    def tidy_up_known_categories(categories):
        known_categories = []

        for category in categories:
            known_categories.append({
                'category_id': category.category_id,
                'category_name': category.category_name,
                'category_description': category.category_description,
            })

        return known_categories

    def __get_known_categories(self):
        """
        Getting Known Categories to Aid in Classification Selection for Large Language Models
        """
        statement = select(Category).where(Category.kb_id == self.kb_id)
        db_categories = self.session.exec(statement).all()
        return self.tidy_up_known_categories(db_categories)
