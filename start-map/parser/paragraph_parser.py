import copy
import json
import uuid
import fitz
import datetime
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
            1. **理解文本内容**，并识别功能或话题变化。  
            2. 如果上一页与当前页属于同一功能块：  
                - 若上一页结尾内容尚未结束、当前页顺势衔接，为 **full_continuation**。  
                - 若上一页已完整阐述一个小结，当前页在同一功能块下继续展开，为 **partial_continuation**。  
                - 以上两种情形下，`is_continuous` 均为 **true**。  
            3. 如果当前页开始了新的功能块或话题（如从“公司战略”切换到“公司治理”），则 `is_continuous` 为 **false**，并判定为 **independent**。  
            4. 标题变化可作为参考线索，但最终判断需结合内容块的实际变化。  
            5. 解释部分力求简明扼要，概括出主要依据。
            
            ## Workflows
            1. **输入**：上一页（`previous_page_text`）与当前页（`current_page_text`）文本内容。  
            2. **识别**：深入理解两段文本所属的功能块或话题类型。  
            3. **判定**：若两页功能块相同 → `is_continuous` = true；否则 → `is_continuous` = false。  
                - **true** → 根据内容连贯程度判定为 `full_continuation` 或 `partial_continuation`。  
                - **false** → 判定为 `independent`。  
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

    def pdf_parse(self, file_path):
        doc = fitz.open(file_path)
        all_paragraphs = []
        index = 0
        page_contents = [page.get_text() for page in doc.pages()]

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
                if judge_result['is_continuous'] == 'false':
                    index = next_index
                    break

                previous_page_text += current_page_text
                next_index += 1

            parse_messages = copy.deepcopy(PARAGRAPH_PARSE_MESSAGES)
            parse_messages[1]['content'] += f"```<当前:{cur_index}至{next_index}页, 段落原文:{previous_page_text}>```"
            paragraph_content = self.llm.chat(parse_messages)[0]
            paragraph_content['paragraph_id'] = str(uuid.uuid4())
            paragraph_content['metadata'] = {'最后更新时间': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
            print(paragraph_content)
            all_paragraphs.append(paragraph_content)
            # 截止文件尾部
            if next_index == len(page_contents):
                break

        self.paragraphs = copy.deepcopy(all_paragraphs)
        return all_paragraphs

    def parse(self, **kwargs):
        file_path = kwargs.get('path')
        if file_path.endswith('.pdf'):
            return self.pdf_parse(file_path)
        elif file_path.endswith('.docx'):
            ...

    def storage_parser_data(self):
        with open(r'D:\xqm\python\project\llm\start-map\data\paragraph_info.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            data.extend(self.paragraphs)

        with open(r'D:\xqm\python\project\llm\start-map\data\paragraph_info.json', 'w+',
                  encoding='utf-8') as f:
            f.write(json.dumps(data, ensure_ascii=False))

    def back_fill_parent(self, parent):
        parent_id = parent['document_id']
        parent_description = parent['description']
        for paragraph in self.paragraphs:
            paragraph['parent'] = parent_id
            paragraph['parent_description'] = f'此段落来源描述:<{parent_description}>'
