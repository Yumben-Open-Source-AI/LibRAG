import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from jinja2 import Environment, meta, FunctionLoader

import openai
from docx import Document
from docxtpl import DocxTemplate

from web_server.ai.router import create_llm_completion


def read_docx(doc: Document):
    """
    读取docx 文档获取内容
    :param doc: Document object
    :return:
    """
    full_text = []
    for paragraph in doc.paragraphs:
        full_text.append(paragraph.text)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                full_text.append(cell.text)

    return ''.join(full_text)


def arguments_convert(arg: str, arg_type: str):
    """
    变量数值转换
    :param arg: 变量
    :param arg_type: 目标转换数值类型
    :return:
    """
    try:
        convert_mapping = {
            'int': int,
            'float': float,
            'str': str
        }
        return convert_mapping[arg_type](arg)
    except Exception as e:
        print(e)
        return arg


def generate_report():
    # 提取所有标识符
    doc = DocxTemplate('files/比亚迪尽职调查报告模板.docx')
    env = Environment(loader=FunctionLoader(read_docx))
    template = env.loader.get_source(env, doc.get_docx())
    parsed_content = env.parse(template)
    targets = meta.find_undeclared_variables(parsed_content)

    # 获取标识符映射信息
    with open('data/content_mapping.json', 'r', encoding='utf-8') as f:
        all_identifier = json.load(f)

    # 获取文档信息
    with open('data/byd_info-generate.json', 'r', encoding='utf-8') as f:
        doc_contents = json.load(f)
    doc_contents = {doc_detail['filename']: doc_detail for doc_detail in doc_contents}
    identifier_dict = {}

    # 创建远程llm 获取对应数据
    remote_llm = openai.OpenAI(
        api_key='sk-3fb76d31383b4552b9c3ebf82f44157d',
        base_url='https://dashscope.aliyuncs.com/compatible-mode/v1'
    )
    system_prompt = """
        # Role：数据解析师

        # Profile：
        - version：1.0
        - language：zh-cn
        - description：你将获得一个JSON数组作为现有数据，内容包含多个文件每页内容总结。用户会给出数据存放的位置例如XX页XX数据，你需要理解用户给出的操作提示，分析并通过理解数据存放位置如实准确无误的返回用户所需指定格式数据
        JSON结构：[
            {
                "filename": "文件名",
                "content": [{"description": "每一页文档的指标描述总结", "page_number": "第几页文档"}]
            }
        ]

        # Skills
        - 深度解析JSON数据结构，并理解其内容操作提示。
        - 具备优秀的索引能力，可以通过提示即数据存放位置找到对应数据。
        - 具备强大的文本问题解析能力，可以借助用户提示精准找到数据内容。

        # Rules
        - 遍历JSON数组中的所有文件及其文档每一页内容。
        - 通过用户给出的数据存放位置提示，在JSON数据中准确无误获取数据。
        - 如果是数值型数据，需要严格保证小数点位置正确。
        - 如实且精准返回匹配的内容，不添加额外信息或主观判断。

        # Workflow
        1. 获取并理解现有JSON数组数据意义。
        2. 获取并理解用户给出的数据存放位置提示。
        3. 分析用户所需数据在第几页，严格确保与JSON数据中page_number数值一致。
        4. 通过提示如实准确无误的返回用户所需数据。
        5. 最终输出用户所需格式数据。
    """
    with ThreadPoolExecutor(max_workers=25) as executor:
        tasks_type = {}
        for identifier in targets:
            values = all_identifier[identifier]
            operate = values['operate']
            values['identifier'] = identifier

            # TODO 不同维度数据来源获取
            task_param = {
                'llm': remote_llm,
                'message_prompts': [
                    {'role': 'user', 'content': str(doc_contents[values['target_file']])},
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': '从`第三页`文档中提取`交易性金融資產`，只输出不带有逗号分隔符数值金额'},
                    {'role': 'assistant', 'content': '25415146000'},
                    {'role': 'user', 'content': operate}
                ]
            }
            task = executor.submit(create_llm_completion, **task_param)
            tasks_type[task] = values

        for task in as_completed(tasks_type.keys()):
            completion = task.result()
            values = tasks_type[task]
            identifier = values['identifier']
            value = arguments_convert(completion, values['type'])
            print(identifier + ": " + str(value))
            identifier_dict[identifier] = value

    doc.render(identifier_dict)
    doc.save(filename='比亚迪尽职调查报告.docx')


generate_report()
