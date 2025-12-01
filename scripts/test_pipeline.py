from agents.controller import Orchestrator
from core.utils import save_json


if __name__ == "__main__":
    orchestrator = Orchestrator()
    question = "Find Total SKU with value 'MEN5004-KR-L'"
    result = orchestrator.run_pipeline(question)

    print("\n----- FINAL RESPONSE -----")
    print("Answer:", result["answer"])
    print("SQL:", result["sql"])
    print("Result Rows:", result["rows"])
    
    save_json(result, "result.json")