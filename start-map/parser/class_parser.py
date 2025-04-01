import uuid
import datetime
from string import Template
from llm.base import BaseLLM
from parser.base import BaseParser

CLASS_PARSE_SYSTEM_MESSAGES = [
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
            6. 若无明确匹配类别，返回新建分类标记 new_classification: true
            
            ## Workflows
            1. 接收输入：
                - 文档内容或描述（如摘要、标题）
                - 已知分类列表（JSON数组，包含 class_name, class_id, description 等字段）
            2. 匹配逻辑：
                - 首先尝试在已知分类中匹配最相关的类别（按语义、关键词等）。
                - 如无匹配，再创建新的抽象分类。
            3. 若匹配成功，返回匹配分类及 new_classification: false，否则构建新分类结构。
            4. 输出结构化分类 JSON，包括所有必要字段与注释说明。
            
            ## Example Output
            json
            {
                "class_name": "", #分类名称
                "description": "分类描述:<>", #这个分类的描述
                "metadata": {
                    "最后更新时间": "{{#1742954273623.text#}}",
                    "关联实体": [] #此分类涉及到的实体信息
                },
                "new_classification":true/false
            }
        """
    }
]

CLASS_PARSE_USER_MESSAGES = [
    {
        'role': 'user',
        'content': """
            读取文档，使用中文生成这段文本的分类以及分类描述，最终按照Example Output样例生成完整json格式数据```<文档描述:<$description>>```
        """
    }
]


class ClassParser(BaseParser):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.class_obj = {}

    def parse(self, **kwargs):
        documents = kwargs.get('documents')
        description = documents['description']
        content = Template(CLASS_PARSE_USER_MESSAGES[0]['content'])
        CLASS_PARSE_USER_MESSAGES[0]['content'] = content.substitute(description=description)
        class_content = self.llm.chat(CLASS_PARSE_SYSTEM_MESSAGES + CLASS_PARSE_USER_MESSAGES)[0]
        self.class_obj = class_content
        return class_content
