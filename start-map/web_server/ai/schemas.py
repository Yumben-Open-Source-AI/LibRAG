from sqlmodel import Field, SQLModel


class KbBase(SQLModel):
    kd_name: str = Field(default='')
    kd_description: str | None = Field(default='')
    keywords: str | None = Field(default='')


class KnowledgeBase(KbBase, table=True):
    __tablename__ = "knowledge_base"

    kd_id: int | None = Field(default=None, primary_key=True)
