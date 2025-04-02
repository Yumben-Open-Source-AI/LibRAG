import re

from collections import deque
import os

from llm.qwen import Qwen
from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph

from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from parser.paragraph_parser import ParagraphParser


def loading_data(filename: str, base_dir: str = '../../files/'):
    # TODO feat config system
    os.environ['OPENAI_API_KEY'] = 'sk-3fb76d31383b4552b9c3ebf82f44157d'
    os.environ['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'

    file_path = os.path.join(base_dir, filename)
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

    # back fill paragraph parent data
    par_parser.back_fill_parent(document)
    par_parser.storage_parser_data()

    category_parser = CategoryParser(qwen)
    category_params = {
        'document': document,
    }
    category = category_parser.parse(**category_params)

    # back fill document parent data
    doc_parser.back_fill_parent(category)
    doc_parser.storage_parser_data()

    domain_parser = DomainParser(qwen)
    domain_params = {
        'cla': category
    }
    domain = domain_parser.parse(**domain_params)

    # back fill cla parent data
    if category['new_classification'] == 'true':
        category_parser.back_fill_parent(domain)
        category_parser.storage_parser_data()

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
        r'C:\Users\Xman\Downloads\大数据应用平台V5.0项目E包-大数据共享系统V2.1功能拓展项目投标文件.docx')
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
    return root.children, doc_str


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


if __name__ == '__main__':
    loading_data(filename='比亚迪股份有限公司 2024年第三季度报告（2024-10-30）.pdf')
    # title_tree = [tree_to_dict(node) for node in title_tree]
    # merge_tree = merge_nodes(title_tree)
    #
    # print(extract_subtitles(merge_tree))
