from typing import List
from pydantic import BaseModel


class Item(BaseModel):
    file_path: str
    policy_type: str
    kb_id: int


class FileInfo(BaseModel):
    items: List[Item]
