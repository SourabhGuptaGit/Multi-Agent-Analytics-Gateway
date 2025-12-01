from core.rag import build_prompt_context
from agents.nl_to_sql_agent import generate_sql_from_question
from agents.validation_agent import validate_and_fix_sql
from core.sql_executor import SQLExecutor
from agents.response_agent import ResponseAgent
from core.utils import logger


class Orchestrator:

    def __init__(self):
        self.executor = SQLExecutor()
        self.responder = ResponseAgent()

    def run_pipeline(self, question: str) -> dict:
        """
        Full end-to-end pipeline:
            NL question → RAG → NL2SQL → validation → execution → answer
        Returns structured dict for API/UI.
        """

        logger.info(f"Starting pipeline for question: {question}")

        # 1. Retrieve metadata context from FAISS + schema json
        rag_context, schema = build_prompt_context(question)

        # 2. NL → SQL
        sql, schema_struct = generate_sql_from_question(rag_context)
        logger.success(f"Generated SQL:\n{sql}")

        # 3. Validate + Fix SQL
        validation = validate_and_fix_sql(sql=sql, schema_struct=schema, auto_fix=True)
        final_sql = validation["sql"]

        logger.success(f"Validated / Final SQL:\n{final_sql}")

        # 4. Execute SQL on DuckDB
        exec_result = self.executor.run_sql(final_sql)

        # 5. Format results
        formatted = self.executor.format_results(exec_result["df"])

        # 6. Natural language answer
        final_answer = self.responder.generate_answer(
            user_question=question,
            sql=final_sql,
            formatted=formatted,
            rows=exec_result["rows"]
        )

        logger.success("Pipeline completed successfully.")

        # 7. Full structured return object
        return {
            "question": question,
            "sql": final_sql,
            "answer": final_answer,
            "rows": exec_result["rows"],
            "markdown": formatted["markdown"],
            "json": formatted["json"],
            "summary": formatted["text"],
            "execution_time_ms": exec_result["execution_time_ms"],
            "validation": validation,
        }
