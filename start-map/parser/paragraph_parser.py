import copy
import json
import uuid
import fitz
import datetime
from llm.base import BaseLLM
from parser.base import BaseParser
from concurrent.futures import ThreadPoolExecutor, as_completed

PARAGRAPH_PARSE_SYSTEM_MESSAGES = [
    {
        'role': 'system',
        'content': """
            Role: 文档总结专家
            - version: 1.0
            - language: 中文
            - description: 你将得到User输入的一段文本，请详细提取且总结描述其内容，包含必须如实准确提取关键信息如所有指标及其数值数据等，最终按指定格式生成总结及描述。

            Skills
            - 擅长使用面向对象的视角抽取文本内容的对象属性(属性选项:当前页,内容所属类型[摘要/引言/目录/首页/正文/公告/...]。
            - 生成详细及信息丰富的描述。
            - 擅长提取文本中的数值数据。
            - 擅长提取文本中所有指标信息。
            - 擅长生成严格符合JSON格式的输出。
            - 擅长使用清晰的语言完整总结文本的主要内容。
            - 擅长使用陈述叙事的风格总结文本的主要内容。

            Rules
            - 描述与总结不能省略内容。
            - 每个summary至少20字，用清晰准确的语言陈述，不添加额外主观评价，陈述出所有指标和对象属性(如:这是xxx第xxx页的[摘要/引言/目录/首页/正文/公告/...]内容，内容包含以下指标内容xxx)。
            - 每个content至少50个字，且必须涵盖文本中所有出现的指标信息及数值数据，文本中准确如实提取，避免出现遗漏情况，注重完整和清晰度。
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
                "paragraph_name": "",#填写章节或段落名称,
                "summary": "段落描述:<>",
                "content": "",
                "keywords": [],#关键词
                "position":""，#段落在文中的位置
            }
            ```
            Warning:
            -summary必须列出所有指标字段，禁止使用```等```字眼省略指标项，但不需要数值数据。
            -content必须列出所有指标及数值数据，不能省略。  
        """
    }
]

PARAGRAPH_PARSE_USER_MESSAGES = [
    {
        'role': 'user',
        'content': """
            读取文档，使用中文生成这段文本的描述以及总结，最终按照Example Output样例生成完整json格式数据
        """
    }
]


class ParagraphParser(BaseParser):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.paragraphs = []

    def parse(self, **kwargs):
        file_path = kwargs.get('path')
        doc = fitz.open(file_path)
        all_paragraphs = []
        page_count = 1
        with ThreadPoolExecutor(max_workers=25) as executor:
            tasks_page = []
            for page in doc:
                doc_markdown = page.get_text()
                user_message = copy.deepcopy(PARAGRAPH_PARSE_USER_MESSAGES)
                user_message[0]['content'] += f"```<当前页:{page_count}, 段落原文:{doc_markdown}>```"
                task = executor.submit(self.llm.chat, PARAGRAPH_PARSE_SYSTEM_MESSAGES + user_message)
                tasks_page.append(task)
                page_count += 1

            for task in as_completed(tasks_page):
                paragraph_content = task.result()[0]
                paragraph_content['paragraph_id'] = str(uuid.uuid4())
                paragraph_content['metadata'] = {'最后更新时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                all_paragraphs.append(paragraph_content)

        # deepcopy
        self.paragraphs = copy.deepcopy(all_paragraphs)
        return all_paragraphs

    def storage_parser_data(self):
        with open(r'F:\Python\Project\LLM\llm_star_map\start-map\data\paragraph_info.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.extend(self.paragraphs)

        with open(r'F:\Python\Project\LLM\llm_star_map\start-map\data\paragraph_info.json', 'w+', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def back_fill_parent(self, parent):
        parent_id = parent['document_id']
        parent_description = parent['description']
        for paragraph in self.paragraphs:
            paragraph['parent'] = parent_id
            paragraph['parent_description'] = f'此段落来源描述:<{parent_description}>'
