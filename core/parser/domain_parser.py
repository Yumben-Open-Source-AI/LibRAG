import copy
import uuid
import datetime
from string import Template
from sqlmodel import select
from llm.llmchat import LlmChat
from parser.base import BaseParser
from tools.prompt_load import TextFileReader
from web_server.ai.models import Domain

DOMAIN_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/parse/DOMAIN_SYSTEM.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/parse/DOMAIN_USER.txt")
    }
]


class DomainParser(BaseParser):
    def __init__(self, llm: LlmChat, kb_id, session):
        super().__init__(llm, kb_id, session)
        self.domain = None
        self.known_domains = []
        self.new_domain = 'true'

    def parse(self, **kwargs):
        category = kwargs.get('category')
        parse_type = kwargs.get('parse_type', 'default')
        ext_domains = kwargs.get('ext_domains', [])
        known_domains = self.__get_known_domains()
        if parse_type == 'rebuild':
            known_domains = self.tidy_up_known_domains(ext_domains)
        parse_params = {
            'category_name': category.category_name,
            'category_description': category.category_description,
            'known_domains': known_domains
        }
        parse_messages = copy.deepcopy(DOMAIN_PARSE_MESSAGES)
        content = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = content.substitute(cla=str(parse_params))
        self.domain = self.llm.chat(parse_messages)
        self.new_domain = self.domain['new_domain']
        if self.new_domain == 'true':
            self.domain['kb_id'] = self.kb_id
            del self.domain['domain_id']
            self.domain = Domain(**self.domain)
        else:
            db_domain = self.session.get(Domain, uuid.UUID(self.domain['domain_id']))
            if parse_type == 'rebuild':
                for domain in ext_domains:
                    if domain.domain_id.__str__() == self.domain['domain_id']:
                        db_domain = domain

            if not db_domain:
                raise ValueError('new_domain judge is wrong, db domain does not exist')
            db_domain.domain_description = self.domain['domain_description']
            self.domain = db_domain
        self.domain.meta_data['最后更新时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return self.domain

    def storage_parser_data(self, parent):
        self.session.add(self.domain)

    @staticmethod
    def tidy_up_known_domains(domains):
        known_domains = []
        for domain in domains:
            known_domains.append({
                'domain_id': domain.domain_id,
                'domain_name': domain.domain_name,
                'domain_description': domain.domain_description
            })

        return known_domains

    def __get_known_domains(self):
        """
        Getting Known domains to Aid in Classification Selection for Large Language Models
        """
        statement = select(Domain).where(Domain.kb_id == self.kb_id)
        db_domains = self.session.exec(statement).all()
        return self.tidy_up_known_domains(db_domains)
