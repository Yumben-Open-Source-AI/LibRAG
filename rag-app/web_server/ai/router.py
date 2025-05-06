import datetime
import json
import os
import re
from collections import deque
from typing import List, Literal, Optional, Annotated

import jieba
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, BackgroundTasks, Depends
from sqlmodel import select

from db.database import SessionDep, get_engine
from llm.deepseek import DeepSeek
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser

from llm.qwen import Qwen
from selector.base import SelectorParam
from selector.class_selector import CategorySelector
from selector.document_selector import DocumentSelector
from selector.domain_selector import DomainSelector
from selector.paragraph_selector import ParagraphSelector
from web_server.ai.models import KnowledgeBase, KbBase, Paragraph, Document, Category, Domain
from web_server.ai.views import loading_data

router = APIRouter(tags=['ai'], prefix='/ai')


@router.get('/recall')
async def query_with_llm(kb_id: int, session: SessionDep, question: str):
    from rank_bm25 import BM25Okapi
    import numpy as np

    params = SelectorParam(Qwen(), kb_id, session, question)
    selected_domains = DomainSelector(params).collate_select_params().start_select()
    print(selected_domains)
    selected_categories = CategorySelector(params).collate_select_params(selected_domains).start_select()
    print(selected_categories)
    selected_documents = DocumentSelector(params).collate_select_params(selected_categories).start_select()
    print(selected_documents)
    target_paragraphs = ParagraphSelector(params).collate_select_params(
        selected_documents).start_select().collate_select_result()
    print(target_paragraphs)

    recall_content = [par['content'] for par in target_paragraphs]

    # BM25进行段落召回评分
    tokenized_paragraphs = [list(jieba.cut(par)) for par in recall_content]
    tokenized_question = list(jieba.cut(question))
    bm25 = BM25Okapi(tokenized_paragraphs, k1=1.5, b=0.6)
    par_scores = bm25.get_scores(tokenized_question)
    exp_scores = [np.exp(s) for s in par_scores]
    for i, score in enumerate(exp_scores):
        target_paragraphs[i]['score'] = score
    return target_paragraphs


@router.get('/meta_data/{kb_id}/{meta_type}')
async def get_meta_data(kb_id: int, meta_type: str, session: SessionDep):
    all_parser = {
        'paragraph': Paragraph,
        'document': Document,
        'category': Category,
        'domain': Domain,
    }

    if meta_type not in all_parser:
        raise HTTPException(404, 'meta type is not supported')

    target = all_parser[meta_type]

    statement = select(target).where(target.kb_id == kb_id)
    return session.exec(statement).all()


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
async def upload_file(
        background_tasks: BackgroundTasks,
        kb_id: int = Form(...),
        files: List[str] = Form(...),
        policy_types: List[str] = Form(...),
        engine=Depends(get_engine)
):
    background_tasks.add_task(loading_data, kb_id, files, policy_types, engine)
    return {'message': '知识库文件加载任务后台处理中'}


@router.post('/knowledge_bases', response_model=KnowledgeBase)
async def create_knowledge_bases(kb: KbBase, session: SessionDep):
    db_kb = KnowledgeBase.model_validate(kb)
    session.add(db_kb)
    session.commit()
    session.refresh(db_kb)
    return db_kb


@router.get('/knowledge_base/{kb_id}')
async def read_knowledge_base(kb_id: int, session: SessionDep):
    know_base = session.get(KnowledgeBase, kb_id)
    documents = know_base.documents
    know_base = know_base.dict()

    if not know_base:
        raise HTTPException(status_code=404, detail="KnowledgeBase not found")

    know_base['documents'] = documents
    return know_base


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
