import json
import os.path
import uuid

import openai
import pymupdf4llm
import pymupdf
import requests

# doc = pymupdf.open('C_24070018IR-C-BYD+COMPANY-1707-HKEx.pdf')
# page_count = doc.page_count
# doc.close()
# doc_markdown = pymupdf4llm.to_markdown('C_24070018IR-C-BYD+COMPANY-1707-HKEx.pd', pages=[i for i in range(1, page_count)])

descriptions = {
    "公司信息": "描述企业基本情况，包括业务范围、市场定位及产业链构成。",
    "资产负债": "衡量企业总资产、总负债、资本支出、债务结构，反映偿债能力及资金流动性。",
    "财务状况": "表示企业在某一时刻经营资金的来源收入支出和分布情况。",
    "股东信息": "展示股东名单、持股比例、治理结构、控股股东、高管团队及投资者信息。",
    "法律合规": "衡量专利保护、法律诉讼、环保法规、税收合规及ESG评级等风险管理。"
}

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


def keybert_keyword():
    """ keyBERT 关键词提取技术 """
    from keybert import KeyBERT
    kw_model = KeyBERT(model='paraphrase-multilingual-MiniLM-L12-v2')
    keywords = kw_model.extract_keywords(doc_markdown, keyphrase_ngram_range=(1, 3), stop_words='english',
                                         use_maxsum=True,
                                         nr_candidates=20, top_n=5)


def nlp_keyword():
    """ nlp_mt5_zero-shot-augment_chinese-base 模型提取关键词 """
    from modelscope.pipelines import pipeline
    from langchain_text_splitters import MarkdownHeaderTextSplitter

    # 定义要分割的标题级别
    headers_to_split_on = [
        ("#", "Header 1"),
        ("##", "Header 2"),
        ("###", "Header 3"),
        ("####", "Header 4"),
    ]
    # 创建分割器
    markdown_splitter = MarkdownHeaderTextSplitter(headers_to_split_on, strip_headers=False)
    # 执行分割
    md_header_splits = markdown_splitter.split_text(doc_markdown)
    t2t_generator = pipeline('text2text-generation', 'damo/nlp_mt5_zero-shot-augment_chinese-base',
                             model_revision='v1.0.0')
    result = {}
    finally_result = []
    # 打印结果
    for index, doc in enumerate(md_header_splits):
        current_keyword = t2t_generator('抽取关键词:' + doc.page_content)
        print(current_keyword)
        result[str(index)] = current_keyword
        # 整理关键词
        text = current_keyword['text']
        [finally_result.append(keyword) for keyword in text.split(',') if keyword not in finally_result]
    print(finally_result)


