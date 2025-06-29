import asyncio
import json
import os.path
import uuid
from decimal import Decimal
from functools import partial
from typing import Annotated, List

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, File, UploadFile, Form
from sqlmodel import select

from db.database import SessionDep
from llm.llmchat import LlmChat
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from selector.base import SelectorParam
from selector.class_selector import CategorySelector
from selector.document_selector import DocumentSelector
from selector.domain_selector import DomainSelector
from selector.paragraph_selector import ParagraphSelector
from tools.log_tools import selector_logger, parser_logger
from tools.result_scoring import ResultScoringParser
from web_server.ai.models import KnowledgeBase, KbBase, Paragraph, Document, Category, Domain, CategoryDocumentLink, \
    ProcessingTask

router = APIRouter(tags=['ai'], prefix='/ai')


@router.get('/recall')
async def query_with_llm(kb_id: int, session: SessionDep, question: str):
    llm_chat = LlmChat()
    params = SelectorParam(llm_chat, kb_id, session, question)
    selected_domains, domains = DomainSelector(params).collate_select_params().start_select()
    selector_logger.info(f'{question} -> {domains}')
    selected_categories, categories = CategorySelector(params).collate_select_params(selected_domains).start_select()
    selector_logger.info(f'{question} -> {domains} \n-> {categories}')
    selected_documents, documents = DocumentSelector(params).collate_select_params(selected_categories).start_select()
    selector_logger.info(f'{question} -> {domains} \n-> {categories} \n-> {documents}')

    if not selected_documents:
        return []

    target_paragraphs = ParagraphSelector(params).collate_select_params(
        selected_documents).start_select().collate_select_result()
    selector_logger.info(
        f'选择完成正在打分：{question} -> {domains} \n-> {categories} \n-> {documents} \n-> {target_paragraphs}')
    recall_content = [par['parent_description'] + par['content'] for par in target_paragraphs]
    if not recall_content:
        return []

    scorer_agent = ResultScoringParser(llm_chat)
    sem = asyncio.Semaphore(8)
    loop = asyncio.get_running_loop()

    async def score_one(idx: int, par_text: str):
        async with sem:
            # ★ 把同步 rate 放到线程池 ★
            score = await loop.run_in_executor(
                None,  # None = 默认 ThreadPoolExecutor
                partial(scorer_agent.rate, question, par_text)
            )

        # ----- 精度处理 -----
        rel = Decimal(str(score.get("context_relevance", 0)))
        suf = Decimal(str(score.get("context_sufficiency", 0)))
        clr = Decimal(str(score.get("context_clarity", 0)))
        total = (rel + suf + clr)

        target_paragraphs[idx].update(
            context_relevance=float(rel),
            context_sufficiency=float(suf),
            context_clarity=float(clr),
            total_score=float(total),
            diagnosis=score.get("diagnosis", ""),
        )

    # 并发跑完所有评分任务
    await asyncio.gather(*(score_one(i, txt) for i, txt in enumerate(recall_content)))

    target_paragraphs.sort(key=lambda x: x["total_score"], reverse=True)
    selector_logger.info(
        f'已完成打分：{question} -> {domains} \n-> {categories} \n-> {documents} \n-> {target_paragraphs}')
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
    db_result = session.exec(statement).all()

    result = []
    # TODO 优化序列化
    if meta_type == 'document':
        for doc in db_result:
            doc_dict = doc.dict()
            doc_dict['parent_id'] = [category.category_id for category in doc.categories]
            doc_dict['parent_description'] = [f'此文档所属父级类别描述:<{category.category_description}>' for category
                                              in doc.categories]
            result.append(doc_dict)
    elif meta_type == 'category':
        for category in db_result:
            category_dict = category.dict()
            category_dict['parent_description'] = f'此分类所属父级领域描述:<{category.domain.domain_description}>'
            result.append(category_dict)

    return result or db_result


