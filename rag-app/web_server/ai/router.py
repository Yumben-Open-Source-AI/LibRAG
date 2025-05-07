from typing import Annotated

import jieba
from fastapi import APIRouter, HTTPException, Query, BackgroundTasks, Depends
from sqlmodel import select

from db.database import SessionDep, get_engine
from llm.deepseek import DeepSeek
from llm.qwen import Qwen
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from selector.base import SelectorParam
from selector.class_selector import CategorySelector
from selector.document_selector import DocumentSelector
from selector.domain_selector import DomainSelector
from selector.paragraph_selector import ParagraphSelector
from web_server.ai.models import KnowledgeBase, KbBase, Paragraph, Document, Category, Domain, CategoryDocumentLink
from web_server.ai.schemas import FileInfo
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

    return result


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
        files_info: FileInfo,
        engine=Depends(get_engine)
):
    background_tasks.add_task(loading_data, files_info, engine)
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
