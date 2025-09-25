"""
@Project ：core 
@File    ：views.py
@IDE     ：PyCharm 
@Author  ：XMAN
@Date    ：2025/6/9 上午10:08 
"""
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, List, Dict, Any

from jwt import encode, decode
from fastapi import Depends, HTTPException, status, UploadFile
from fastapi.security import OAuth2PasswordBearer
from jwt.exceptions import InvalidTokenError, ExpiredSignatureError
from passlib.context import CryptContext
from sqlmodel import select

from db.database import SessionDep
from llm.llmchat import LlmChat
from web_server.ai.models import User, ProcessingTask, Document
from web_server.ai.schemas import UserTokenConfig, TokenData

from selector.base import SelectorParam
from selector.class_selector import CategorySelector
from selector.document_selector import DocumentSelector
from selector.domain_selector import DomainSelector
from selector.paragraph_selector import ParagraphSelector
from tools.result_scoring import ResultScoringParser
from tools.log_tools import selector_logger

SCORING_WORKERS = int(os.getenv("SCORING_WORKERS", "64"))
SCORING_POOL = ThreadPoolExecutor(max_workers=SCORING_WORKERS)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/ai/token")


def verify_token(token: str = Depends(oauth2_scheme)):
    """验证token并检查过期时间"""
    api_keys = set(os.getenv('VALID_API_KEYS').split(','))
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode(token, UserTokenConfig.get_secret_key(), algorithms=[UserTokenConfig.ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        return TokenData(username=username)
    except ExpiredSignatureError:
        pass
    except InvalidTokenError:
        pass

    if token in api_keys:
        return

    raise credentials_exception


def refresh_access_token(token: str):
    """ 自动续签token """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="无效的认证凭据",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode(token, UserTokenConfig.get_secret_key(), algorithms=[UserTokenConfig.ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        data = {'sub': username}
        # 置换新token
        return create_access_token(data), create_refresh_token(data)
    except ExpiredSignatureError:
        pass
    except InvalidTokenError:
        pass

    raise credentials_exception


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_pwd_hash(pwd):
    return pwd_context.hash(pwd)


def get_user(db, username: str):
    return db.query(User).filter(User.user_name == username).first()


def authenticate_user(db: SessionDep, username: str, password: str):
    user = get_user(db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict):
    expires_delta = timedelta(minutes=UserTokenConfig.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = encode(to_encode, UserTokenConfig.get_secret_key(), algorithm=UserTokenConfig.ALGORITHM)
    return encoded_jwt


def create_refresh_token(data: dict):
    refresh_expires_delta = timedelta(minutes=UserTokenConfig.REFRESH_TOKEN_EXPIRE_MINUTES)
    to_encode = data.copy()
    if refresh_expires_delta:
        expire = datetime.now(timezone.utc) + refresh_expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = encode(to_encode, UserTokenConfig.get_secret_key(), algorithm=UserTokenConfig.ALGORITHM)
    return encoded_jwt


def get_current_user(db: SessionDep, token: Annotated[str, Depends(oauth2_scheme)]):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = decode(token, UserTokenConfig.get_secret_key(), algorithms=[UserTokenConfig.ALGORITHM])
        username = payload.get("sub")
        if username is None:
            raise credentials_exception
        token_data = TokenData(username=username)
    except InvalidTokenError:
        raise credentials_exception
    user = get_user(db, username=token_data.username)
    if user is None:
        raise credentials_exception
    return user


def check_file_md5(file: UploadFile, session: SessionDep, chunk_size: int = 8192) -> tuple[ProcessingTask, str]:
    """计算上传文件的 MD5 哈希值"""
    import hashlib
    md5 = hashlib.md5()
    file.file.seek(0)
    while chunk := file.file.read(chunk_size):
        md5.update(chunk)
    file.file.seek(0)
    file_md5 = md5.hexdigest()
    query = session.query(ProcessingTask).filter_by(file_size=file.size, file_md5=file_md5)
    db_file = query.first()
    return db_file, file_md5


def check_file_strategy(file: UploadFile, session: SessionDep, kb_id: int, strategy: str):
    """ 校验上传文件的 策略重复性"""
    filename = file.filename
    # 相同文件相同切割策略不允许上传
    statement = select(Document).where(
        Document.file_path.like(f"%{filename}%"),
        Document.parse_strategy == strategy,
        Document.kb_id == kb_id
    )
    db_strategies = session.exec(statement).all()
    statement = select(ProcessingTask).where(
        ProcessingTask.file_path.like(f"%{filename}%"),
        ProcessingTask.parse_strategy == strategy,
        ProcessingTask.kb_id == kb_id,
        ProcessingTask.status != 'filing'
    )
    db_tasks = session.exec(statement).all()
    return len(db_strategies) > 0 or len(db_tasks) > 0


def full_volume_recall(params: SelectorParam, has_score, score_threshold) -> List[dict]:
    """ 非流式 全量召回 """
    question = params.question
    llm_chat = params.llm
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

    # 只要 has_score=True 且阈值未指定或 >=0 就进行评分
    do_scoring = has_score and (score_threshold is None or score_threshold >= 0)
    if not do_scoring:
        return target_paragraphs

    selector_logger.info(
        f'选择完成正在打分：{question} -> {domains} \n-> {categories} \n-> {documents} \n-> {target_paragraphs}')

    recall_content = [f"{par.get('parent_description', '')}{par.get('content', '')}" for par in target_paragraphs]
    if not recall_content:
        return []

    scorer_agent = ResultScoringParser(llm_chat)

    # 单个评分任务在线程里执行，避免阻塞当前线程
    def _score_one(idx: int, par_text: str):
        score = scorer_agent.rate(question, par_text)  # 同步函数，放在线程执行
        context_relevance = Decimal(str(score.get("A", 0) or 0))
        context_sufficiency = Decimal(str(score.get("B", 0) or 0))
        context_clarity = Decimal(str(score.get("C", 0) or 0))
        reliability = Decimal(str(score.get("D", 0) or 0))
        total = context_relevance + context_sufficiency + context_clarity + reliability
        return idx, {
            "context_relevance": float(context_relevance),
            "context_sufficiency": float(context_sufficiency),
            "context_clarity": float(context_clarity),
            "reliability": float(reliability),
            "total_score": float(total),
            "diagnosis": score.get("E", ""),
        }

    # 提交并发评分任务
    futures = [
        SCORING_POOL.submit(_score_one, i, txt)
        for i, txt in enumerate(recall_content)
    ]

    # 回填评分结果
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


def streaming_recall(params: SelectorParam, has_score, score_threshold):
    """ 分阶段流式召回：领域→分类→文档→段落，包含各阶段耗时统计 """
    question = params.question
    llm_chat = params.llm
    # 初始化各阶段耗时记录
    timings = {
        "domain": 0.0,
        "category": 0.0,
        "document": 0.0,
        "paragraph": 0.0,
        "total": 0.0
    }
    # 记录总开始时间
    total_start_time = time.time()

    try:
        # 领域选择计时
        domain_start_time = time.time()
        selected_domains, domains = DomainSelector(params).collate_select_params().start_select()
        domain_end_time = time.time()
        timings["domain"] = round(domain_end_time - domain_start_time, 2)

        selector_logger.info(f"[{question}] 领域选择结果: {domains}, 耗时: {timings['domain']}秒")
        # 推送领域阶段事件，包含耗时
        yield generate_sse_event(
            stage="domain",
            data={
                "selected_domains": domains,
                "count": len(domains),
                "elapsed_time": timings["domain"]  # 本阶段耗时
            },
            message=f"领域选择完成，共选中 {len(domains)} 个领域，耗时 {timings['domain']:.2f} 秒"
        )
    except Exception as e:
        yield generate_sse_event(stage="error", data={"error": str(e)}, message=f"领域选择失败：{str(e)}")
        return

    try:
        # 分类选择计时
        category_start_time = time.time()
        selected_categories, categories = CategorySelector(params).collate_select_params(
            selected_domains).start_select()
        category_end_time = time.time()
        timings["category"] = round(category_end_time - category_start_time, 2)

        selector_logger.info(f"[{question}] 分类选择结果: {categories}, 耗时: {timings['category']}秒")
        # 推送分类阶段事件，包含耗时
        yield generate_sse_event(
            stage="category",
            data={
                "selected_categories": categories,
                "count": len(categories),
                "elapsed_time": timings["category"],  # 本阶段耗时
                "cumulative_time": round(timings["domain"] + timings["category"], 2)  # 累计耗时
            },
            message=f"分类选择完成，共选中 {len(categories)} 个分类，耗时 {timings['category']:.2f} 秒，累计 {timings['domain'] + timings['category']:.2f} 秒"
        )
    except Exception as e:
        yield generate_sse_event(stage="error", data={"error": str(e)}, message=f"分类选择失败：{str(e)}")
        return

    try:
        # 文档选择计时
        document_start_time = time.time()
        selected_documents, documents = DocumentSelector(params).collate_select_params(
            selected_categories).start_select()
        document_end_time = time.time()
        timings["document"] = round(document_end_time - document_start_time, 2)

        selector_logger.info(f"[{question}] 文档选择结果: {documents}, 耗时: {timings['document']}秒")
        # 推送文档阶段事件，包含耗时
        yield generate_sse_event(
            stage="document",
            data={
                "selected_documents": documents,
                "count": len(documents),
                "elapsed_time": timings["document"],  # 本阶段耗时
                "cumulative_time": round(timings["domain"] + timings["category"] + timings["document"], 2)  # 累计耗时
            },
            message=f"文档选择完成，共选中 {len(documents)} 个文档，耗时 {timings['document']:.2f} 秒，累计 {sum(timings.values()) - timings['total']:.2f} 秒"
        )
    except Exception as e:
        yield generate_sse_event(stage="error", data={"error": str(e)}, message=f"文档选择失败：{str(e)}")
        return

    # 无文档需要直接终止流式召回
    if not selected_documents:
        total_end_time = time.time()
        timings["total"] = round(total_end_time - total_start_time, 2)
        yield generate_sse_event(
            stage="complete",
            data={
                "reason": "无匹配文档",
                "timings": timings  # 返回所有计时信息
            },
            message=f"无匹配文档，召回结束，总耗时 {timings['total']:.2f} 秒"
        )
        return

    try:
        # 段落选择计时
        paragraph_start_time = time.time()
        target_paragraphs = ParagraphSelector(params).collate_select_params(
            selected_documents).start_select().collate_select_result()

        do_scoring = has_score and (score_threshold is None or score_threshold >= 0)
        if do_scoring and target_paragraphs:
            # 开始并发评分
            recall_content = [f"{par.get('parent_description', '')}{par.get('content', '')}" for par in
                              target_paragraphs]
            scorer_agent = ResultScoringParser(llm_chat)

            def _score_one(idx: int, par_text: str):
                score = scorer_agent.rate(question, par_text)  # 同步函数，放在线程执行
                context_relevance = Decimal(str(score.get("A", 0) or 0))
                context_sufficiency = Decimal(str(score.get("B", 0) or 0))
                context_clarity = Decimal(str(score.get("C", 0) or 0))
                reliability = Decimal(str(score.get("D", 0) or 0))
                total = context_relevance + context_sufficiency + context_clarity + reliability
                return idx, {
                    "context_relevance": float(context_relevance),
                    "context_sufficiency": float(context_sufficiency),
                    "context_clarity": float(context_clarity),
                    "reliability": float(reliability),
                    "total_score": float(total),
                    "diagnosis": score.get("E", ""),
                }

            futures = [
                SCORING_POOL.submit(_score_one, i, txt)
                for i, txt in enumerate(recall_content)
            ]
            for fut in as_completed(futures):
                idx, updates = fut.result()
                target_paragraphs[idx].update(updates)

            # 排序+阈值过滤
            target_paragraphs.sort(key=lambda x: x.get("total_score", 0.0), reverse=True)
            if score_threshold is not None:
                target_paragraphs = [x for x in target_paragraphs if x.get("total_score", 0.0) >= score_threshold]

        # 计算段落阶段耗时（包括评分）
        paragraph_end_time = time.time()
        timings["paragraph"] = round(paragraph_end_time - paragraph_start_time, 2)

        # 计算总耗时
        total_end_time = time.time()
        timings["total"] = round(total_end_time - total_start_time, 2)

        for paragraph in target_paragraphs:
            paragraph['paragraph_id'] = paragraph['paragraph_id'].__str__()
            paragraph['parent_id'] = paragraph['parent_id'].__str__()

        # 推送段落阶段事件，包含本阶段耗时和总耗时
        yield generate_sse_event(
            stage="paragraph",
            data={
                "target_paragraphs": target_paragraphs,
                "count": len(target_paragraphs),
                "elapsed_time": timings["paragraph"],  # 本阶段耗时
                "cumulative_time": timings["total"],  # 总耗时
                "timings": timings  # 所有阶段的耗时详情
            },
            message=f"段落召回完成，共获取 {len(target_paragraphs)} 个相关段落，本阶段耗时 {timings['paragraph']:.2f} 秒，总耗时 {timings['total']:.2f} 秒"
        )
    except Exception as e:
        print(str(e))
        yield generate_sse_event(stage="error", data={"error": str(e)}, message=f"段落召回失败：{str(e)}")
        return

    yield generate_sse_event(
        stage="complete",
        data={
            "reason": "全阶段完成",
            "timings": timings  # 返回所有计时信息
        },
        message=f"流式召回已全部完成，总耗时 {timings['total']:.2f} 秒"
    )


def generate_sse_event(stage: str, data: Dict[str, Any], message: str) -> str:
    """ 生成SSE事件格式的字符串，包含阶段、数据和消息 """
    event_data = json.dumps({
        'stage': stage,
        'data': data,
        'message': message
    })
    return f'data: {event_data}\n\n'
