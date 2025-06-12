import copy
import json
import os
import re
import tempfile
import uuid
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from string import Template
from llm.llmchat import LlmChat
from parser.agentic_chunking import ChunkOrganizer
from parser.base import BaseParser

from pathlib import Path

from parser.chinese_text_splitter import FlexibleRecursiveSplitter
from parser.load_api import convert_pdf_to_md, convert_file_type, PDFLoader
from tools.log_tools import parser_logger as logger
from tools.prompt_load import TextFileReader
from web_server.ai.models import Document, Paragraph

# 生成段落总结
PARAGRAPH_PARSE_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/parse/PARAGRAPH_SYSTEM.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/parse/PARAGRAPH_USER.txt")
    }
]
# 送入全文提取标题
FULL_TEXT_CATALOG_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/agent/FULL_TEXT_CATALOG_SYSTEN.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/agent/FULL_TEXT_CATALOG_USER.txt")
    }
]
# 送入跨页内容判断连续性
PARAGRAPH_JUDGE_MESSAGES = [
    {
        'role': 'system',
        'content': TextFileReader().read_file("prompts/agent/PARAGRAPH_JUDGE_SYSTEM.txt")
    },
    {
        'role': 'user',
        'content': TextFileReader().read_file("prompts/agent/PARAGRAPH_JUDGE_USER.txt")
    }
]


class ParagraphParser(BaseParser):
    def __init__(self, llm: LlmChat, kb_id, session):
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
            logger.debug(file_path)

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
        paragraph_content = self.llm.chat(parse_messages)
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
                    logger.debug(f'[SKIP] 未匹配标题 -> {t}')
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
        catalog_messages = copy.deepcopy(FULL_TEXT_CATALOG_MESSAGES)
        template = Template(catalog_messages[1]['content'])
        catalog_messages[1]['content'] = template.substitute(content=pdf_content)
        catalog_result = self.llm.chat(catalog_messages)
        catalogs = catalog_result['catalogs']
        titles = catalogs
        if isinstance(catalog_result['catalogs'], str):
            titles = catalogs.split('\n')
        logger.debug(f'解析目录:{titles}')
        try:
            result = split_markdown_structured_document(pdf_content, titles)

            last_index = 0
            # 根据目录层级分割文本块
            for clean_title, block in result.items():
                raw_title = block['raw_title']
                raw_content = block['content']
                logger.debug(f'【Markdown标题】{clean_title}')
                logger.debug(f'【实际匹配标题】{raw_title}')
                logger.debug(f'【内容片段】\n{raw_content}\n')
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
                    logger.debug(f'页码范围: {cur_index} - {next_index}')
                    page_text = f'标题({raw_title}) 内容({raw_content})'
                    self.chat_parse_paragraph(cur_index, next_index, page_text)
        except ValueError as e:
            logger.error(str(e), exc_info=True)

    def __automate_judgment_split(self, file_path):
        """
        文本切割策略-轮询自动判断
        按页轮询自主大模型判断上下文
        场景: 目录层级多、文件结构复杂优先
        """
        page_contents = PDFLoader(file_path).load_file()
        index = 0

        # 上下文连贯判断
        while index < len(page_contents):
            cur_index = index
            previous_page_text = page_contents[index]
            next_index = index + 1
            while next_index < len(page_contents):
                current_page_text = page_contents[next_index]
                paragraph_judge_messages = copy.deepcopy(PARAGRAPH_JUDGE_MESSAGES)
                template = Template(paragraph_judge_messages[1]['content'])
                paragraph_judge_messages[1]['content'] = template.substitute(
                    previous_page_text=previous_page_text,
                    current_page_text=current_page_text
                )
                judge_result = self.llm.chat(paragraph_judge_messages)
                logger.debug(judge_result)
                if 'is_continuous' in judge_result and judge_result['is_continuous'] == 'false':
                    index = next_index
                    break

                previous_page_text += current_page_text
                index = next_index
                next_index += 1
            self.chat_parse_paragraph(cur_index + 1, next_index, previous_page_text)
            logger.debug(f'页码范围: {cur_index + 1} - {next_index}')
            logger.debug(self.paragraphs)
            # 截止至文件尾部
            if next_index == len(page_contents):
                break

    def __page_split(self, file_path):
        """
        文本切割策略-按页切割
        场景: 目录层级多、文件结构复杂优先
        """
        page_contents = PDFLoader(file_path).load_file()
        with ThreadPoolExecutor(max_workers=25) as executor:
            tasks_page = []
            for page_count, doc_markdown in enumerate(page_contents, start=1):
                parse_messages = copy.deepcopy(PARAGRAPH_PARSE_MESSAGES)
                parse_messages[1]['content'] += f"```<当前页:{page_count}, 段落原文:{doc_markdown}>```"
                task = executor.submit(self.llm.chat, parse_messages)
                tasks_page.append(task)

            for task in as_completed(tasks_page):
                paragraph_content = task.result()
                self.collate_paragraphs(paragraph_content)

    def __agentic_chunking(self, file_path):
        """
        文本切割策略-agentic_chunking
        场景: 处理速度最慢，能够保持极致的上下文语义连贯
        """
        page_contents = ''.join(PDFLoader(file_path).load_file())
        logger.debug(f'AGENTIC_CHUNKING切割前文本:{page_contents}')
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
