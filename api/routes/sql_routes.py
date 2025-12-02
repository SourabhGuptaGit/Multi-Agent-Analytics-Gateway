from fastapi import APIRouter
from api.models.sql import SQLRequest
from core.sql_executor import SQLExecutor

router = APIRouter()
executor = SQLExecutor()

@router.post("/sql")
def run_sql(req: SQLRequest):
    res = executor.run_sql(req.sql)
    formatted = executor.format_results(res["df"])

    return {
        "success": res["success"],
        "sql": res["sql"],
        "rows": res["rows"],
        "markdown": formatted["markdown"],
        "error": res["error"]
    }
