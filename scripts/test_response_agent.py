from agents.response_agent import ResponseAgent
from core.sql_executor import SQLExecutor
from agents.nl_to_sql_agent import generate_sql_from_question
from agents.validation_agent import validate_and_fix_sql
from core.rag import build_prompt_context

def test_flow():
    question = "Find Total SKU with value 'MEN5004-KR-L'"

    # Step 1: RAG
    rag, schema = build_prompt_context(question)

    # Step 2: NL→SQL
    sql, schema_struct = generate_sql_from_question(rag)

    # Step 3: Validate SQL
    result = validate_and_fix_sql(sql=sql, schema_struct=schema, auto_fix=True)
    
    # Step 4: Execute SQL
    executor = SQLExecutor()
    exec_result = executor.run_sql(result["sql"])
    formatted = executor.format_results(exec_result["df"])

    # Step 5: Response Agent
    agent = ResponseAgent()
    final_ans = agent.generate_answer(
        question,
        result["sql"],
        formatted,
        exec_result["rows"]
    )

    print("\nFINAL ANSWER:")
    print(final_ans)

if __name__ == "__main__":
    test_flow()
