import json
import os
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated, List

from fastapi import APIRouter, HTTPException, Query, File, UploadFile, Form, Depends, status
from fastapi.responses import FileResponse
from fastapi_pagination import Page, paginate
from fastapi_pagination.ext.sqlalchemy import paginate as sqlalchemy_paginate
from fastapi_pagination.utils import disable_installed_extensions_check
from sqlmodel import select

from db.database import SessionDep
from llm.llmchat import LlmChat
from parser.class_parser import CategoryParser
from parser.document_parser import DocumentParser
from parser.domain_parser import DomainParser
from parser.load_api import convert_file_type
from parser.parser_worker import task_trigger
from selector.base import SelectorParam
from selector.class_selector import CategorySelector
from selector.document_selector import DocumentSelector
from selector.domain_selector import DomainSelector
from selector.paragraph_selector import ParagraphSelector
from tools.log_tools import selector_logger, parser_logger
from tools.result_scoring import ResultScoringParser
from web_server.ai.models import KnowledgeBase, KbBase, Paragraph, Document, Category, Domain, CategoryDocumentLink, \
    ProcessingTask
from web_server.ai.schemas import Token, UserTokenConfig
from web_server.ai.views import authenticate_user, create_access_token, verify_token, check_file_strategy, \
    create_refresh_token, refresh_access_token
from web_server.ai.views import check_file_md5

router = APIRouter(tags=['ai'], prefix='/ai')

# 建议放模块级，整个进程复用，避免每次请求新建线程池
SCORING_WORKERS = int(os.getenv("SCORING_WORKERS", "64"))
SCORING_POOL = ThreadPoolExecutor(max_workers=SCORING_WORKERS)


@router.get('/recall')
def query_with_llm(
        kb_id: int,
        session: SessionDep,
        question: str,
        has_source_text: bool = False,
        score_threshold: float | None = None,
        token=Depends(verify_token),
        has_score: bool = True,
) -> List[object]:
    """
    领域-分类-文档-段落召回
    Arag:
        kb_id: 知识库id
        session: 数据库连接
        question: 用户问题
        has_source_text: 是否返回原文
        score_threshold: 分数阈值
        token: 请求token
        has_score： 是否进行打分
    Return:
        target_paragraphs: 用户问题相关的段落答案
    """
    # params init
    if score_threshold and not isinstance(score_threshold, float):
        score_threshold = float(str(score_threshold))

    if not session.get(KnowledgeBase, kb_id):
        raise HTTPException(status_code=404, detail="数据库无此知识库，请检查")

    if question and isinstance(question, str):
        # TODO 问题字符串格式校验不够优雅
        question = question.replace('\r\n', '')
        question = question.replace('\n', '')
        question = question.replace('"', '')
        question = question.replace("'", '')

    llm_chat = LlmChat()
    params = SelectorParam(llm_chat, kb_id, session, question, has_source_text)
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
    # ---- 评分阶段（可选，纯同步+线程池并发）----
    # 逻辑：只要 has_score=True 且阈值未指定或 >=0 就进行评分
    do_scoring = has_score and (score_threshold is None or score_threshold >= 0)
    if not do_scoring:
        return target_paragraphs

    selector_logger.info(
        f'选择完成正在打分：{question} -> {domains} \n-> {categories} \n-> {documents} \n-> {target_paragraphs}')

    recall_content = [f"{par.get('parent_description', '')}{par.get('content', '')}" for par in target_paragraphs]
    if not recall_content:
        return []

    scorer_agent = ResultScoringParser(llm_chat)

    # 单个评分任务（在线程里执行，避免阻塞当前线程）
    def _score_one(idx: int, par_text: str):
        score = scorer_agent.rate(question, par_text)  # 同步函数，放在线程执行
        rel = Decimal(str(score.get("A", 0) or 0))
        suf = Decimal(str(score.get("B", 0) or 0))
        clr = Decimal(str(score.get("C", 0) or 0))
        total = rel + suf + clr
        return idx, {
            "context_relevance": float(rel),
            "context_sufficiency": float(suf),
            "context_clarity": float(clr),
            "total_score": float(total),
            "diagnosis": score.get("D", ""),
        }

    # 提交并发评分任务（最大并发由 SCORING_POOL 控制）
    futures = [
        SCORING_POOL.submit(_score_one, i, txt)
        for i, txt in enumerate(recall_content)
    ]

    # 回填评分结果（在当前线程回填，避免并发写共享列表）
    for fut in as_completed(futures):
        idx, updates = fut.result()
        target_paragraphs[idx].update(updates)

    # 排序与阈值过滤
    target_paragraphs.sort(key=lambda x: x.get("total_score", 0.0), reverse=True)

    if score_threshold is not None:
        selector_logger.info(f'过滤分数小于阈值：{score_threshold} 的段落')
        target_paragraphs = [x for x in target_paragraphs if x.get("total_score", 0.0) >= score_threshold]

    selector_logger.info(
        f'已完成打分：{question} -> {domains} \n-> {categories} \n-> {documents} \n-> {target_paragraphs}'
    )
    return target_paragraphs


