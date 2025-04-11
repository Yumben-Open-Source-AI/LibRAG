import json
import re

from collections import deque
import os

import fitz

from llm.deepseek import DeepSeek
from llm.qwen import Qwen
from fastapi import APIRouter
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from parser.paragraph_parser import ParagraphParser

router = APIRouter(tags=['ai'], prefix='/ai')

from llm.qwen import Qwen
from selector.document_selector import DocumentSelector
from selector.paragraph_selector import ParagraphSelector


@router.get('/query')
async def query_with_llm(question: str):
    qwen = Qwen()
    document_selector = DocumentSelector(qwen)
    selected_documents = document_selector.collate_select_params().start_select(question)
    paragraph_selector = ParagraphSelector(qwen)
    target_paragraphs = paragraph_selector.collate_select_params(selected_documents).start_select(
        question).collate_select_result()
    return target_paragraphs


@router.get('/meta_data')
async def get_meta_data(meta_type: str):
    data = []
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data'))

    all_parser = {
        'paragraph': 'paragraph_info.json',
        'document': 'document_info.json',
        'category': 'category_info.json',
        'domain': 'domain_info.json',
    }
    if meta_type in all_parser:
        file_name = all_parser[meta_type]
        file_path = os.path.join(base_dir, file_name)
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

    return data


@router.get('/rebuild')
async def rebuild_data():
    """
    重建domain领域以及category分类索引
    """
    deepseek = DeepSeek()

    documents = await get_meta_data(meta_type='document')
    for document in documents:
        doc_parser = DocumentParser(deepseek)
        doc_parser.document = document
        category_parser = CategoryParser(deepseek)
        category_params = {
            'document': document,
        }
        category = category_parser.parse(**category_params)
        print('category', category)

        # back fill document parent data
        doc_parser.back_fill_parent(category, True)
        doc_parser.storage_parser_data()

        domain_parser = DomainParser(Qwen())
        domain_params = {
            'cla': category
        }
        domain = domain_parser.parse(**domain_params)
        print('domain', domain)

        # back fill category parent data
        if category_parser.new_classification == 'true':
            category_parser.back_fill_parent(domain)
        category_parser.storage_parser_data()

        # back fill domain parent data
        if domain_parser.new_domain == 'true':
            domain_parser.back_fill_parent(None)
        domain_parser.storage_parser_data()


def loading_data(filename: str, base_dir: str = '../../files/公开文件和公告/'):
    file_path = os.path.join(base_dir, filename)
    deepseek = DeepSeek()
    qwen = Qwen()

    par_parser = ParagraphParser(qwen)
    paragraph_params = {
        'path': file_path
    }
    all_paragraphs = par_parser.parse(**paragraph_params)

    doc_parser = DocumentParser(qwen)
    document_params = {
        'paragraphs': all_paragraphs,
        'path': file_path
    }
    document = doc_parser.parse(**document_params)
    print('document', document)

    # 段落解析器回填上级文档数据
    par_parser.back_fill_parent(document)
    par_parser.storage_parser_data()

    category_parser = CategoryParser(qwen)
    category_params = {
        'document': document,
    }
    category = category_parser.parse(**category_params)
    print('category', category)

    # 文档解析器回填上级分类数据
    doc_parser.back_fill_parent(category)
    doc_parser.storage_parser_data()

    domain_parser = DomainParser(Qwen())
    domain_params = {
        'cla': category
    }
    domain = domain_parser.parse(**domain_params)
    print('domain', domain)

    # 若生成新分类数据则回填上级领域数据
    if category_parser.new_classification == 'true':
        category_parser.back_fill_parent(domain)
    category_parser.storage_parser_data()

    # 若生成新领域数据则回填上级数据
    if domain_parser.new_domain == 'true':
        domain_parser.back_fill_parent(None)
    domain_parser.storage_parser_data()


class TitleNode:
    def __init__(self, title, level):
        self.title = title  # title
        self.level = level  # level
        self.children = []  # children


def iter_block_items(parent):
    """
    Yield each paragraph and table child within *parent*, in document order.
    Each returned value is an instance of either Table or Paragraph. *parent*
    would most commonly be a reference to a main Document object, but
    also works for a _Cell object, which itself can contain paragraphs and tables.
    """
    if isinstance(parent, Document):
        parent_elm = parent.element.body
    elif isinstance(parent, _Cell):
        parent_elm = parent._tc
    else:
        raise ValueError("something's not right")

    for child in parent_elm.iterchildren():
        if isinstance(child, CT_P):
            yield Paragraph(child, parent)
        elif isinstance(child, CT_Tbl):
            yield Table(child, parent)


