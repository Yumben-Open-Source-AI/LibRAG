import datetime
import json
import os
import re
from collections import deque
from typing import List, Literal, Optional, Annotated

from docx.document import Document
from docx.oxml.table import CT_Tbl
from docx.oxml.text.paragraph import CT_P
from docx.table import _Cell, Table
from docx.text.paragraph import Paragraph
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from sqlmodel import select

from db.database import SessionDep
from web_server.ai.schemas import KbBase, KnowledgeBase, FilePolicy
from llm.deepseek import DeepSeek
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from parser.paragraph_parser import ParagraphParser

from llm.qwen import Qwen
from selector.document_selector import DocumentSelector
from selector.paragraph_selector import ParagraphSelector

router = APIRouter(tags=['ai'], prefix='/ai')


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


@router.post('/upload')
async def loading_data(
        kb_id: int = Form(...),
        file: UploadFile = File(..., description="文件列表"),
        policy_type: str = Form(...,
                                       description="处理文本策略: 1.page_split(多并发按页分割)、2.catalog_split(识别段落标题自动分割)、3.automate_judgment_split(自动上下文分割)")
):
    base_dir = './files/'
    os.makedirs(base_dir, exist_ok=True)
    file_name = file.filename

    contents = await file.read()
    file_path = os.path.abspath(os.path.join(base_dir, file_name))
    with open(file_path, 'wb') as f:
        f.write(contents)

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


@router.post('/knowledge_bases', response_model=KnowledgeBase)
async def create_knowledge_bases(kb: KbBase, session: SessionDep):
    db_kb = KnowledgeBase.model_validate(kb)
    session.add(db_kb)
    session.commit()
    session.refresh(db_kb)
    return db_kb


@router.get('/knowledge_base/{kb_id}', response_model=KbBase)
async def read_knowledge_base(kb_id: int, session: SessionDep):
    kd = session.get(KnowledgeBase, kb_id)
    if not kd:
        raise HTTPException(status_code=404, detail="KnowledgeBase not found")
    return kd


@router.get('/knowledge_bases', response_model=list[KnowledgeBase])
async def read_knowledge_bases(
        session: SessionDep,
        offset: int = 0,
        limit: Annotated[int, Query(le=100)] = 100,
):
    heroes = session.exec(select(KnowledgeBase).offset(offset).limit(limit)).all()
    return heroes


@router.patch('/knowledge_base/{kb_id}', response_model=KbBase)
def update_knowledge_base(kb_id: int, kb: KbBase, session: SessionDep):
    kb_db = session.get(KnowledgeBase, kb_id)
    if not kb_db:
        raise HTTPException(status_code=404, detail="Hero not found")
    kb_data = kb.model_dump(exclude_unset=True)
    kb_db.sqlmodel_update(kb_data)
    session.add(kb_db)
    session.commit()
    session.refresh(kb_db)
    return kb_db


# @router.get('/meta_data/{kb_id}')
# async def get_meta_data(meta_type: str, kb_id: int, session: SessionDep):
#     data = []
#     base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../data'))
#
#     all_parser = {
#         'paragraph': 'paragraph_info.json',
#         'document': 'document_info.json',
#         'category': 'category_info.json',
#         'domain': 'domain_info.json',
#     }
#     if meta_type in all_parser:
#         file_name = all_parser[meta_type]
#         file_path = os.path.join(base_dir, file_name)
#         with open(file_path, 'r', encoding='utf-8') as f:
#             data = json.load(f)
#
#     return data


if __name__ == '__main__':
    os.environ['OPENAI_API_KEY'] = 'sk-3fb76d31383b4552b9c3ebf82f44157d'
    os.environ['OPENAI_BASE_URL'] = 'https://dashscope.aliyuncs.com/compatible-mode/v1'
    # page_split
    # catalog_split
    # automate_judgment_split
