import copy
import json
import os
import re
import tempfile
import uuid
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from string import Template
from llm.base import BaseLLM
from parser.agentic_chunking import ChunkOrganizer
from parser.base import BaseParser
from markdownify import MarkdownConverter

from pathlib import Path

from parser.chinese_text_splitter import FlexibleRecursiveSplitter
from parser.load_api import convert_pdf_to_md, convert_file_type
from web_server.ai.models import Document, Paragraph

PARAGRAPH_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': """
            Role: 文档总结专家
            - version: 1.0
            - language: 中文
            - description: 你将得到User输入的一段文本，请详细提取且总结描述其内容，包含必须如实准确提取关键信息如所有指标及其数值数据等，最终按指定格式生成总结及描述。

            Skills
            - 擅长使用面向对象的视角抽取文本内容的对象属性(属性项:什么文档,当前页,对象主体,内容所属类型[摘要/引言/目录/首页/正文/公告/...]。
            - 生成详细及信息丰富的描述。
            - 擅长提取文本中的数值数据。
            - 擅长提取文本中所有指标信息。
            - 擅长生成严格符合JSON格式的输出。
            - 擅长使用清晰的语言完整总结文本的主要内容。
            - 擅长使用陈述叙事的风格总结文本的主要内容。

            Rules
            - 描述与总结不能省略内容。
            - 每个summary至少20字，用清晰准确的语言陈述，不添加额外主观评价，陈述出所有指标和对象属性(如:这是xxx(什么文档/章节)第xxx页xxx(对象主体)的[摘要/引言/目录/首页/正文/公告/...]内容，内容包含以下指标内容xxx)。
            - summary必须声明页码，段落类型，对象主体这三个属性。
            - 每个content至少50个字，且必须涵盖文本中所有出现的指标信息及数值数据，文本中准确如实提取，避免出现遗漏情况，注重完整和清晰度。
            - 允许根据上下文内容智能分割，生成多个paragraph
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
            [
                {
                    "paragraph_name": "",#填写章节或段落名称
                    "summary": "<>", #段落描述；
                    "content": "",
                    "keywords": [],#关键词
                    "position":""，#段落在文中的位置，如第几页，第几章
                }
            ]
            ```
            Warning:
            -summary必须列出所有指标字段包括页码说明，禁止使用```等```字眼省略指标项，但不需要数值数据。
            -content必须列出所有指标及数值数据，不能省略。  
            -输出不要增加额外字段，严格按照Example Output结构输出。
            -不要解释行为。
        """
    },
    {
        'role': 'user',
        'content': """
            读取文档，使用中文生成这段文本的描述以及总结，最终按照Example Output样例生成完整json格式数据
        """
    }
]
PARAGRAPH_CATALOG_MESSAGES = [
    {
        'role': 'system',
        'content': """
            # Role: 文本标题结构提取器
            
            ## Profile
            - author: LangGPT
            - version: 1.0
            - language: 中文
            - description: 从任意格式文本中**仅**提取文中实际存在的一至三级大标题（跳过四级及以下标题），最终使用 Markdown 风格的 `#`（#、##、###）表示标题层级并将结果结构化为 JSON 输出。
            
            ## Skills
            1. 能基于多种线索（编号、缩进、格式、类型等）准确识别**一二三级标题**。
            2. 标题可为任意长度，保留标题全部原文与顺序。
            3. 忽略正文以及**四级及以下标题**（即`####` 及更多井号、或示例“1.1.1.1”、编号、缩进、标记等其他类似深度层次等）。
            4. 使用 Markdown 的 `#`（#、##、###）表示层级并保持原顺序。
            
            ## Rules
            1. 仅提取一、二、三级标题，**禁止**提取四级及以下标题；若检测到 `####` 及更多井号，或编号/缩进/标记中存在四级及更深层次时，直接跳过不输出。
            2. 标题内容保持不变，不做任何精简或修改，并保持原顺序。
            3. 忽略正文（普通文本）和其他无关元素，仅输出标题结构。
            4. 最终结果只输出为以下 JSON 结构，**键名固定**为 `"catalogs"`：
            
            ## Example Output
            ```json
            {
                "catalogs":  [] #<用 Markdown 形式的标题串列表>
            }
            Warning:
            -最多输出到三级标题###为止，禁止输出四级标题####；
        """
    },
    {
        'role': 'user',
        'content': '解析文本且提取文中所有一二三级标题结构，最终只需返回字符串形式大纲保留文中实际出现的标题不需要具体内容(#表示一级标题以此类推)<$content>'
    }
]
PARAGRAPH_JUDGE_MESSAGES = [
    {
        'role': 'system',
        'content': """
            # Role: 跨页文档连续性判别助手

            ## Profile
            - **Author**: LangGPT  
            - **Version**: 1.0  
            - **Language**: 中文 / 英文  
            - **Description**: 你是一位专业的跨页文档解析助手，负责基于内容功能块的变化来判断跨页文本是否连续。哪怕文本围绕同一主体对象（如同一家公司），只要内容功能块发生变化（如从“战略创新”切换到“公司治理”），也需准确识别并判定为不连续。

            ## Skills
            1. 深度理解文档内容，精准识别文本功能/话题块。  
            2. 忽略主体对象的一致性（同公司或同人），专注于内容功能块的变化。  
            3. 仅依据内容块的功能划分来判断连续性。  
            4. 输出简洁、结构化的连续性判断结果。

            ## Background
            在长篇文档中，哪怕内容都与同一家公司相关，也可能在不同部分呈现截然不同的功能块（例如：公司概述、战略创新、公司治理、荣誉奖项等）。一旦前后页面功能块不同，即可判定为不连续。

            ## Goals
            1. 严格基于内容块 / 功能块的变化来判断页面间的连续性。  
            2. 忽略是否属于同一主体，只关注内容在功能和逻辑上的划分。  
            3. 提供明确且结构化的输出结果，以支持后续文档处理流程。

            ## Rules
            1. 理解文本内容，并识别功能或话题变化。  
            2. 如果上一页与当前页属于同一功能块：  
                - 若上一页结尾内容尚未结束、当前页顺势衔接，为 full_continuation。  
                - 若上一页已完整阐述一个小结，当前页在同一功能块下继续展开，为 partial_continuation。  
                - 以上两种情形下，`is_continuous` 均为 'true'。  
            3. 如果当前页开始了新的功能块或话题（如从“公司战略”切换到“公司治理”），则 `is_continuous` 为 'false'，并判定为 'independent'。  
            4. 标题变化可作为参考线索，但最终判断需结合内容块的实际变化。  
            5. 解释部分力求简明扼要，概括出主要依据。

            ## Workflows
            1. **输入**：上一页（`previous_page_text`）与当前页（`current_page_text`）文本内容。  
            2. **识别**：深入理解两段文本所属的功能块或话题类型。  
            3. **判定**：若两页功能块相同 → `is_continuous` = 'true'；否则 → `is_continuous` = 'false'。  
                - 'true' → 根据内容连贯程度判定为 `full_continuation` 或 `partial_continuation`。  
                - 'false' → 判定为 `independent`。  
            4. **输出**：返回 JSON 格式结果，包含 `is_continuous`、`continuity_type`、`explanation` 三个字段。

            ## Example Output
            ```json
            {
                "is_continuous": "true" or "false",
                "continuity_type": "full_continuation" | "partial_continuation" | "independent",
                "explanation": "简要说明本次判定的主要逻辑，如话题是否连续、段落是否承接等。"
            }
            """
    },
    {
        'role': 'user'
    }
]


class NoEscapeConverter(MarkdownConverter):
    """ 重写MarkdownConverter更改转义策略 """

    def escape(self, text, parent_tags):
        # 直接返回原始文本，不做任何转义
        return text


class ParagraphParser(BaseParser):
    def __init__(self, llm: BaseLLM, kb_id, session):
        super().__init__(llm, kb_id, session)
        self.paragraphs = []
        self.parse_strategy = ''

    def pdf_parse(self, file_path):
        policies = {
            'page_split': self.__page_split,
            'catalog_split': self.__catalog_split,
            'automate_judgment_split': self.__automate_judgment_split,
            'agentic_chunking': self.__agentic_chunking
        }
        if self.parse_strategy not in policies:
            raise ValueError('异常的文本切割策略，请提供正确的文本分割策略')
        policies[self.parse_strategy](file_path)
        all_paragraphs = copy.deepcopy(self.paragraphs)
        return all_paragraphs

    def parse(self, **kwargs):
        file_path = kwargs.get('path')
        self.parse_strategy = kwargs.get('parse_strategy')
        file_obj = Path(file_path)

        # 文件转换为pdf
        if file_obj.suffix in ['.doc', '.docx']:
            temp_dir = tempfile.mkdtemp()
            convert_file_type(file_path, temp_dir)
            name = file_obj.name.replace(file_obj.suffix, '.pdf')
            file_path = os.path.join(temp_dir, name)
            print(file_path)

        if file_path.endswith('.pdf'):
            # TODO rm temp_dir
            return self.pdf_parse(file_path)

    def storage_parser_data(self, parent: Document):
        paragraphs = []
        for paragraph in self.paragraphs:
            paragraph['parent_id'] = parent.document_id
            paragraph['parent_description'] = f'此段落来源描述:<{parent.document_description}>'
            paragraphs.append(Paragraph(**paragraph))
        self.session.add_all(paragraphs)

    def collate_paragraphs(self, paragraph_content):
        if isinstance(paragraph_content, dict):
            paragraph_content['kb_id'] = self.kb_id
            paragraph_content['meta_data'] = {'最后更新时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            self.paragraphs.append(paragraph_content)
        elif isinstance(paragraph_content, list):
            for paragraph in paragraph_content:
                paragraph['kb_id'] = self.kb_id
                paragraph['meta_data'] = {'最后更新时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            self.paragraphs.extend(paragraph_content)

    def chat_parse_paragraph(self, cur_index, next_index, page_text):
        parse_messages = copy.deepcopy(PARAGRAPH_PARSE_MESSAGES)
        parse_messages[1]['content'] += f"```<当前页:{cur_index}至{next_index}, 段落原文:{page_text}>```"
        paragraph_content = self.llm.chat(parse_messages)[0]
        self.collate_paragraphs(paragraph_content)

    def __catalog_split(self, file_path):
        """
        文本切割策略-目录
        按照目录切割
        场景: 目录层级不多优先
        """

        def find_text_page(target_text):
            """ 查找文本所在PDF中的页码 """
            import fitz
            doc = fitz.open(file_path)

            for page_num in range(len(doc)):
                text = doc.load_page(page_num).get_text().replace('\n', '').replace(' ', '')

                if target_text in text and page_num >= last_index - 1:
                    return page_num + 1

            return -1

        def html_to_markdown(pages: str):
            """ html形式table转化为markdown """
            pattern = '<!--.*?-->|<html[^>]*>[\s\S]*?</html>'
            htmls = re.findall(pattern, pages)
            for html in htmls:
                markdown_html = NoEscapeConverter().convert(html)
                pages = pages.replace(html, markdown_html)

            return pages

        def preprocess_markdown_titles(markdown_titles):
            """ 预处理Markdown格式的标题列表，去除#符号和空格 """
            processed = markdown_titles
            return processed

        def split_markdown_structured_document(full_text: str,
                                               markdown_titles: list[str]) -> dict[str, dict]:
            """
            根据 Markdown 目录切割 PDF 文本。
            - 找不到的标题自动跳过，不影响后续切割。
            - 返回 {clean_title: {"raw_title": 原始标题, "content": 对应内容}}
            """
            import re, unicodedata

            PUNCT_CLASSES = {
                "(": r"[\(\（]",
                ")": r"[\)\）]",
                ",": r"[,，]",
                ":": r"[:：]",
                ";": r"[;；]",
                ".": r"[\.。]",
                "!": r"[!！]",
                "?": r"[\?？]",
                "-": r"[-－﹣_]",
                "/": r"[/／]",
            }

            def _clean(t: str) -> str:
                # 去掉井号、空白并做全角→半角归一
                return unicodedata.normalize("NFKC", re.sub(r'^#+\s*', '', t)).strip()

            def _build_pattern(title: str) -> str:
                """
                把中文符号和英文符号视为同一个：
                例：'三、投资管理（二）费用' → S∙a∙v∙e…
                """
                parts = []
                for ch in title:
                    if ch.isspace():
                        parts.append(r"\s*")  # 任意空白
                    elif ch in PUNCT_CLASSES:
                        parts.append(PUNCT_CLASSES[ch])
                    else:
                        parts.append(re.escape(ch))
                # 标题行以换行或文末结束
                return "".join(parts) + r"(?:\s*\n|\Z)"

            clean_titles = [_clean(t) for t in markdown_titles]

            valid_titles, matches = [], []
            last_pos = 0

            for t in clean_titles:
                pat = _build_pattern(t)
                m = re.search(pat, full_text[last_pos:], flags=re.MULTILINE)
                if not m:  # 找不到就跳过
                    print(f"[SKIP] 未匹配标题 -> {t}")
                    continue

                start = last_pos + m.start()
                end = last_pos + m.end()
                matches.append((start, end))
                valid_titles.append(t)
                last_pos = end
            # 如果一个都没匹配到，直接返回空 dict
            if not matches:
                return {}

            # 结尾哨兵，简化最后一段计算
            matches.append((len(full_text), len(full_text)))

            # 构造分块结果
            sections = {}
            for idx, title in enumerate(valid_titles):
                title_start, title_end = matches[idx]
                next_start = matches[idx + 1][0]

                raw_title = full_text[title_start:title_end].strip('\n')
                content = full_text[title_end:next_start].strip('\n')

                sections[title] = {"raw_title": raw_title, "content": content}

            return sections

        pdf_content = convert_pdf_to_md(file_path)

        catalog_messages = copy.deepcopy(PARAGRAPH_CATALOG_MESSAGES)
        template = Template(catalog_messages[1]['content'])
        catalog_messages[1]['content'] = template.substitute(content=pdf_content)
        catalog_result = self.llm.chat(catalog_messages)[0]
        catalogs = catalog_result['catalogs']
        titles = catalogs
        if isinstance(catalog_result['catalogs'], str):
            titles = catalogs.split('\n')
        print(titles)
        try:
            result = split_markdown_structured_document(pdf_content, titles)

            last_index = 0
            # 根据目录层级分割文本块
            for clean_title, block in result.items():
                raw_title = block['raw_title']
                raw_content = block['content']
                print(f"【Markdown标题】{clean_title}")
                print(f"【实际匹配标题】{raw_title}")
                print(f"【内容片段】\n{raw_content}\n")
                raw_content = raw_content.replace(' ', '').replace('\n', '')
                if '|' in raw_content:
                    raw_content = raw_content.replace('|', '')
                if '---' in raw_content:
                    raw_content = raw_content.replace('---', '')
                if '#' in raw_content:
                    raw_content = raw_content.replace('#', '')
                content = raw_content
                cur_index = find_text_page(content[:20])
                next_index = find_text_page(content[-20:])
                next_index = next_index if next_index != -1 else cur_index
                last_index = next_index
                if len(content) > 0:
                    print(cur_index)
                    print(next_index)
                    page_text = f'标题({raw_title}) 内容({raw_content})'
                    self.chat_parse_paragraph(cur_index, next_index, page_text)
        except ValueError as e:
            print(str(e))

    def __automate_judgment_split(self, file_path):
        """
        文本切割策略-轮询自动判断
        按页轮询自主大模型判断上下文
        场景: 目录层级多、文件结构复杂优先
        """
        import fitz

        pdf_content = fitz.open(file_path)
        index = 0
        page_contents = [page.get_text() for page in pdf_content.pages()]

        # 上下文连贯判断
        while index < len(page_contents):
            cur_index = index
            previous_page_text = page_contents[index]
            next_index = index + 1
            while next_index < len(page_contents):
                current_page_text = page_contents[next_index]
                user_content = {
                    'previous_page_text': f'```{previous_page_text}```',
                    'current_page_text': f'```{current_page_text}```',
                }
                PARAGRAPH_JUDGE_MESSAGES[1]['content'] = str(user_content)
                judge_result = self.llm.chat(PARAGRAPH_JUDGE_MESSAGES)[0]
                print(judge_result)
                if 'is_continuous' in judge_result and judge_result['is_continuous'] == 'false':
                    index = next_index
                    break

                previous_page_text += current_page_text
                index = next_index
                next_index += 1
            self.chat_parse_paragraph(cur_index + 1, next_index, previous_page_text)
            print(cur_index + 1, next_index)
            print(self.paragraphs)
            # 截止至文件尾部
            if next_index == len(page_contents):
                break

    def __page_split(self, file_path):
        """
        文本切割策略-按页切割
        场景: 目录层级多、文件结构复杂优先
        """
        import fitz
        doc = fitz.open(file_path)
        with ThreadPoolExecutor(max_workers=25) as executor:
            tasks_page = []
            for page in doc.pages():
                doc_markdown = page.get_text()
                page_count = page.number + 1
                parse_messages = copy.deepcopy(PARAGRAPH_PARSE_MESSAGES)
                # parse_messages[0]['content'] = system_prompt
                parse_messages[1]['content'] += f"```<当前页:{page_count}, 段落原文:{doc_markdown}>```"
                task = executor.submit(self.llm.chat, parse_messages)
                tasks_page.append(task)

            for task in as_completed(tasks_page):
                paragraph_content = task.result()[0]
                self.collate_paragraphs(paragraph_content)

    def __agentic_chunking(self, file_path):
        """
        文本切割策略-agentic_chunking
        场景: 处理速度最慢，能够保持极致的上下文语义连贯
        """
        import fitz

        pdf_content = fitz.open(file_path)
        page_contents = ''.join([page.get_text() for page in pdf_content.pages()])

        ps = FlexibleRecursiveSplitter(granularity="sentence", chunk_size=1024, overlap_units=2)
        organizer = ChunkOrganizer()
        chunks = []

        for i, sentence in enumerate(ps.split(page_contents), 1):
            chunks = organizer.process(sentence)

        for chunk in chunks:
            chunk_dict = chunk.model_dump()
            chunk_dict['paragraph_id'] = uuid.UUID(chunk_dict.pop('chunk_id'))
            chunk_dict['paragraph_name'] = chunk_dict.pop('paragraph_name')
            chunk_dict['summary'] = chunk_dict.pop('summary')
            chunk_dict['keywords'] = chunk_dict.pop('keywords')
            chunk_dict['position'] = chunk_dict.pop('position')
            chunk_dict['content'] = ' '.join(chunk_dict.pop('propositions'))
            chunk_dict['meta_data'] = {'最后更新时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            chunk_dict['kb_id'] = self.kb_id
            self.paragraphs.append(chunk_dict)
