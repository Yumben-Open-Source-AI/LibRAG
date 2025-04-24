"""
@Project ：start-map 
@File    ：views.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/4/24 上午11:48 
"""
import datetime
import os

from fastapi import Form, UploadFile, File

from llm.qwen import Qwen
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from parser.paragraph_parser import ParagraphParser


def loading_data(kb_id: int, file_name: str, file_path: str, policy_type: str):
    # 进行文件预处理
    print('开始处理' + file_name, datetime.datetime.now())
    qwen = Qwen()

    par_parser = ParagraphParser(qwen, kb_id)
    paragraph_params = {
        'path': file_path,
        'policy_type': policy_type
    }
    all_paragraphs = par_parser.parse(**paragraph_params)
    print('paragraph', all_paragraphs)

    doc_parser = DocumentParser(qwen, kb_id)
    document_params = {
        'paragraphs': all_paragraphs,
        'path': file_path
    }
    document = doc_parser.parse(**document_params)
    print('document', document)

    # 段落解析器回填上级文档数据
    par_parser.back_fill_parent(document)
    par_parser.storage_parser_data()

    category_parser = CategoryParser(qwen, kb_id)
    category_params = {
        'document': document,
    }
    category = category_parser.parse(**category_params)
    print('category', category)

    # 文档解析器回填上级分类数据
    doc_parser.back_fill_parent(category)
    doc_parser.storage_parser_data()

    domain_parser = DomainParser(qwen, kb_id)
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
