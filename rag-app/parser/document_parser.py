import copy
import os
import datetime
import json
import uuid
from string import Template
from llm.base import BaseLLM
from parser.base import BaseParser
from web_server.ai.models import Document, Category

DOCUMENT_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': """
            Role: 文档总结专家
            - version: 1.0
            - language: 中文
            - description: 你将得到User输入的一组段落文本，请详细提取且总结描述其内容，包含必须如实准确提取关键信息如关键指标及其数值数据等，最终按指定格式生成总结及描述。

            Skills
            - 生成详细及信息丰富的描述。
            - 擅长提取文本中的数值及时间信息。
            - 擅长提取文本中所有指标信息。
            - 擅长生成严格符合JSON格式的输出。
            - 擅长使用清晰的语言完整总结文本的主要内容。
            - 擅长使用陈述叙事的风格总结文本的主要内容。

            Rules
            - 描述与总结不能省略内容。
            - document_description至少20字，用清晰准确的语言陈述，不添加额外主观评价，陈述出关键指标和对象属性(如:这是xxx(对象主体)xxx(什么时间)的xxx文档，主要内容为xxx),文本中准确如实提取，避免出现遗漏情况，注重完整和清晰度。
            - 严格生成结构化不带有转义的JSON数据的总结及描述。
            - 总结和描述仅使用文本格式呈现。

            Workflows
            1. 获取用户提供的文本。
            2. 逐行解析提取文本的指标。
            3. 理解文中主要内容，结合指标和对象属性生成总结。
            4. 组合关键信息和对象属性生成描述，确保指标信息及数值数据完整。
            5. 输出最终的总结及描述，确保准确性、可读性、完整性。

            Example Output
            ```json
            {
                "document_name": "",#文档名称(注意提取时间等信息维度);
                "document_description": "<>", #文档描述；
                "meta_data": {"作者": "", "版本": ""},
                "file_path": ""#填写文档路径;
            }
            ```
            Warning:
            -document_description禁止使用```等```字眼省略指标项，但不需要数值数据。
            -输出不要增加额外字段，严格按照Example Output结构输出。
            -不要解释行为。
        """
    },
    {
        'role': 'user',
        'content': """
            读取文档，使用中文生成这段文本的描述以及总结，最终按照Example Output样例生成完整json格式数据```<文档段落描述:<<$paragraphs>>,文档路径："$path">```
        """
    }
]


class DocumentParser(BaseParser):
    def __init__(self, llm: BaseLLM, kb_id, session):
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
        self.document = self.llm.chat(parse_messages)[0]
        self.document['kb_id'] = self.kb_id
        self.document['parse_strategy'] = kwargs.get('parse_strategy')
        self.document['meta_data']['最后更新时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        self.document = Document(**self.document)
        return self.document

    def storage_parser_data(self, parent: Category):
        self.document.categories.append(parent)
        self.session.add(self.document)

    def rebuild_parser_data(self, parent: Category):
        # 解绑旧类别
        self.document.categories = []
        self.document.categories.append(parent)
        self.session.add(self.document)
