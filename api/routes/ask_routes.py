from fastapi import APIRouter
from api.models.ask import AskRequest
from agents.controller import Orchestrator

router = APIRouter()
orchestrator = Orchestrator()

@router.post("/ask")
def ask_question(req: AskRequest):
    result = orchestrator.run_pipeline(req.question)

    return {
        "question": result["question"],
        "answer": result["answer"],
        "sql": result["sql"],
        "rows": result["rows"],
        "markdown": result["markdown"],
        "summary": result["summary"],
        "validation": result["validation"],
        "execution_time_ms": result["execution_time_ms"]
    }
