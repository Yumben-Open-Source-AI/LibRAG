import datetime
import json
import os
import re
from collections import deque

from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from fastapi import APIRouter

from llm.deepseek import DeepSeek
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
async def rebuild_data(meta_type: str):
    """
    重建domain领域以及category分类索引
    """
    deepseek = DeepSeek()
    qwen = Qwen()

    # TODO 调整重建domain & category索引接口
    if meta_type == 'category':
        documents = await get_meta_data(meta_type='document')
        # TODO 清空category & domain 数据文件
        for document in documents:
            doc_parser = DocumentParser(deepseek)
            doc_parser.document = document
            category_parser = CategoryParser(qwen)
            category_params = {
                'document': document,
            }
            category = category_parser.parse(**category_params)
            print('category', category)

            # back fill document parent data
            doc_parser.back_fill_parent(category, True)
            doc_parser.storage_parser_data()

            domain_parser = DomainParser(qwen)
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
    elif meta_type == 'domain':
        categories = await get_meta_data(meta_type='category')
        for category in categories:
            category_parser = CategoryParser(qwen)
            category_parser.category = category
            domain_parser = DomainParser(qwen)
            domain_params = {
                'cla': category
            }
            domain = domain_parser.parse(**domain_params)
            print('domain', domain)

            category_parser.back_fill_parent(domain)
            category_parser.storage_parser_data()

            # back fill domain parent data
            if domain_parser.new_domain == 'true':
                domain_parser.back_fill_parent(None)
            domain_parser.storage_parser_data()


def loading_data(files: dict, base_dir: str = '../../files/'):
    for file_name, policy_type in files.items():
        file_path = os.path.join(base_dir, file_name)

        print('开始处理' + file_name, datetime.datetime.now())
        qwen = Qwen()

        par_parser = ParagraphParser(qwen)
        paragraph_params = {
            'path': file_path,
            'policy_type': policy_type
        }
        all_paragraphs = par_parser.parse(**paragraph_params)
        print('paragraph', all_paragraphs)

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

        domain_parser = DomainParser(qwen)
        domain_params = {
            'cla': category
        }
        domain = domain_parser.parse(**domain_params)
        print('domain', domain)

        category_parser.back_fill_parent(domain)
        category_parser.storage_parser_data()

        domain_parser.back_fill_parent(None)
        domain_parser.storage_parser_data()
        print(file_name + '处理完毕', datetime.datetime.now())


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


from markdownify import MarkdownConverter


class NoEscapeConverter(MarkdownConverter):
    """ 重写MarkdownConverter更改转义策略 """

    def escape(self, text):
        # 直接返回原始文本，不做任何转义
        return text


if __name__ == '__main__':
    os.environ['OPENAI_API_KEY'] = 'sk-3fb76d31383b4552b9c3ebf82f44157d'
    os.environ['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    # page_split
    # catalog_split
    # automate_judgment_split

    loading_data(
        {
            '大数据查询平台_接口文档_1.6.pdf': 'automate_judgment_split'
        }
    )