@router.get('/meta_data/{kb_id}/{meta_type}')
def get_meta_data(kb_id: int, meta_type: str, session: SessionDep, token=Depends(verify_token)):
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
def update_kb_index(kb_id: int, session: SessionDep, token=Depends(verify_token)):
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
def upload_file(
        session: SessionDep,
        items: str = Form(...),
        files: List[UploadFile] = File(...),
        token=Depends(verify_token)
):
    message = ''
    count = 0

    try:
        items: list = json.loads(items)
        base_dir = os.path.abspath('./files')
        os.makedirs(base_dir, exist_ok=True)

        for i, file in enumerate(files):
            file_name = file.filename
            file_suffix = Path(file_name).suffix
            if file_suffix not in ['.doc', '.docx', '.pdf', '.png', '.jpeg', '.jpg']:
                # 预校验上传文件后缀
                message += f'\n{file_name}文件无法处理不支持格式，支持格式:[.doc, .docx, .pdf, .png, .jpeg, .jpg]'
                continue

            kb_id = items[i]['kb_id']
            strategy = items[i]['policy_type']
            is_strategy_repeat = check_file_strategy(file, session, kb_id, strategy)
            if is_strategy_repeat:
                # 预校验上传文件切割策略
                message += f'\n已存在重复切割策略文件:{file_name} 切割策略:{strategy}\n'
                items.pop(i)
                continue

            count += 1
            db_file, md5 = check_file_md5(file, session)
            if not db_file:
                # 预校验上传文件MD5
                parser_logger.info(f'正在上传文件:{file}')
                file_path = os.path.join(base_dir, file_name)
                with open(file_path, 'wb') as f:
                    shutil.copyfileobj(file.file, f)
                parser_logger.info(f'文件上传完毕:{file}')
            else:
                file_path = db_file.file_path
            task = ProcessingTask(**{
                'status': 'pending',
                'file_size': file.size,
                'file_path': file_path,
                'kb_id': kb_id,
                'file_md5': md5,
                'parse_strategy': strategy,
            })
            session.add(task)
            session.commit()
            session.refresh(task)  # 获取新创建任务的ID

            # 激活线程池立即处理
            task_trigger.set()
            parser_logger.info(f'任务 {task.task_id} 已加入处理队列')

    except Exception as e:
        session.rollback()
        parser_logger.error(f'{e}', exc_info=True)

    response_count = f'共{count}个文件成功解析' if count > 0 else ''
    return {'message': response_count + message}


@router.get('/files/{filename}')
def open_file(filename: str):
    file_path = os.path.join('files', filename)
    file_obj = Path(file_path)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail='文件不存在')

    # 支持的文件类型
    allowed_suffixes = ['.docx', '.doc', '.pdf', '.png', '.jpeg', '.jpg']
    if file_obj.suffix not in allowed_suffixes:
        raise HTTPException(status_code=400, detail='Unsupported file type')

    if file_obj.suffix == '.doc':
        filename = filename.replace('.doc', '.docx')
        file_path = os.path.join('files', filename)
        # 检查是否存在docx版本
        if not os.path.exists(file_path):
            convert_file_type(
                file_obj.absolute(),
                file_obj.parent.absolute(),
                'docx'
            )
        file_obj = Path(file_path)

    if file_obj.suffix == '.pdf':
        media_type = 'application/pdf'
    elif file_obj.suffix == '.png':
        media_type = 'image/png'
    elif file_obj.suffix in ['.jpg', '.jpeg']:
        media_type = 'image/jpeg'
    elif file_obj.suffix == '.docx':
        media_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'

    return FileResponse(
        file_path,
        media_type=media_type,
        filename=filename,
    )


@router.post('/knowledge_bases', response_model=KnowledgeBase)
def create_knowledge_bases(kb: KbBase, session: SessionDep, token=Depends(verify_token)):
    db_kb = KnowledgeBase.model_validate(kb)
    session.add(db_kb)
    session.commit()
    session.refresh(db_kb)
    return db_kb


@router.get('/knowledge_base/{kb_id}')
def query_knowledge_base(
        kb_id: int,
        session: SessionDep,
        token=Depends(verify_token)
) -> Page[dict]:
    know_base = session.get(KnowledgeBase, kb_id)
    if not know_base:
        raise HTTPException(status_code=404, detail="KnowledgeBase not found")

    documents = session.query(Document).filter(Document.kb_id == kb_id).all()
    documents = [doc.model_dump() for doc in documents]
    documents.sort(key=lambda x: x.get('meta_data', {}).get('最后更新时间', ''), reverse=True)
    # 获取处理中的任务
    all_tasks = session.query(ProcessingTask).filter(ProcessingTask.kb_id == kb_id).all()
    document_paths = {(document['file_path'], document['parse_strategy']) for document in documents}

    # 合并文档和任务
    for task in all_tasks:
        if task.status == 'filing':
            continue

        if (task.file_path, task.parse_strategy) not in document_paths:
            documents.insert(0, {
                'task': task.model_dump()  # 使用model_dump转换任务对象
            })
            document_paths.add((task.file_path, task.parse_strategy))

    disable_installed_extensions_check()
    return paginate(documents)


