import uuid
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import pymupdf4llm
import openai

from llm.qwen import Qwen

PARAGRAPH_PARSE_MESSAGES = [
    {'role': 'system', 'content': """
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
            "paragraph_name": "",#填写章节或段落名称
            "paragraph_id": "{{#1742956971474.text#}}",
            "summary": "段落描述:<>",
            "content": "",
            "keywords": [],#关键词
            "position":""，#段落在文中的位置
            "metadata": {最后更新时间: "{{#1742954273623.text#}}"}
        }
        ```
        Warning:
            -summary必须列出所有指标字段，禁止使用```等```字眼省略指标项，但不需要数值数据。
            -content必须列出所有指标及数值数据，不能省略。  
    """}
]


def loading_data(filename: str, base_dir: str = 'data/'):
    os.environ['OPENAI_API_KEY'] = 'sk-3fb76d31383b4552b9c3ebf82f44157d'
    os.environ['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    page_count = 1
    page_content = ''
    doc = pymupdf4llm.to_markdown(base_dir + filename)
    result = {'filename': filename, 'content': []}
    qwen = Qwen()

    # 生成每页段落描述
    system_prompt = """    
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
        - 描述与总结只能输出中文，不得输出任何英文单词、短语或句子、不能省略。
        - 每个summary至少20字，用清晰准确的语言陈述，不添加额外主观评价，陈述出所有指标和对象属性(如:这是xxx第xxx页的[摘要/引言/目录/首页/正文/公告/...]内容，内容包含以下指标内容xxx)。
        - 每个description至少50个字，且必须涵盖文本中所有出现的指标信息及数值数据，文本中准确如实提取，避免出现遗漏情况，注重完整和清晰度。
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
            "summary": "",
            "description": ""
        }
        ```
        Warning:
         -summary必须列出所有指标字段，禁止使用```等```字眼省略指标项，但不需要数值数据。
         -description必须列出所有指标及数值数据，不能省略。  
    """

    with ThreadPoolExecutor(max_workers=25) as executor:
        tasks_page = {}
        for page in doc:
            doc_markdown = page.get_text()
            task_param = {
                'llm': remote_llm,
                'model': 'qwen2.5-72b-instruct',
                'message_prompts': [
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user',
                     'content': f"读取文档，使用中文生成这段文本的描述以及总结，最终生成完整json格式数据```page_number:{page_content},content:{doc_markdown}```"}
                ],
                'max_token': 8192,
                'timeout': 120000
            }
            task = executor.submit(create_llm_completion, **task_param)
            tasks_page[task] = page_count
            page_count += 1

        for task in as_completed(tasks_page.keys()):
            completion = task.result()
            page_count = tasks_page[task]
            completion['page_number'] = page_count
            completion['index'] = str(uuid.uuid4())
            result['content'].append(completion)

            if page_count < 25:
                # 页数限制避免数据量超出max_tokens
                print(completion)
                page_content += completion['description']

    # 生成全文总结
    system_prompt = """
                # Roles:文档总结专家
                - language：中文
                - description：你擅长根据文档段落内容进行概括，用户会提供一篇文章的段落信息，理解段落内容且进行充分总结概括涉及的主要业务领域信息及时间维度信息。

                # Skill:
                - 擅长概括文档所属的领域信息且生成简洁总结性内容。

                # Rules:
                - 以叙述的语义进行总结表述。
                - 仅概括文档所属的业务领域以及时间维度信息，不需要生成具体数值。
                - 根据文档内容生成相关时间维度信息的陈述。
                - 概括至少20个字，且需要概括所有文档中实际出现的业务领域，确保不存在遗漏业务领域情况。

                # Workflows:
                1. 获取段落内容。
                2. 理解所有段落内容。
                3. 仅精准概括文中所属什么业务领域，且概括的业务领域概念定义清晰，具备行业专业性。
                4. 最终输出概括，确保准确性、简洁性以及时间维度的完整性。

                # Example output
                这是XXX年XXX文档，文档内容涵盖了XXXX业务领域信息。
                """
    completion = create_llm_completion(remote_llm, 'qwen2.5-72b-instruct', [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': str(
            page_content) + '\n根据文档段落内容生成一句话的简洁精准概括'}
    ], max_token=8192, timeout=120000)
    result['overall_description'] = completion

    # summary更新段落描述
    for content in result['content']:
        content['summary'] = f'段落来源描述:{result["overall_description"]};段落内容描述:{content["summary"]}'

    # 根据页码重排序段落
    result['content'] = sorted(result['content'], key=lambda x: x['page_number'])
    with open('data/byd_info.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        data.append(result)

    with open('data/byd_info.json', 'w+', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False))

    return 'success'
