from pydantic import BaseModel

class SQLRequest(BaseModel):
    sql: str
