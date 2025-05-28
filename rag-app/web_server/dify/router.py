import os
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, Depends, Header, HTTPException, status
from db.database import SessionDep
from web_server.ai.models import KnowledgeBase
from web_server.ai.router import query_with_llm
from web_server.dify.schemas import ComparisonOperator, MetadataCondition, LogicalOperator, RetrievalResponse, APIError, \
    RetrievalRequest, Record, Condition
load_dotenv()
router = APIRouter(tags=['dify'], prefix='/dify')

# ---------------------------------------------------------------------------
# ★ 2.  鉴权依赖（Bearer <token>）
# ---------------------------------------------------------------------------

VALID_API_KEYS = {str(os.getenv('VALID_API_KEYS', default=""))}

print(VALID_API_KEYS)

async def verify_api_key(
        authorization: str = Header(..., alias="Authorization")
):
    """
    解析并验证 Bearer Token
    """
    prefix = "Bearer "
    if not authorization.startswith(prefix):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=APIError(error_code=1001,
                            error_msg="无效的 Authorization 头格式。预期格式为 Bearer <api-key>").dict(),
        )
    token = authorization[len(prefix):]
    if token not in VALID_API_KEYS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=APIError(error_code=1002, error_msg="授权失败").dict(),
        )
    return token


# ---------------------------------------------------------------------------
# ★ 3.  metadata 条件过滤工具
# ---------------------------------------------------------------------------

from dateutil import parser as dt_parser  # pip install python-dateutil
from decimal import Decimal, InvalidOperation


def _to_number(val: str):
    """尝试把字符串转成数字；失败则返回 None"""
    try:
        return Decimal(val.replace(",", ""))  # 兼容千分位
    except (InvalidOperation, AttributeError):
        return None


def _to_datetime(val: str):
    """尝试将字符串解析为 datetime；失败返回 None"""
    try:
        return dt_parser.parse(val)
    except (ValueError, TypeError):
        return None


def _match_condition(meta: Dict[str, Any], cond: Condition) -> bool:
    """
    判断 meta 是否满足 cond
    - 支持所有字符串、数值、日期运算
    - 如果同一个 Condition.name 里列出多个字段，只要 *有一个字段* 命中则算通过
    """
    op = cond.comparison_operator
    cmp_val_raw = cond.value

    # 预处理：把待比较值预解析为数字 / 日期，方便后面比较
    cmp_num = _to_number(cmp_val_raw) if cmp_val_raw is not None else None
    cmp_dt = _to_datetime(cmp_val_raw) if cmp_val_raw is not None else None

    for field in cond.name:
        v = meta.get(field)

        # 统一为 str 参与字符串比较
        v_str = "" if v is None else str(v)

        # ---------------- 空值 / NULL ---------------- #
        if op in {ComparisonOperator.null, ComparisonOperator.not_null}:
            is_null = v is None
            return is_null if op == ComparisonOperator.null else not is_null

        # ---------------- 空字符串 ---------------- #
        if op in {ComparisonOperator.empty, ComparisonOperator.not_empty}:
            is_empty = (v_str.strip() == "")
            return is_empty if op == ComparisonOperator.empty else not is_empty

        # ---------------- 字符串匹配 ---------------- #
        if op == ComparisonOperator.contains:
            if cmp_val_raw in v_str:
                return True
        elif op == ComparisonOperator.not_contains:
            if cmp_val_raw not in v_str:
                return True
        elif op == ComparisonOperator.start_with:
            if v_str.startswith(cmp_val_raw):
                return True
        elif op == ComparisonOperator.end_with:
            if v_str.endswith(cmp_val_raw):
                return True
        elif op in {ComparisonOperator.is_, ComparisonOperator.eq}:
            if v_str == cmp_val_raw:
                return True
        elif op in {ComparisonOperator.is_not, ComparisonOperator.ne}:
            if v_str != cmp_val_raw:
                return True

        # ---------------- 数值比较 ---------------- #
        num_v = _to_number(v_str)
        if num_v is not None and cmp_num is not None:
            if op == ComparisonOperator.gt and num_v > cmp_num:
                return True
            if op == ComparisonOperator.lt and num_v < cmp_num:
                return True
            if op == ComparisonOperator.ge and num_v >= cmp_num:
                return True
            if op == ComparisonOperator.le and num_v <= cmp_num:
                return True

        # ---------------- 日期比较 ---------------- #
        dt_v = _to_datetime(v_str)
        if dt_v is not None and cmp_dt is not None:
            if op == ComparisonOperator.before and dt_v < cmp_dt:
                return True
            if op == ComparisonOperator.after and dt_v > cmp_dt:
                return True

    return False


