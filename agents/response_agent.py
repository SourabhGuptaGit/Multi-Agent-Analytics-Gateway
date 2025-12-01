# agents/response_agent.py

from core.utils import logger
from core.config import settings
from core.llm import call_llm  # uses the unified llm selector


class ResponseAgent:
    """
    Converts SQL execution results into a natural-language answer.
    Uses the selected LLM provider to produce a final user-facing response.
    """

    def build_prompt(self, user_question, sql, formatted, rows):
        """
        Builds detailed but safe LLM prompt using:
        - Original question
        - Generated SQL
        - SQL execution summary
        - JSON rows
        - Markdown preview (LLM-readable)
        """

        markdown = formatted.get("markdown", "")
        json_rows = formatted.get("json", [])
        summary = formatted.get("text", "")

        prompt = f"""
        You are an expert data analyst. The system has already generated SQL, executed it, 
        and obtained clean results from DuckDB.

        Your task:
        - Provide a clear, factual, concise natural-language answer to the user.
        - Do NOT hallucinate.
        - Base everything strictly on the SQL results provided.
        - If results are empty, politely say no rows were found.

        ------------------------
        USER QUESTION:
        {user_question}

        ------------------------
        SQL USED:
        {sql}

        ------------------------
        RESULT SUMMARY:
        {summary}

        ------------------------
        RESULT ROWS (JSON):
        {json_rows}

        ------------------------
        RESULT TABLE (Markdown):
        {markdown}

        ------------------------
        Now produce the final answer in plain English.
        """
        return prompt.strip()

    # ---------------------------------------------------------------------
    def generate_answer(self, user_question, sql, formatted, rows):
        """
        Calls the LLM using the built prompt and returns natural language answer.
        """
        logger.info("Response Agent generating final answer...")

        prompt = self.build_prompt(user_question, sql, formatted, rows)

        answer = call_llm(prompt)

        logger.success("Final natural-language answer generated.")
        return answer.strip()
