from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, conint, confloat, validator


# ---------------------------------------------------------------------------
# ★ 1.  Pydantic 数据模型
# ---------------------------------------------------------------------------

class RetrievalSetting(BaseModel):
    top_k: conint(ge=1) = Field(..., description="最大返回条数")
    score_threshold: confloat(ge=0, le=1) = Field(..., description="相关性阈值，0~1")


class LogicalOperator(str, Enum):
    and_ = "and"
    or_ = "or"


class ComparisonOperator(str, Enum):
    # 字符串类
    contains = "contains"
    not_contains = "not contains"
    start_with = "start with"
    end_with = "end with"
    is_ = "is"
    is_not = "is not"
    empty = "empty"
    not_empty = "not empty"
    null = "null"
    not_null = "not null"

    # 通用比较符
    eq = "="  # 等价于 is
    ne = "≠"  # 或 "!="
    gt = ">"
    lt = "<"
    ge = "≥"
    le = "≤"

    # 日期比较
    before = "before"
    after = "after"


class Condition(BaseModel):
    name: List[str]
    comparison_operator: ComparisonOperator
    value: Optional[str] = None

    @validator("value", always=True)
    def _check_value(cls, v, values):
        op = values.get("comparison_operator")
        no_value_needed = {
            ComparisonOperator.empty,
            ComparisonOperator.not_empty,
            ComparisonOperator.null,
            ComparisonOperator.not_null,
        }
        if op in no_value_needed:
            return v
        if v is None:
            raise ValueError(f"value is required for comparison_operator [{op}]")
        return v


class MetadataCondition(BaseModel):
    logical_operator: LogicalOperator = LogicalOperator.and_
    conditions: List[Condition]


class RetrievalRequest(BaseModel):
    knowledge_id: str
    query: str
    retrieval_setting: RetrievalSetting
    metadata_condition: Optional[MetadataCondition] = None


# ---------- 响应 ---------- #
class Record(BaseModel):
    content: str
    score: float
    title: str
    metadata: Optional[Dict[str, Any]] = None


class RetrievalResponse(BaseModel):
    records: List[Record]


# ---------- 异常响应 ---------- #
class APIError(BaseModel):
    error_code: int
    error_msg: str