def read_table(table):
    table_str = ''
    for row in table.rows:
        current_row = '|'.join([cell.text.replace('\n', '').replace(' ', '') for cell in row.cells])
        row_str = "{}{}{}".format('|', current_row, '|')
        table_str += row_str + '\n'
    return table_str


def tree_to_dict(tree: TitleNode):
    """
    Converting a title tree to a dict
    """
    return {
        'title': tree.title,
        'level': tree.level,
        'children': [tree_to_dict(child) for child in tree.children]
    }


def read_word():
    import docx
    doc = docx.Document(
        r'C:\Users\yumben\Documents\WeChat Files\wxid_fohbbc6swku621\FileStorage\File\2025-04\贵阳农商银行超值宝3年28期理财产品2024年年度报告.docx')
    root = TitleNode("ROOT", level=-1)
    stack = deque([root])
    doc_str = ''

    for block in iter_block_items(doc):
        if isinstance(block, Paragraph):
            xml = block._p.xml
            title = block.text
            # get title rank
            if xml.find('<w:outlineLvl') > 0:
                start_index = xml.find('<w:outlineLvl')
                end_index = xml.find('>', start_index)
                outline_xml = xml[start_index:end_index + 1]
                outline_value = int(re.search("\d+", outline_xml).group())

                if outline_value <= 0:
                    continue
                new_node = TitleNode(title, level=outline_value)
                while stack[-1].level >= outline_value:
                    stack.pop()
                stack[-1].children.append(new_node)
                stack.append(new_node)
            doc_str += block.text
        elif isinstance(block, Table):
            doc_str += read_table(block)
    return root, doc_str


def merge_nodes(nodes):
    """
    Merge check title tree to filter duplicate items
    """
    import copy
    nodes = copy.deepcopy(nodes)
    i = 0
    while i < len(nodes):
        current = nodes[i]
        j = i + 1
        while j < len(nodes):
            next_node = nodes[j]
            if current['title'] == next_node['title'] and current['level'] == next_node['level']:
                current['children'].extend(next_node['children'])
                del nodes[j]
            else:
                j += 1
        current['children'] = merge_nodes(current['children'])
        i += 1
    return nodes


def extract_subtitles(data):
    def add_children(node):
        nonlocal subtitle
        for child in node.get('children', []):
            subtitle += child['title']
            add_children(child)

    result = []
    for first in data:
        for second in first['children']:
            # 提取二级标题
            subtitle = second['title']
            # 递归拼接子节点内容
            add_children(second)
            result.append(subtitle)
    return result


def preprocess_markdown_titles(markdown_titles):
    """预处理Markdown格式的标题列表，去除#符号和空格"""
    processed = []
    for title in markdown_titles:
        # 去除Markdown标题符号和前后空格
        clean_title = re.sub(r'^#+\s*', '', title.strip())
        processed.append(clean_title)
    return processed


def split_markdown_structured_document(full_text, markdown_titles):
    """
    根据Markdown格式的目录结构切割文档
    :param full_text: 完整文档文本
    :param markdown_titles: 包含Markdown标记的标题列表，例如 ["## 一、标题", "### （一）子标题"]
    :return: 按结构分割的字典 {处理后的标题: 内容}
    """
    # 预处理标题（去除Markdown符号）
    clean_titles = preprocess_markdown_titles(markdown_titles)

    # 构建正则表达式模式（精确匹配清洗后的标题）
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


