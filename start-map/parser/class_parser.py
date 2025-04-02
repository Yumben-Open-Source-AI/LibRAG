import json
import uuid
import datetime
from string import Template
from llm.base import BaseLLM
from parser.base import BaseParser

CATEGORY_PARSE_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': """
            # Role: 文档标准分类生成专家
            
            ## Profile
            - author: LangGPT 
            - version: 1.1
            - language: 中文
            - description: 能根据文档内容与语义抽象出其所属的标准类别，优先从用户提供的分类列表中进行匹配，若无匹配则生成新的抽象分类，并输出结构化 JSON。
            
            ## Skills
            1. 基于文档内容提炼核心语义，抽象归类。
            2. 优先匹配“已知分类列表”中的类名与描述。
            3. 若无合适类别，能自动生成合理的新类别。
            4. 输出结构规范、字段注释完整，适配分类系统集成。
            
            ## Rules
            1. 类别命名需具备**抽象性与通用性**，避免将具体文档当作类名。
            3. 优先匹配用户提供的 known_categories 分类列表。
            5. metadata 字段需涵盖：更新时间、关联组织。
            6. 若无明确匹配类别，返回新建分类标记 new_classification: 'true'
            
            ## Workflows
            1. 接收输入：
                - 文档内容或描述（如摘要、标题）
                - 已知分类列表（JSON数组，包含 class_name, class_id, description 等字段）
            2. 匹配逻辑：
                - 首先尝试在已知分类中匹配最相关的类别（按语义、关键词等）。
                - 如无匹配，再创建新的抽象分类。
            3. 若匹配成功，返回匹配分类及 new_classification: 'false'，否则构建新分类结构。
            4. 输出结构化分类 JSON，包括所有必要字段与注释说明。
            
            ## Example Output
            json
            {
                "class_name": "", #分类名称
                "description": "分类描述:<>", #这个分类的描述
                "metadata": {
                    "关联实体": [] #此分类涉及到的实体信息
                },
                "new_classification": 'true'/'false'
            }
        """
    }
]

CATEGORY_PARSE_USER_MESSAGES = [
    {
        'role': 'user',
        'content': """
            读取文档，使用中文生成这段文本的分类以及分类描述，最终按照Example Output样例生成完整json格式数据```<文档描述:<$description>>```
        """
    }
]


class CategoryParser(BaseParser):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.category = {}
        self.known_categories = []
        self.category_doc_dict = {}

    def parse(self, **kwargs):
        document = kwargs.get('document')
        description = document['description']
        document_id = document['document_id']
        self.known_categories = self.__get_known_categories()
        parse_params = {
            'document_description': description,
            'known_categories': self.known_categories,
        }
        content = Template(CATEGORY_PARSE_USER_MESSAGES[0]['content'])
        CATEGORY_PARSE_USER_MESSAGES[0]['content'] = content.substitute(description=str(parse_params))
        category_content = self.llm.chat(CATEGORY_PARSE_SYSTEM_MESSAGES + CATEGORY_PARSE_USER_MESSAGES)[0]
        category_content['category'] = str(uuid.uuid4())
        category_content['metadata']['最后更新时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        category_content.setdefault('documents', []).append(document_id)

        # llm judgments this document is not an added type
        if category_content['new_classification'] == 'false':
            documents = self.category_doc_dict[category_content['category_name']]
            documents.append(document_id)
            category_content['documents'] = documents
            self.update_storage_data()
        self.category = category_content
        return category_content

    def back_fill_parent(self, parent):
        self.category['parent'] = parent['domain_id']
        self.category['parent_description'] = parent['description']

    def __get_known_categories(self):
        """
        Getting Known Categories to Aid in Classification Selection for Large Language Models
        """
        with open(r'D:\xqm\python\project\llm\start-map\data\class_info.json', 'r', encoding='utf-8') as f:
            categories = json.load(f)

        for category in categories:
            self.category_doc_dict[category['category_name']] = category['documents']
            del category['metadata']
            del category['documents']
            del category['parent']
            del category['parent_description']

        return categories

    def storage_parser_data(self):
        del self.category['new_classification']
        with open(r'D:\xqm\python\project\llm\start-map\data\class_info.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.append(self.category)

        with open(r'D:\xqm\python\project\llm\start-map\data\class_info.json', 'w+', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def update_storage_data(self):
        del self.category['new_classification']
        with open(r'D:\xqm\python\project\llm\start-map\data\class_info.json', 'r', encoding='utf-8') as f:
            data = json.load(f)

        for cla in data:
            if cla['class_id'] == self.cla['class_id']:
                data.remove(cla)
                data.append(cla)

        with open(r'D:\xqm\python\project\llm\start-map\data\class_info.json', 'w+', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False))