@router.get('/knowledge_bases', response_model=list[KnowledgeBase])
def query_knowledge_bases(
        session: SessionDep,
        offset: int = 0,
        limit: Annotated[int, Query(le=100)] = 100,
        token=Depends(verify_token)
):
    return session.exec(select(KnowledgeBase).offset(offset).limit(limit)).all()


@router.patch('/knowledge_base/{kb_id}', response_model=KbBase)
def update_knowledge_base(kb_id: int, kb: KbBase, session: SessionDep, token=Depends(verify_token)):
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
def delete_knowledge_base(kb_id: int, session: SessionDep, token=Depends(verify_token)):
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
    session.query(ProcessingTask).filter_by(kb_id=kb_id).delete()
    session.query(KnowledgeBase).filter_by(kb_id=kb_id).delete()
    session.commit()


@router.delete('/document/{document_id}')
def delete_document(document_id: str, session: SessionDep, token=Depends(verify_token)):
    document_id = uuid.UUID(document_id)
    session.query(Paragraph).filter_by(parent_id=document_id).delete()
    db_document = session.query(Document).filter_by(document_id=document_id).first()
    session.query(CategoryDocumentLink).filter_by(document_id=document_id).delete()
    tasks = session.query(ProcessingTask).filter_by(file_path=db_document.file_path,
                                                    parse_strategy=db_document.parse_strategy)
    for task in tasks:
        task.status = 'filing'
    # TODO 暂不同步调整category summary
    session.delete(db_document)
    session.add_all(tasks)
    session.commit()


@router.get('/paragraphs/{document_id}')
def query_paragraphs(document_id: str, session: SessionDep, token=Depends(verify_token)):
    """ 查询单个文档所有段落 """
    import re
    all_paragraphs = session.query(Paragraph).filter_by(parent_id=uuid.UUID(document_id)).all()
    if session.get(Document, uuid.UUID(document_id)).parse_strategy == 'page_split':
        all_paragraphs.sort(key=lambda x: int(re.findall(r'\d+', x.position)[0]))
    return all_paragraphs


@router.get('/paragraph/{paragraph_id}')
def query_paragraph(paragraph_id: str, session: SessionDep, token=Depends(verify_token)):
    """ 查询单个段落 """
    return session.query(Paragraph).get(uuid.UUID(paragraph_id))


@router.get('/documents/{category_id}')
def query_documents(category_id: str, session: SessionDep, token=Depends(verify_token)):
    """ 查询单个分类下所有文档 """
    document_ids = session.query(CategoryDocumentLink).filter_by(category_id=uuid.UUID(category_id)).all()
    document_ids = [document.document_id for document in document_ids]
    return session.query(Document).filter(Document.document_id.in_(document_ids)).all()


@router.get('/filter_documents')
def query_documents(
        document_name: str,
        session: SessionDep,
        token=Depends(verify_token)
) -> Page[Document]:
    """ 模糊筛选条件文档 """
    filter_condition = f"%{document_name}%"
    return sqlalchemy_paginate(session, select(Document).filter(Document.file_path.like(filter_condition)))


@router.get('/document/{document_id}')
def query_document(document_id: str, session: SessionDep, token=Depends(verify_token)):
    """ 查询单个文档"""
    return session.query(Document).get(uuid.UUID(document_id))


@router.get('/categories/{domain_id}')
def query_categories(domain_id: str, session: SessionDep, token=Depends(verify_token)):
    """ 查询单个领域下所有分类 """
    return session.query(Category).filter_by(parent_id=uuid.UUID(domain_id)).all()


@router.get('/category/{category_id}')
def query_category(category_id: str, session: SessionDep, token=Depends(verify_token)):
    """ 查询单个分类 """
    return session.query(Category).get(uuid.UUID(category_id))


@router.get('/domain/{domain_id}')
def query_domain(domain_id: str, session: SessionDep, token=Depends(verify_token)):
    """ 查询单个领域 """
    return session.query(Domain).get(uuid.UUID(domain_id))


@router.post('/token')
def login_for_access_token(
        session: SessionDep,
        password: str = Form(...),
        username: str = Form(...)
) -> Token:
    user = authenticate_user(session, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或者密码错误",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user.user_name}
    )
    fresh_token = create_refresh_token(
        data={"sub": user.user_name}
    )
    return Token(access_token=access_token, refresh_token=fresh_token, token_type='bearer')


@router.post('/refresh')
def login_refresh_token(refresh_token: str = Form(...)):
    access_token, fresh_token = refresh_access_token(refresh_token)
    return Token(access_token=access_token, refresh_token=fresh_token, token_type='bearer')


@router.get('/tasks')
def query_processing_tasks(kb_id: int, session: SessionDep, token=Depends(verify_token)):
    return session.query(ProcessingTask).filter(ProcessingTask.kb_id == kb_id).all()
