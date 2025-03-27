import json
import os.path
import uuid

import fitz

import openai
import pymupdf4llm
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

header = {
    "Host": "www.bydglobal.com",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:133.0) Gecko/20100101 Firefox/133.0",
    "Accept": "application/json;charset=utf-8;",
    "Accept-Language": "zh-CN,zh;q=0.8,zh-TW;q=0.7,zh-HK;q=0.5,en-US;q=0.3,en;q=0.2",
    "Accept-Encoding": "gzip, deflate, br, zstd", "X-Requested-With": "XMLHttpRequest",
    "Connection": "keep-alive",
    "Referer": "https://www.bydglobal.com/cn/Investor/InvestorAnnals.html?scroll=true",
    "Sec-Fetch-Dest": "empty", "Sec-Fetch-Mode": "cors", "Sec-Fetch-Site": "same-origin",
    "Cookie": "JSESSIONID=QkkmoXjOuFA5Mq8CYe8kfazBTSjRgT7Cv0seXg6NQ9lgPQ9QvlZU!1328154614!-628377588; _ga_S0CD5LNY1M=GS1.1.1740108702.1.1.1740109871.0.0.0; _ga=GA1.2.339892044.1740108703; _gid=GA1.2.910022650.1740108704; Hm_lvt_4a5d8a40f7652db15c0e21da37e0ed5b=1740108704; Hm_lpvt_4a5d8a40f7652db15c0e21da37e0ed5b=1740109586; HMACCOUNT=91FFFC4AC557E907; Hm_lvt_8fb49462150bd4d80d431c53c09c182b=1740109552; Hm_lpvt_8fb49462150bd4d80d431c53c09c182b=1740109580"
}


def create_llm_completion(llm, message_prompts: list, model: str = 'qwen2.5-72b-instruct', max_token: int = 8192,
                          timeout: int = 12000, temperature=0.6,
                          max_retries=3):
    def _try_parse_json(content: str) -> dict:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            import re
            json_match = re.findall(r"\{.*\}", content, re.DOTALL)
            if json_match:
                return json.loads(json_match[0])
            else:
                return content

    retries = 0
    while retries < max_retries:
        try:
            completion = llm.chat.completions.create(
                temperature=temperature,
                model=model,
                messages=message_prompts,
                max_tokens=max_token,
                timeout=timeout,
                top_p=0.95
            )
            content = completion.choices[0].message.content
            return _try_parse_json(content)
        except Exception as e:
            print(e)
            retries += 1


def ai_keyword(base_dir: str, filename: str):
    """
    提取报告内容
    """
    # init params
    page_count = 1
    page_content = ''
    doc = fitz.open(base_dir + filename)
    result = {'filename': filename, 'content': []}
    remote_llm = openai.OpenAI(
        api_key='sk-3fb76d31383b4552b9c3ebf82f44157d',
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )

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


if __name__ == '__main__':
    # ai_keyword('./', '比亚迪股份有限公司 2024年第三季度报告（2024-10-30）.pdf')
    import docx

    doc = docx.Document('大数据应用平台V5.0项目E包-大数据共享系统V2.1功能拓展项目投标文件.doc')
    for body in iter(doc.element.body):
        print(body)