@router.patch('/index/{kb_id}')
async def update_kb_index(kb_id: int, session: SessionDep):
    llm_chat = LlmChat()
    try:
        # 重建索引过程不能影响查询
        db_categories = session.query(Category).filter_by(kb_id=kb_id).all()
        db_category_ids = [category.category_id for category in db_categories]
        db_domains = session.query(Domain).filter_by(kb_id=kb_id).all()
        db_domain_ids = [domain.domain_id for domain in db_domains]
        # 重建类别及领域索引
        domains = []
        categories = []
        statement = select(Document).where(Document.kb_id == kb_id)
        db_documents = session.exec(statement)
        for doc in db_documents:
            doc_parser = DocumentParser(llm_chat, kb_id, session)
            doc_parser.document = doc
            cat_parser = CategoryParser(llm_chat, kb_id, session)
            domain_parser = DomainParser(llm_chat, kb_id, session)

            new_category = cat_parser.parse(**{
                'document': doc,
                'parse_type': 'rebuild',
                'ext_categories': categories
            })
            parser_logger.info(f'文件:{doc.document_name} 类别重构建:{new_category}')

            new_domain = domain_parser.parse(**{
                'category': new_category,
                'parse_type': 'rebuild',
                'ext_domains': domains
            })
            parser_logger.info(f'文件:{doc.document_name} 领域重构建:{new_domain}')

            doc_parser.rebuild_parser_data(new_category)
            cat_parser.rebuild_parser_data(new_domain)

            domains.append(new_domain)
            categories.append(new_category)

        # 清理旧数据
        session.query(Category).filter(Category.category_id.in_(db_category_ids)).delete()
        session.query(CategoryDocumentLink).filter(CategoryDocumentLink.category_id.in_(db_category_ids)).delete()
        session.query(Domain).filter(Domain.domain_id.in_(db_domain_ids)).delete()
        session.add_all(categories)
        session.add_all(domains)
        session.commit()
    except Exception as e:
        parser_logger.error(f'重构建异常:{e}', exc_info=True)
        session.rollback()


@router.post('/upload')
async def upload_file(
        session: SessionDep,
        items: str = Form(...),
        files: List[UploadFile] = File(...)
):
    try:
        items = json.loads(items)
        base_dir = os.path.abspath('./files')
        os.makedirs(base_dir, exist_ok=True)
        for i, file in enumerate(files):
            content = await file.read()
            file_path = os.path.join(base_dir, file.filename)
            with open(file_path, 'wb') as f:
                f.write(content)
            items[i]['file_path'] = file_path
            task = ProcessingTask(**{
                'status': 'pending',
                'file_path': file_path,
                'kb_id': items[i]['kb_id'],
                'parse_strategy': items[i]['policy_type']
            })
            session.add(task)
            session.commit()
    except Exception as e:
        session.rollback()
        parser_logger.error(f'{e}', exc_info=True)

    return {'message': '知识库文件加载任务后台处理中'}


@router.post('/knowledge_bases', response_model=KnowledgeBase)
async def create_knowledge_bases(kb: KbBase, session: SessionDep):
    db_kb = KnowledgeBase.model_validate(kb)
    session.add(db_kb)
    session.commit()
    session.refresh(db_kb)
    return db_kb


@router.get('/knowledge_base/{kb_id}')
async def query_knowledge_base(kb_id: int, session: SessionDep):
    know_base = session.get(KnowledgeBase, kb_id)
    documents = know_base.documents
    know_base = know_base.dict()

    if not know_base:
        raise HTTPException(status_code=404, detail="KnowledgeBase not found")

    know_base['documents'] = documents
    return know_base


@router.get('/knowledge_bases', response_model=list[KnowledgeBase])
async def query_knowledge_bases(
        session: SessionDep,
        offset: int = 0,
        limit: Annotated[int, Query(le=100)] = 100,
):
    return session.exec(select(KnowledgeBase).offset(offset).limit(limit)).all()


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


@router.delete('/knowledge_base/{kb_id}')
async def delete_knowledge_base(kb_id: int, session: SessionDep):
    session.query(Paragraph).filter_by(kb_id=kb_id).delete()
    db_documents = session.query(Document).filter_by(kb_id=kb_id)
    db_documents_ids = [doc.document_id for doc in db_documents]
    session.query(CategoryDocumentLink).filter(CategoryDocumentLink.document_id.in_(db_documents_ids)).delete()
    db_documents.delete()

    db_categories = session.query(Category).filter_by(kb_id=kb_id)
    db_categories_ids = [category.category_id for category in db_categories]
    session.query(CategoryDocumentLink).filter(CategoryDocumentLink.category_id.in_(db_categories_ids)).delete()
    db_categories.delete()

    session.query(Domain).filter_by(kb_id=kb_id).delete()
    session.query(KnowledgeBase).filter_by(kb_id=kb_id).delete()
    session.commit()


@router.delete('/document/{document_id}')
async def delete_document(document_id: str, session: SessionDep):
    document_id = uuid.UUID(document_id)
    session.query(Paragraph).filter_by(parent_id=document_id).delete()
    db_documents = session.query(Document).filter_by(document_id=document_id)
    db_documents_ids = [doc.document_id for doc in db_documents]
    session.query(CategoryDocumentLink).filter(CategoryDocumentLink.document_id.in_(db_documents_ids)).delete()
    # TODO 暂不同步调整category summary
    db_documents.delete()
    session.commit()


@router.get('/paragraphs/{document_id}')
async def query_paragraphs(document_id: str, session: SessionDep):
    return session.query(Paragraph).filter_by(parent_id=uuid.UUID(document_id)).all()


@router.get('/paragraph/{paragraph_id}')
async def query_paragraph(paragraph_id: str, session: SessionDep):
    paragraph_id = uuid.UUID(paragraph_id)
    return session.query(Paragraph).get(paragraph_id)