def ai_keyword(base_dir: str, filename: str = '重庆长安汽车股份有限公司2024年第三季度报告.pdf'):
    """
        提取报告内容
        """
    import fitz
    # 线上ai概括信息
    remote_llm = openai.OpenAI(
        api_key='sk-3fb76d31383b4552b9c3ebf82f44157d',
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
    )
    doc = fitz.open(filename)
    result = {'filename': filename, 'content': []}

    system_prompt = """
            Role: 文档总结专家
            - version: 1.0 
            - language: 中文
            - description: 你将得到一段文本，详细提取且总结描述其内容，包含必须如实准确提取关键信息如所有指标及其数值数据等，最终按指定格式生成总结及描述。

            Skills 
            - 生成详细及信息丰富的描述。
            - 擅长提取文本中的数值数据。
            - 擅长提取文本中所有指标信息。
            - 擅长生成严格符合JSON格式的输出。
            - 擅长使用清晰的语言完整总结文本的主要内容。

            Rules 
            - 描述与总结只能输出中文，不得输出任何英文单词、短语或句子。
            - 每个总结至少20字，用清晰准确的语言表达，不添加额外主观评价，仅列出所有指标。
            - 每个描述至少50个字，且必须涵盖文本中所有出现的指标信息及数值数据，文本中准确如实提取，避免出现遗漏情况，注重完整和清晰度。
            - 严格生成结构化不带有转义的JSON数据的总结及描述。
            - 总结和描述仅使用文本格式呈现。

            Workflows 
            1. 获取用户提供的文本。 
            2. 逐行解析提取文本的指标。
            3. 理解文中主要内容，结合指标生成总结。
            4. 组合关键信息生成描述，确保指标信息及数值数据完整。
            5. 输出最终的总结及描述，确保准确性、可读性、完整性。

            Example Output
            ```json
            {
                "summary": "#必须列出所有指标但不需要数值数据",
                "description": "#所有指标及数值数据"
            }
            ```
        """
    page_count = 0
    for page in doc:
        doc_markdown = page.get_text()
        llm_params = {
            'temperature': 0.6,
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user',
                 'content': '读取文档，使用中文生成这段文本的描述以及总结，最终生成完整json格式数据' + doc_markdown}
            ],
            'model': 'deepseek-r1-distill-qwen-32b',
            'max_tokens': 16384,
            'timeout': 120000
        }
        response = remote_llm.chat.completions.create(**llm_params)
        response_content = response.choices[0].message.content

        # 处理思考链
        if '</think>' in response_content:
            response_content = response_content.split('</think>')[1]
        response_content = response_content.replace('\n', '')

        # 转换json
        if '```json' in response_content:
            response_content = response_content.replace('```', '').replace('json', '')
        response_content = json.loads(response_content)
        response_content['index'] = str(uuid.uuid4())
        result['content'].append(response_content)

        if page_count < 25:
            response_content
        page_count += 1

    # 生成总结
    system_prompt = """
            # Roles:文档总结专家
            - language：中文
            - description：你擅长根据文档段落内容进行概括，用户会提供一篇文章的段落信息，理解段落内容且进行总结概括涉及的主要业务领域信息。

            # Skill:
            - 擅长概括文档所属的领域信息且生成简洁总结性内容。

            # Rules:
            - 以叙述的语义进行总结表述。
            - 概括只需总结文档所属什么业务领域即可，不需要生成具体数值。
            - 概括不超过10个字，且需要概括所有文档中实际出现的业务领域，确保不存在遗漏业务领域情况。

            # Workflows:
            1. 获取段落内容。
            2. 理解所有段落内容。
            3. 仅精准概括文中所属什么业务领域，且概括的业务领域概念定义清晰，具备行业专业性。
            4. 最终输出概括，确保准确性、简洁性。
            """
    completion = remote_llm.chat.completions.create(
        temperature=0.6,
        model='deepseek-r1-distill-qwen-32b',
        messages=[
            {'role': 'user', 'content': str(
                result) + '\n根据文档段落内容生成一句话的简洁精准概括，需要总结文档段落涉及的业务领域'}
        ],
        max_tokens=16384,
        timeout=120000,
    )
    result['overall_description'] = completion.choices[0].message.content

    # 结合overall_description整理summary
    for content in result['content']:
        summary = content['summary']
        summary = f'段落来源描述:<{result["overall_description"]}>;段落内容描述:' + summary
        content['summary'] = summary

    with open('/robot/yumbotAPI/src/ai/byd_info.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        data.append(result)

    with open('/robot/yumbotAPI/src/ai/byd_info.json', 'w+', encoding='utf-8') as f:
        f.write(json.dumps(data, ensure_ascii=False))

    return 'success'


def splicing_keyword():
    with open('byd_info.json', 'r+', encoding='utf-8') as f:
        data = json.load(f)

    with open('byd_info.json', 'w', encoding='utf-8') as f:
        keywords = {
            "财务状况": ["资产负债表", "总资产", "总负债", "净资产", "资产负债率", "营收增长率", "经营现金流量净额",
                         "流动资产合计", "非流动资产合计", "所有者权益合计"],
            "股东信息": ["主要股东名单", "持股比例", "控股股东", "实际控制人", "机构投资者", "普通股股东总数",
                         "前10名股东持股情况", "持有有限售条件的股份数量", "质押、标记或冻结情况",
                         "报告期末表决权恢复的优先股股东总数", "前10名无限售流通股股东持股情况"]}
        result = {
            'title': '比亚迪股份有限公司 2024年第一季度报告（2024-04-29）',
            'http': 'http://www.bydglobal.com:80/sites/REST/resources/v1/aggregates/BYD_CN/BydInvestorNotice/1617162416460',
            'description': []
        }
        for index, field in enumerate(keywords.keys()):
            result['description'].append({
                'info': field,
                'keyword': keywords[field],
            })
        data.append(result)
        json.dump(data, f, ensure_ascii=False)


def get_online_report_list():
    """
    在线映射报告
    :return:
    """
    url = 'https://www.bydglobal.com/sites/REST/resources/v1/search/sites/BYD_CN/types/BydInvestorNotice/assets?fields=name,id,createdby,updatedby,description,Title,publishTime,loadFile&field:subtype:equals=regualrReport&orderBy=publishTime:desc&links=next'

    response = requests.get(url, headers=header).json()

    # Initialize an empty dictionary to store results
    result = {}

    # Loop through the 'items' and extract the necessary data
    for index, item in enumerate(response.get('items', [])):
        href = item.get('link', {}).get('href', '')
        title = item.get('Title', '')
        # Use the index or href as a unique key for each entry
        result[index] = {"http": href, "Title": title}

    return result


def download_online_files(hei):
    json.loads(hei)


def get_report_template(files: None):
    """
    获取文件模板列表
    :return:
    """
    reports = get_online_report_list()
    download_fail = ['比亚迪股份有限公司 2023年年报（2024-03-26）', '比亚迪股份有限公司 2023年年报（印刷版）（2024-04-26）',
                     '比亚迪股份有限公司 2024年中期报告（2024-08-28）', '比亚迪股份有限公司 2023年中期报告（2023-08-28）',
                     '比亚迪股份有限公司 2022年年报(印刷版) （2023-04-18）', '比亚迪股份有限公司 2022年年报（2023-03-28）',
                     '比亚迪股份有限公司 2022年中期报告（2022-08-29）',
                     '比亚迪股份有限公司 2021年年报(印刷版) （2022-04-14）']
    for key, report in reports.items():
        tile = report['Title']
        url = report['http']

        if tile in download_fail:
            continue

        if os.path.exists(tile + '.pdf'):
            markdown = pymupdf4llm.to_markdown(tile + '.pdf')
            import pathlib
            pathlib.Path(tile + '.md').write_bytes(markdown.encode('utf-8'))
            continue

        # print('start downloading', tile)
        response = requests.get(url, headers=header, timeout=100).status_code
        # start = response['start']
        # link_suffix = response[start]['loadFile_bloblink_']
        # download_url = 'https://www.bydglobal.com' + link_suffix
        #
        # with open(tile + '.pdf', 'wb') as f:
        #     f.write(requests.get(download_url, headers=header, timeout=100).content)
        # print(tile, 'finish')


if __name__ == '__main__':
    # ai_keyword()

    with open('byd_info.json', 'r', encoding='utf-8') as f:
        doc_markdown = json.load(f)

    for doc in doc_markdown:
        [for ]