def filter_by_metadata(
        records: List[Dict[str, Any]],
        meta_cond: Optional[MetadataCondition],
) -> List[Dict[str, Any]]:
    if meta_cond is None:
        return records

    filtered = []
    for rec in records:
        meta_ok_list = [
            _match_condition(rec.get("metadata", {}), c)
            for c in meta_cond.conditions
        ]
        ok = all(meta_ok_list) if meta_cond.logical_operator == LogicalOperator.and_ else any(meta_ok_list)
        if ok:
            filtered.append(rec)
    return filtered


# ---------------------------------------------------------------------------
# ★ 4.  内部业务依赖 —— 你现成的召回流水线
# ---------------------------------------------------------------------------

async def inner_recall(kb_id: int, question: str, session: SessionDep) -> List[Dict[str, Any]]:
    """
    调用你的 query_with_llm，并把 total_score 归一化到 0~1
    """
    raw = await query_with_llm(kb_id=kb_id, session=session, question=question)
    print(raw)
    if not raw:
        return []

    # 你的 total_score = relevance+sufficiency+clarity ∈ [0,1]（1*3）
    max_score = 3
    for r in raw:
        r["score"] = round(float(r["total_score"]) / max_score, 4)
        r.setdefault("title", r.get("document_title", ""))  # 没标题就补空
        r.setdefault("metadata", {})
    return raw


# ---------------------------------------------------------------------------
# ★ 5.  /retrieval 端点
# ---------------------------------------------------------------------------

@router.post(
    "/retrieval",
    response_model=RetrievalResponse,
    responses={
        401: {"model": APIError},
        403: {"model": APIError},
        404: {"model": APIError},
        500: {"model": APIError},
    },
)
async def dify_retrieval(
        session: SessionDep,
        req: RetrievalRequest,
        _: str = Depends(verify_api_key)
):
    try:
        kb_pk = int(req.knowledge_id)  # 请求是字符串，转 int
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=APIError(error_code=2001, error_msg="知识库不存在").dict(),
        )

    kb_row = session.get(KnowledgeBase, kb_pk)  # 等同 SELECT ... WHERE pk = :id
    if kb_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=APIError(error_code=2001, error_msg="知识库不存在").dict(),
        )

    kb_id = kb_row.kb_id  # 后续 inner_recall 用

    # 2) 执行召回链
    try:
        paragraphs = await inner_recall(kb_id, req.query, session=session)

    except Exception as exc:
        # 兜底 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=APIError(error_code=5000, error_msg=f"内部错误: {exc}").dict(),
        )



    # 3) 阈值过滤、metadata 过滤
    paragraphs = [
        p for p in paragraphs if p["score"] >= req.retrieval_setting.score_threshold
    ]
    paragraphs = filter_by_metadata(paragraphs, req.metadata_condition)

    # ------------------------------------------------------------
    # 4) 整形为 Dify Records  + 归一化 score
    # ------------------------------------------------------------
    def to_records(raw: List[dict]) -> List[Record]:
        """
        将内部段落对象映射到 Dify Record
        - total_score ∈ [0,3] → score ∈ [0,1]
        - title：优先 paragraph_name，其次 parent_description，其次空串
        - metadata：保留你需要透出的字段（可自行裁剪）
        """

        records: List[Record] = []
        for p in raw:
            # -------- 归一化得分 -------- #
            score = p["score"]             # 已是 0~1 范围

            # -------- Title 逻辑 -------- #
            title = p.get("paragraph_name") or p.get("parent_description", "")[:30]

            # -------- Metadata -------- #
            meta = {
                "paragraph_id": p.get("paragraph_id"),
                "parent_id": p.get("parent_id"),
                "position": p.get("position"),
                "keywords": p.get("keywords"),
                "summary": p.get("summary"),
                "diagnosis": p.get("diagnosis"),
                # 直接转发你原来的 meta_data
                **(p.get("meta_data") or {})
            }

            # 生成 Record
            records.append(
                Record(
                    content=p.get("content", ""),
                    score=score,
                    title=title,
                    metadata=meta,
                )
            )

        return records

    # 5) 整形 & top-k
    paragraphs.sort(key=lambda x: x["total_score"], reverse=True)
    top_raw = paragraphs[: req.retrieval_setting.top_k]
    records = to_records(top_raw)

    return RetrievalResponse(records=records)