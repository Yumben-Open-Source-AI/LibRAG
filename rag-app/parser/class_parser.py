import copy
import json
import os
import uuid
import datetime
from string import Template

from sqlmodel import select

from llm.base import BaseLLM
from parser.base import BaseParser
from web_server.ai.models import Category, Domain

CATEGORY_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': """
            # Role: 文档标准分类生成专家

            ## Profile
            - author: LangGPT 
            - version: 1.3
            - language: 中文
            - description: 能基于文档语义抽象归纳出其所属信息类别，优先从用户提供的分类体系中进行语义匹配，如无合适匹配则智能生成更具抽象性的新类别，并输出结构化分类信息。

            ## Skills
            1. 抽象理解文档内容并归纳核心语义。
            2. 匹配语义层级更优的现有分类或生成新类别。
            3. 优化不清晰的分类描述，提高语义边界的清晰度。
            4. 生成分类名称需具备概括力，避免内容堆砌或专用化命名。
            5. 输出格式标准，字段清晰，便于系统集成与溯源。

            ## Rules
            1. 分类应体现**语义层次与信息抽象结构**，避免使用具体内容或组织名作为类名。
            2. 已知分类（known_categories）优先匹配“语义上最贴合”的类别，而非关键词匹配。
            3. 若已知分类中无覆盖该语义领域的条目，生成具有更高抽象概括力的新类别，并设定 `new_classification: 'true'`。
            4. 若匹配的分类描述存在模糊或内容不充分的情况，进行语义增强与边界清晰化补充后再输出。
            5. 优化后的category_description 应包含原先的描述内容，仅针对新的文档描述补充该分类描述。
            6. 输出结构中需包括分类基本信息与语义注释（meta_data），支持内容映射、更新时间和归属逻辑。
            7. 对文档的归类应基于其信息作用/属性与结构特征，如强调技术对接、结构规范、通信协议等，则应优先归入具备系统性、结构性或平台接入特征的抽象语义类，而非归于以事务性或项目执行为核心的范畴。

            ## Workflows
            1. 接收输入：
                - `document_name`: 文档标题或名称
                - `document_description`: 文档摘要或结构内容描述
                - `known_categories`: JSON数组，包含可供归类的类别（含名称、ID、描述）
            2. 匹配方式：
                - 从分类名称和分类描述中双向比对语义抽象层级，优先匹配“本质属性”一致的分类。
                - 若document_description的用途与目的与category_name不符应生成新分类。
                - 若无匹配分类，生成新的抽象类别，并命名为能覆盖该类文档集合的类别名。
                - 若匹配成功但描述不具备泛化能力，则优化扩展其适用语义。
            3. 输出内容：
                - 使用标准结构输出 `category_name`, `category_id`, `category_description`, `meta_data`, `new_classification`
            
            ## Example Output
            json
            {
                "category_id": "",
                "category_name": "", # 抽象的语义类名
                "category_description": "", # 分类语义定义与内容适用范围
                "meta_data": {
                    "关联实体": [] # 可为空，或包含系统、部门、模块名称等
                },
                "new_classification": 'true'/'false'
            }

            Warning:
            -输出字段必须与示例结构一致，不得额外添加或省略。
            -无需解释输出内容或行为逻辑。
        """
    },
    {
        'role': 'user',
        'content': """读取文档，使用中文生成或选择这段文本的分类以及分类描述，最终按照Example Output样例生成完整json格式数据``<$parse_info>```"""
    }
]


class CategoryParser(BaseParser):
    def __init__(self, llm: BaseLLM, kb_id, session):
        super().__init__(llm, kb_id, session)
        self.category = None
        self.known_categories = []
        self.new_classification = 'true'

    def parse(self, **kwargs):
        document = kwargs.get('document')
        ext_categories = kwargs.get('ext_categories', [])
        known_categories = self.__get_known_categories()
        if ext_categories:
            known_categories = self.tidy_up_known_categories(ext_categories)
        parse_params = {
            'document_name': document.document_name,
            'document_description': document.document_description,
            'known_categories': known_categories,
        }
        parse_messages = copy.deepcopy(CATEGORY_PARSE_MESSAGES)
        content = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = content.substitute(parse_info=str(parse_params))
        self.category = self.llm.chat(parse_messages)[0]
        self.new_classification = self.category['new_classification']
        if self.new_classification == 'true':
            self.category['kb_id'] = self.kb_id
            del self.category['category_id']
            self.category = Category(**self.category)
        else:
            db_category = self.session.get(Category, uuid.UUID(self.category['category_id']))
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
