import datetime
import json
import uuid
from string import Template
from llm.base import BaseLLM
from parser.base import BaseParser

DOCUMENT_PARSE_SYSTEM_MESSAGES = [
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
            - 每个description至少20字，用清晰准确的语言陈述，不添加额外主观评价，陈述出关键指标和对象属性(如:这是xxx文档的xxx，主要内容为xxx),文本中准确如实提取，避免出现遗漏情况，注重完整和清晰度。
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
                "document_name": ""#文档名称,
                "description": "文档描述:<>",
                "metadata": {"作者": "", "版本": ""},
                "file_path": "", #填写文档路径
            }
            ```
            Warning:
            -description禁止使用```等```字眼省略指标项，但不需要数值数据。
        """
    }
]

DOCUMENT_PARSE_USER_MESSAGES = [
    {
        'role': 'user',
        'content': """
            读取文档，使用中文生成这段文本的描述以及总结，最终按照Example Output样例生成完整json格式数据```<文档段落描述:<<$paragraphs>>,文档路径："$path">```
        """
    }
]


class DocumentParser(BaseParser):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.document = {}

    def parse(self, **kwargs):
        paragraphs = kwargs.get('paragraphs')
        path = kwargs.get('path')
        paragraph_ids = []
        for paragraph in paragraphs:
            del paragraph['paragraph_name']
            del paragraph['content']
            del paragraph['keywords']
            del paragraph['position']
            del paragraph['metadata']
            paragraph_ids.append(paragraph['paragraph_id'])
        content = Template(DOCUMENT_PARSE_USER_MESSAGES[0]['content'])
        DOCUMENT_PARSE_USER_MESSAGES[0]['content'] = content.substitute(paragraphs=paragraphs, path=path)
        document_content = self.llm.chat(DOCUMENT_PARSE_SYSTEM_MESSAGES + DOCUMENT_PARSE_USER_MESSAGES)[0]
        document_content['document_id'] = str(uuid.uuid4())
        document_content['metadata']['最后更新时间'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        document_content['paragraphs'] = paragraph_ids
        self.document = document_content
        return document_content

    def storage_parser_data(self):
        with open(r'D:\xqm\python\project\llm\start-map\data\document_info.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.append(self.document)

        with open(r'D:\xqm\python\project\llm\start-map\data\document_info.json', 'w+', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def back_fill_parent(self, parent):
        self.document.setdefault('parent', []).append(parent['class_id'])
        self.document['parent_description'] = parent['description']
