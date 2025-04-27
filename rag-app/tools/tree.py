"""
@Project ：start-map 
@File    ：tree.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/4/23 上午10:44 
"""


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