if __name__ == '__main__':
    # loading_data(filename='贵阳农村商业银行股份有限公司2022年度社会责任报告.pdf')
    os.environ['OPENAI_API_KEY'] = 'sk-3fb76d31383b4552b9c3ebf82f44157d'
    os.environ['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    deepseek = DeepSeek()

    import fitz

    # content = fitz.open('../../files/公开文件和公告/贵阳农村商业银行股份有限公司重大关联交易信息披露报告.pdf')
    #
    # content = ''.join([page.get_text() for page in content.pages()])
    # content.replace('\n', '')
    # print(content)

    content = """
        # 贵阳农村商业银行股份有限公司重大关联交易信息披露报告  
        根据《银行保险机构关联交易管理办法》以及《贵阳农村商业银行股份有限公司关联交易管理办法（试行）》等相关规定，现将贵阳农村商业银行股份有限公司（以下简称本行）近期重大关联交易相关情况披露如下：  
        ## 一、关联交易概述  
        2024 年 8 月 30 日，本行向贵州省国有资本运营有限责任公司（以下简称省资本公司）办理流动资金贷款 5 亿元，期限 1 年，贷款利率为 $3.35\%$ ，担保方式为存单质押。  
        ## 二、交易对手情况  
        ### （一）贵州省国有资本运营有限责任公司  
        主体类型：有限责任公司  
        经营范围：法律、法规、国务院决定规定禁止的不得经营；法律、法规、国务院决定规定应当许可（审批）的，经审批机关批准后凭许可（审批）文件经营;法律、法规、国务院决定规定无需许可（审批）的，市场主体自主选择经营。（承担省委、省政府下达的重大民生工程和重点项目建设投融资业务；土地开发；国有资源及资产经营管理；对批准注入的国有资产和承建项目形成的国有资产进行经营管理；开展金融股权投资、基金管理与资产管理业务；物业经营、物业管理；企业并购与重组；对外股权投资；风险投资；受托资产管理；债务对应资产的批量收购、处置；投融资管理相关咨询业务；房屋出租；股东决定的其他投融资业务。）  
        法定代表人：王贵军  
        注册地址：贵州省贵阳市云岩区南垭路 67 号  
        注册资本及其变化：人民币 600.00 亿元。省资本公司最近一次变更注册资本为 2019 年 9 月 6 日，将其注册资本由 100.00 亿元增加至人民币 600.00 亿元。  
        ### （二）与本行的关联关系  
        贵州金融控股集团有限责任公司（贵州贵民投资集团有限责任公司）持有本行超过 $5\%$ 的股份，省资本公司作为省金控集团的全资子公司，根据《银行保险机构关联交易管理办法》第七条，纳入本行关联方管理。  
        ## 三、定价政策  
        该笔业务属于本行正常经营范围内发生的常规业务，与关联方之间的交易遵循市场化定价原则，以不优于对非关联方同类交易的条件开展关联交易，不存在利益输送及价格操纵行为，没有损害本行和股东的利益，符合关联交易管理要求的公允性原则，不影响本行独立性，不会对本行的持续经营能力、损益及资产状况构成不利影响。  
        ## 四、关联交易金额及相应比例  
        截至 2024 年二季度末，本行资本净额为135.76 亿元，上述关联交易占本行上季度资本净额的 $3.68\%$ ,超过上季度资本净额的 $1\%$ ，因此认定为重大关联交易。  
        ## 五、审批程序及决议情况  
        本行与省资本公司开展的关联交易已分别经本行第二届董事会关联交易控制委员会 2024 年第三次会议、第二届董事会第十四次会议审议通过，关联董事对本次关联交易回避表决，会议的召开及表决程序符合法律法规及监管要求。  
        ## 六、独立董事发表意见情况  
        本行三位独立董事均对上述关联交易发表了独立意见，认为关联交易事项已履行了必要的审批程序，与本行实际业务需求相匹配，依照市场公允价格进行，符合本行和全体股东的利益，不存在损害公司、股东，特别是中小股东利益的情形。  
        贵阳农村商业银行股份有限公司2024 年 9 月 18 日
    """
    messages = [
        {
            'role': 'user',
            'content': f'解析文本且提取文中所有标题结构，最终只需返回大纲序列保留文中实际出现的标题不需要具体内容(#表示一级标题以此类推)，生成之后需要自己检查一遍是否是文中实际标题<{content}>'
        }
    ]

    # print(deepseek.chat(messages))

    markdown_titles = "# 贵阳农村商业银行股份有限公司重大关联交易信息披露报告  \n## 一、关联交易概述  \n## 二、交易对手情况  \n### （一）贵州省国有资本运营有限责任公司  \n### （二）与本行的关联关系  \n## 三、定价政策  \n## 四、关联交易金额及相应比例  \n## 五、审批程序及决议情况  \n## 六、独立董事发表意见情况".split(
        '\n')
    try:
        result = split_markdown_structured_document(content, markdown_titles)

        # 打印切割结果
        for original_title in markdown_titles:
            clean_title = preprocess_markdown_titles([original_title])[0]
            print(f"【Markdown标题】{original_title}")
            print(f"【实际匹配标题】{result[clean_title]['raw_title']}")
            print(f"【内容片段】\n{result[clean_title]['content']}\n")
            print("=" * 80)

    except ValueError as e:
        print(str(e))
