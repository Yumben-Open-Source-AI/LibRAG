import copy
import json
import os
import uuid
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from string import Template
from llm.base import BaseLLM
from parser.base import BaseParser

PARAGRAPH_PARSE_MESSAGES = [
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
            - summary必须声明页码和段落类型这两个属性。
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
                "position":""，#段落在文中的页数
            }
            ```
            Warning:
            -summary必须列出所有指标字段包括页码说明，禁止使用```等```字眼省略指标项，但不需要数值数据。
            -content必须列出所有指标及数值数据，不能省略。  
            -输出不要增加额外字段，严格按照Example Output结构输出。
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
        'role': 'user',
        'content': '解析文本且提取文中所有标题结构，最终只需返回字符串形式大纲保留文中实际出现的标题不需要具体内容(#表示一级标题以此类推)，生成之后需要自己检查一遍是否是文中实际标题<$content>, 输出样例: {"catalogs": ""}'
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
            ```
            """
    },
    {
        'role': 'user'
    }
]


class ParagraphParser(BaseParser):
    def __init__(self, llm: BaseLLM):
        self.llm = llm
        self.paragraphs = []
        self.save_path = os.path.join(self.base_path, 'paragraph_info.json')

    def pdf_parse(self, file_path, policy_type='automate_judgment_split'):
        policies = {
            'page_split': self.__page_split,
            'catalog_split': self.__catalog_split,
            'automate_judgment_split': self.__automate_judgment_split,
        }
        if policy_type not in policies:
            raise ValueError('异常的文本切割策略，请提供正确的文本分割策略')

        all_paragraphs = policies[policy_type](file_path)
        self.paragraphs = copy.deepcopy(all_paragraphs)
        return all_paragraphs

    def parse(self, **kwargs):
        file_path = kwargs.get('path')
        policy_type = kwargs.get('policy_type')
        if file_path.endswith('.pdf'):
            return self.pdf_parse(file_path, policy_type)
        elif file_path.endswith('.docx'):
            ...

    def storage_parser_data(self):
        with open(self.save_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.extend(self.paragraphs)

        with open(self.save_path, 'w+', encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def back_fill_parent(self, parent):
        parent_id = parent['document_id']
        parent_description = parent['description']
        for paragraph in self.paragraphs:
            paragraph['parent'] = parent_id
            paragraph['parent_description'] = f'此段落来源描述:<{parent_description}>'

    def chat_parse_paragraph(self, cur_index, next_index, page_text):
        parse_messages = copy.deepcopy(PARAGRAPH_PARSE_MESSAGES)
        parse_messages[1]['content'] += f"```<当前:{cur_index}至{next_index}页, 段落原文:{page_text}>```"
        paragraph_content = self.llm.chat(parse_messages)[0]
        paragraph_content['paragraph_id'] = str(uuid.uuid4())
        paragraph_content['metadata'] = {'最后更新时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        return paragraph_content

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

                if target_text in text:
                    return page_num + 1

            return -1

        def miner_parse_pdf():
            """
            文档解析PDF转化为机器可读格式的工具 pdf to markdown
            """
            import os

            from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
            from magic_pdf.data.dataset import PymuDocDataset
            from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
            from magic_pdf.config.enums import SupportedPdfParseMethod

            # args
            pdf_file_name = os.path.abspath(file_path)
            name_without_suffix = pdf_file_name.split(".")[0]

            # prepare env
            local_image_dir, local_md_dir = "output/images", "output"
            image_dir = str(os.path.basename(local_image_dir))

            os.makedirs(local_image_dir, exist_ok=True)

            image_writer, md_writer = FileBasedDataWriter(local_image_dir), FileBasedDataWriter(
                local_md_dir
            )

            # read bytes
            reader1 = FileBasedDataReader("")
            pdf_bytes = reader1.read(pdf_file_name)  # read the pdf content

            # proc
            ## Create Dataset Instance
            ds = PymuDocDataset(pdf_bytes)

            ## inference
            if ds.classify() == SupportedPdfParseMethod.OCR:
                ds.apply(doc_analyze, ocr=True).pipe_ocr_mode(image_writer).dump_md(
                    md_writer, f"{name_without_suffix}.md", image_dir
                )

                with open(f'{name_without_suffix}.md', 'r', encoding='utf-8') as file:
                    data = file.read()
            else:
                ds.apply(doc_analyze, ocr=False).pipe_txt_mode(image_writer).dump_md(
                    md_writer, f"{name_without_suffix}.md", image_dir
                )

                with open(f'{name_without_suffix}.md', 'r', encoding='utf-8') as file:
                    data = file.read()

            return data

        def preprocess_markdown_titles(markdown_titles):
            """预处理Markdown格式的标题列表，去除#符号和空格"""
            processed = markdown_titles
            return processed

        def split_markdown_structured_document(full_text, markdown_titles):
            """
            根据Markdown格式的目录结构切割文档
            :param full_text: 完整文档文本
            :param markdown_titles: 包含Markdown标记的标题列表
            :return: 按结构分割的字典 {处理后的标题: 内容}
            """
            import re
            clean_titles = markdown_titles

            patterns = []
            for title in clean_titles:
                # 转义特殊字符，匹配标题行（可能包含换行）
                pattern = re.escape(title) + r'(?:\s*\n|\Z)'
                patterns.append(pattern)

            # 查找所有标题的起始位置
            matches = []
            last_pos = 0

            # 验证标题顺序
            for i, pattern in enumerate(patterns):
                match = re.search(pattern, full_text[last_pos:], flags=re.MULTILINE)
                # 标题带着'#'进行初次匹配
                if not match:
                    # 标题去掉'#'字符进行二次匹配
                    clean_titles[i] = re.sub(r'^#+\s*', '', clean_titles[i].strip())
                    match = re.search(re.escape(clean_titles[i]) + r'(?:。\s*|\s*\n|\Z)', full_text[last_pos:],
                                      flags=re.MULTILINE)
                    if not match:
                        expected_title = clean_titles[i]
                        found_titles = '\n'.join(clean_titles[:i])
                        raise ValueError(f"标题 '{expected_title}' 未找到，请确认：\n"
                                         f"1.标题顺序是否正确\n2.是否缺少必要标题\n3.已匹配标题列表：\n{found_titles}")
                start = last_pos + match.start()
                end = last_pos + match.end()
                matches.append((start, end))
                last_pos = start  # 允许重叠匹配

            # 添加文档结束位置
            matches.append((len(full_text), len(full_text)))

            # 提取内容块
            sections = {}
            for i in range(len(clean_titles)):
                title_start, title_end = matches[i]
                content_start = title_end
                content_end = matches[i + 1][0]

                # 提取原始标题（保留文档中的实际格式）
                raw_title = full_text[title_start:title_end].strip('\n')

                # 提取内容（保留原始换行符）
                content = full_text[content_start:content_end].strip('\n')

                # 存储到字典（使用清洗后的标题作为键）
                sections[clean_titles[i]] = {
                    'raw_title': raw_title,  # 文档中实际存在的标题
                    'content': content
                }

            return sections

        all_paragraphs = []
        pdf_content = miner_parse_pdf()
        print(pdf_content)

        template = Template(PARAGRAPH_CATALOG_MESSAGES[0]['content'])
        PARAGRAPH_CATALOG_MESSAGES[0]['content'] = template.substitute(content=pdf_content)
        parse_result = self.llm.chat(PARAGRAPH_CATALOG_MESSAGES)[0]
        catalogs = parse_result['catalogs']
        titles = catalogs
        if isinstance(parse_result['catalogs'], str):
            titles = catalogs.split('\n')
        print(titles)
        try:
            result = split_markdown_structured_document(pdf_content, titles)

            # 打印切割结果
            for original_title in titles:
                clean_title = preprocess_markdown_titles([original_title])[0]
                raw_title = result[clean_title]['raw_title']
                raw_content = result[clean_title]['content']
                print(f"【Markdown标题】{original_title}")
                print(f"【实际匹配标题】{raw_title}")
                print(f"【内容片段】\n{result[clean_title]['content']}\n")
                content = raw_content.replace(' ', '').replace('\n', '')
                cur_index = find_text_page(content[:20])
                next_index = find_text_page(content[-10:]) if find_text_page(content[-10:]) != -1 else cur_index
                if len(content) > 0:
                    print(cur_index)
                    print(next_index)
                    page_text = f'标题({raw_title}) 内容({raw_content})'
                    paragraph_content = self.chat_parse_paragraph(cur_index, next_index, page_text)
                    if paragraph_content:
                        all_paragraphs.append(paragraph_content)

            return all_paragraphs
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
        all_paragraphs = []
        index = 0
        page_contents = [page.get_text() for page in pdf_content.pages()]

        # 上下文连贯判断
        while index < len(page_contents):
            cur_index = index
            previous_page_text = page_contents[index]
            next_index = index + 1
            while next_index < len(page_contents):
                current_page_text = page_contents[next_index]
                user_content = f'previous_page_text:{previous_page_text}\n current_page_text:{current_page_text}'
                PARAGRAPH_JUDGE_MESSAGES[1]['content'] = user_content
                judge_result = self.llm.chat(PARAGRAPH_JUDGE_MESSAGES)[0]
                print(judge_result)
                if 'is_continuous' in judge_result and judge_result['is_continuous'] == 'false':
                    index = next_index
                    break

                previous_page_text += current_page_text
                index = next_index
                next_index += 1
            paragraph_content = self.chat_parse_paragraph(cur_index + 1, next_index, previous_page_text)
            all_paragraphs.append(paragraph_content)
            print(cur_index + 1, next_index)
            print(all_paragraphs)
            # 截止至文件尾部
            if next_index == len(page_contents):
                break
        return all_paragraphs

    def __page_split(self, file_path):
        """
        文本切割策略-按页切割
        场景: 目录层级多、文件结构复杂优先
        """
        import fitz
        doc = fitz.open(file_path)
        all_paragraphs = []
        page_count = 1
        with ThreadPoolExecutor(max_workers=25) as executor:
            tasks_page = []
            for page in doc.pages():
                doc_markdown = page.get_text()
                parse_messages = copy.deepcopy(PARAGRAPH_PARSE_MESSAGES)
                parse_messages[1]['content'] += f"```<当前页:{page_count}, 段落原文:{doc_markdown}>```"
                task = executor.submit(self.llm.chat, parse_messages)
                tasks_page.append(task)
                page_count += 1

            for task in as_completed(tasks_page):
                paragraph_content = task.result()[0]
                paragraph_content['paragraph_id'] = str(uuid.uuid4())
                paragraph_content['metadata'] = {'最后更新时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
                all_paragraphs.append(paragraph_content)

        return all_paragraphs
