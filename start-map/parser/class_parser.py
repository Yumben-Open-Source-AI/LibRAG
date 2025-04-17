import copy
import json
import os
import uuid
import datetime
from string import Template
from llm.base import BaseLLM
from parser.base import BaseParser

CATEGORY_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': """
            # Role: 文档标准分类生成专家

            ## Profile
            - author: LangGPT 
            - version: 1.1
            - language: 中文
            - description: 能根据文档内容与语义抽象出其所属的标准类别，优先从用户提供的分类列表中进行匹配，若无匹配或用户提供的分类列表分类描述不够准确和完善则生成新的抽象分类，并输出结构化 JSON。

            ## Skills
            1. 基于文档内容提炼核心语义，抽象归类。
            2. 优先匹配“已知分类列表”中的分类名称与分类描述。
            3. 若匹配分类存在但描述范围不够清晰明确，优化描述后输出。
            4. 若无合适类别，能自动生成合理的新类别。
            5. 输出结构规范、字段注释完整，适配分类系统集成。

            ## Rules
            1. 类别命名需具备**抽象性与通用性**，避免将具体文档当作类名。
            2. 优先匹配用户提供的 known_categories 分类列表。
            3. 若无匹配或用户提供的分类列表分类描述不够准确和完善则生成新的抽象分类。
            4. 若匹配的分类描述不足/不够清晰明确，优化其描述后输出。
            5. metadata 字段需涵盖：更新时间、关联组织。
            6. 若无明确匹配类别，返回新建分类标记 new_classification: 'true'
            7. 生成新的分类时category_description应尽可能宽泛与抽象以覆盖更广泛的内容。
            8. 优化后的category_description 应包含原先的描述内容，仅针对新的文档描述补充该分类描述。

            ## Workflows
            1. 接收输入：
                - document_name文档名称；
                - document_description 文档内容或描述（如摘要、标题）;
                - known_categories 已知分类列表（JSON数组，包含category_name,category_id,category_description 等字段）;
            2. 匹配逻辑：
                - 首先尝试使用文档描述在已知分类中匹配最相关的类别（按语义、关键词等）。
                - 使用文档描述进行分类时应优先匹配分类名称，其次是分类描述。
                - 如无匹配，再创建新的抽象分类。
                - 如匹配成功但描述不足/不够清晰明确，优化其描述后输出。
            3. 若匹配成功，返回匹配分类及 new_classification: 'false'，否则构建新分类结构。
            4. 输出结构化分类 JSON，包括所有必要字段与注释说明。

            ## Example Output
            json
            {
                "category_name": "", #分类名称
                "category_description": "<>", #这个分类的描述
                "category_id": "",
                "metadata": {
                    "关联实体": [] #此分类涉及到的实体信息
                },
                "new_classification": 'true'/'false'
            }

            Warning:
            -输出不要增加额外字段，严格按照Example Output结构输出。
            -不要解释行为。
        """
    },
    {
        'role': 'user',
        'content': """读取文档，使用中文生成或选择这段文本的分类以及分类描述，最终按照Example Output样例生成完整json格式数据``<$parse_info>```"""
    }
]


class CategoryParser(BaseParser):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.category = {}
        self.known_categories = []
        self.category_doc_dict = {}
        self.new_classification = 'true'
        self.save_path = os.path.join(self.base_path, 'category_info.json')

    def parse(self, **kwargs):
        document = kwargs.get('document')
        doc_name = document['document_name']
        doc_description = document['document_description']
        document_id = document['document_id']
        parse_params = {
            'document_name': doc_name,
            'document_description': doc_description,
            'known_categories': self.__get_known_categories(),
        }
        parse_messages = copy.deepcopy(CATEGORY_PARSE_MESSAGES)
        content = Template(parse_messages[1]['content'])
        parse_messages[1]['content'] = content.substitute(parse_info=str(parse_params))
        self.category = self.llm.chat(parse_messages)[0]
        new_classification = self.category['new_classification']
        # llm judgments this document is not an added type
        if new_classification == 'false':
            # update documents
            documents = self.category_doc_dict[self.category['category_name']]
            documents.append(document_id)
            self.category['documents'] = documents
        else:
            self.category['category_id'] = str(uuid.uuid4())
            self.category.setdefault('documents', []).append(document_id)
        self.category['metadata']['最后更新时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.new_classification = new_classification
        return self.category

    def back_fill_parent(self, parent):
        # 若生成新分类数据则回填上级领域数据
        if self.new_classification == 'true':
            self.category['parent'] = parent['domain_id']
            self.category['parent_description'] = f'此分类所属父级领域描述:<{parent["domain_description"]}>'

    def rebuild_domain(self):
        ...

    def storage_parser_data(self):
        if self.new_classification == 'true':
            del self.category['new_classification']
            with open(self.save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                data.append(self.category)

            with open(self.save_path, 'w+', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False))
        else:
            del self.category['new_classification']
            with open(self.save_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for cla in data:
                if cla['category_id'] == self.category['category_id']:
                    cla['metadata'] = self.category['metadata']
                    cla['documents'] = self.category['documents']
                    cla['category_description'] = self.category['category_description']

            with open(self.save_path, 'w+', encoding='utf-8') as f:
                f.write(json.dumps(data, ensure_ascii=False))

    def __get_known_categories(self):
        """
        Getting Known Categories to Aid in Classification Selection for Large Language Models
        """
        with open(self.save_path, 'r', encoding='utf-8') as f:
            categories = json.load(f)

        for category in categories:
            self.category_doc_dict[category['category_name']] = category['documents']
            del category['metadata']
            del category['documents']
            del category['parent']
            del category['parent_description']

        return categories
