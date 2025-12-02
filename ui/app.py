"""
ui/app.py

ChatGPT-like Gradio UI for MAAG (Multi-Agent Analytics Gateway).

Features:
- Chat-style interface (query -> answer)
- Calls three backend APIs:
    POST /api/ask   -> natural language question pipeline
    POST /api/sql   -> run raw SQL
    GET  /api/health-> health/check
- Shows SQL, markdown answer, results table, execution time
- Download results as CSV
- Session id (keeps history while UI running)
- Settings panel (LLM provider, max tokens, safety toggle)
"""

import gradio as gr
import requests
import json
import pandas as pd
import uuid
import time
from datetime import datetime
from io import StringIO
from core.config import settings


API_BASE = "http://localhost:8000"
API_ASK = f"{API_BASE}/api/ask"
API_SQL = f"{API_BASE}/api/sql"
API_HEALTH = f"{API_BASE}/api/health"
DEFAULT_SESSION_ID = str(uuid.uuid4())

# -----------------------
# Helpers
# -----------------------
def call_health():
    try:
        r = requests.get(API_HEALTH, timeout=6)
        return r.json()
    except Exception as e:
        return {"status": "down", "error": str(e)}

def call_ask(question: str, session_id: str=None, settings_overrides: dict=None):
    """
    Call /api/ask with question.
    settings_overrides is optional dict to pass provider/model overrides (added to request body).
    """
    payload = {"question": question}
    if session_id:
        payload["session_id"] = session_id
    if settings_overrides:
        payload["settings"] = settings_overrides

    try:
        start = time.time()
        r = requests.post(API_ASK, json=payload, timeout=120)
        elapsed = round((time.time() - start) * 1000, 1)
        r.raise_for_status()
        data = r.json()
        data["_elapsed_ms"] = elapsed
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def call_sql(sql: str, session_id: str=None):
    payload = {"sql": sql}
    if session_id:
        payload["session_id"] = session_id

    try:
        start = time.time()
        r = requests.post(API_SQL, json=payload, timeout=120)
        elapsed = round((time.time() - start) * 1000, 1)
        r.raise_for_status()
        data = r.json()
        data["_elapsed_ms"] = elapsed
        return {"ok": True, "data": data}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def format_rows_to_md(rows):
    try:
        df = pd.DataFrame(rows)
        if df.empty:
            return "No rows returned.", df
        md = df.head(25).to_markdown(index=False)
        return md, df
    except Exception as e:
        return f"Could not format rows: {e}", pd.DataFrame()

def download_csv_from_rows(rows):
    df = pd.DataFrame(rows)
    bio = StringIO()
    df.to_csv(bio, index=False)
    bio.seek(0)
    return bio.getvalue()

# -----------------------
# UI FUNCTIONS
# -----------------------
def do_health_check():
    h = call_health()
    if "status" in h and h["status"] == "ok":
        return gr.update(value=f"OK — provider={h.get('llm_provider')} model={h.get('llm_model')}")
    return gr.update(value=f"Down: {h}")

def chat_submit(question, history, session_id, provider, model_name, max_tokens, safety_on):
    # prepare settings overrides for backend (optional)
    settings_overrides = {
        "LLM_PROVIDER": provider,
        "LLM_MODEL_NAME": model_name,
        "LLM_MAX_TOKENS": int(max_tokens),
        "ENABLE_TOKEN_SAFETY": bool(safety_on)
    }

    # append user message to chat history
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    history = history or []
    history.append({"role": "user", "content": question, "time": timestamp})

    # call backend ask
    resp = call_ask(question, session_id=session_id, settings_overrides=settings_overrides)

    if not resp["ok"]:
        err = resp.get("error", "Unknown error")
        history.append({"role": "system", "content": f"Error calling backend: {err}", "time": timestamp})
        return history, "", "", None, None, None, session_id

    data = resp["data"]
    # data should contain fields: answer, sql, rows, markdown, summary, execution_time_ms, validation
    answer = data.get("answer") or data.get("text") or "No answer returned."
    sql = data.get("sql")
    rows = data.get("rows", [])
    markdown = data.get("markdown") or (format_rows_to_md(rows)[0] if rows else "")
    elapsed = data.get("execution_time_ms", data.get("_elapsed_ms"))
    validation = data.get("validation", {})

    # Add assistant message to history
    history.append({"role": "assistant", "content": answer, "time": timestamp})

    # Generate display details
    table_md, df = format_rows_to_md(rows)
    token_info = data.get("token_usage") or data.get("tokens") or {}

    # return updated UI pieces:
    # chat history, sql box value, markdown output, dataframe (for gr.Dataframe), elapsed, token_info, session_id
    return history, (sql or ""), markdown or table_md, df.head(200).to_dict(orient="records") if not df.empty else [], elapsed, token_info, session_id

def run_sql_submit(sql_text, session_id):
    resp = call_sql(sql_text, session_id=session_id)
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    if not resp["ok"]:
        return "", f"Error: {resp.get('error')}", [], None
    data = resp["data"]
    # expected: rows, markdown, success, error
    rows = data.get("rows", [])
    md, df = format_rows_to_md(rows)
    elapsed = data.get("_elapsed_ms", data.get("execution_time_ms"))
    return md, f"Executed in {elapsed} ms", df.head(200).to_dict(orient="records"), session_id

def download_csv_handler(rows):
    csv_text = download_csv_from_rows(rows or [])
    return csv_text

# -----------------------
# Build Gradio UI
# -----------------------
with gr.Blocks(title="MAAG — Chat UI") as demo:
    # top row: health and session
    with gr.Row():
        gr.Markdown("## Multi-Agent Analytics Gateway (MAAG) — Chat UI")
        health_btn = gr.Button("Health Check", scale=1)
        health_out = gr.Textbox(label="Backend Health", interactive=False)

    with gr.Row():
        with gr.Column(scale=1):
            # left: history pane
            gr.Markdown("### Conversation")
            chat_history = gr.State(value=[])  # store as list of dicts
            session_id_state = gr.State(value=DEFAULT_SESSION_ID)

            history_box = gr.Chatbot(elem_id="chatbot", label="MAAG Chat")
            # input controls
            user_input = gr.Textbox(label="Ask a question", placeholder="e.g. Find total SKU MEN5004-KR-L", lines=2)
            submit_btn = gr.Button("Send")

            with gr.Row():
                clear_btn = gr.Button("Clear")
                download_history_btn = gr.Button("Download History (JSON)")

            # settings collapsible
            with gr.Accordion("Settings (LLM & Safety)", open=False):
                provider_dropdown = gr.Dropdown(choices=["openai", "gemini", "ollama"], value="openai", label="LLM Provider")
                model_input = gr.Textbox(label="Model Name", value="", placeholder="Leave blank to use default from backend")
                max_tokens_input = gr.Number(label="LLM max tokens", value=1024, precision=0)
                safety_checkbox = gr.Checkbox(label="Enable token safety", value=True)

        with gr.Column(scale=1):
            # right: details and SQL
            gr.Markdown("### SQL & Results")
            sql_box = gr.Textbox(label="Generated SQL", lines=4)
            run_sql_button = gr.Button("Run SQL (raw)")
            sql_run_output = gr.Textbox(label="SQL Execution Status", interactive=False)
            result_table = gr.Dataframe(headers=["results"], datatype=["str"], interactive=False)
            download_csv_btn = gr.Button("Download Results CSV")

            gr.Markdown("### Assistant Output (Markdown)")
            assistant_md = gr.Markdown("", elem_id="assistant_md")

            gr.Markdown("### Diagnostics")
            diag_box = gr.JSON(value={})

    # -----------------------
    # Events wiring
    # -----------------------
    def clear_history(history, session_id):
        new_session = str(uuid.uuid4())
        return [], gr.update(value=None), [], new_session

    def download_history(history):
        return json.dumps(history, indent=2)

    # health check binding
    health_btn.click(fn=do_health_check, inputs=None, outputs=health_out)

    # submit chat
    submit_btn.click(
        fn=chat_submit,
        inputs=[user_input, chat_history, session_id_state, provider_dropdown, model_input, max_tokens_input, safety_checkbox],
        outputs=[chat_history, sql_box, assistant_md, result_table, diag_box, gr.State(), session_id_state],
        queue=True
    )

    # clear button
    clear_btn.click(fn=clear_history, inputs=[chat_history, session_id_state], outputs=[chat_history, sql_box, result_table, session_id_state])

    # download history
    download_history_btn.click(fn=download_history, inputs=[chat_history], outputs=[gr.File()])

    # run raw SQL
    run_sql_button.click(fn=run_sql_submit, inputs=[sql_box, session_id_state], outputs=[assistant_md, sql_run_output, result_table, session_id_state])

    # download csv of last shown result table
    download_csv_btn.click(fn=download_csv_handler, inputs=[result_table], outputs=[gr.File()])

    # initial health check display on load
    demo.load(fn=do_health_check, inputs=None, outputs=health_out)

# Launch the UI
if __name__ == "__main__":
    
    GRADIO_HOST = settings.GRADIO_HOST
    GRADIO_PORT = int(settings.GRADIO_PORT) if settings.GRADIO_PORT.isdigit() else 7860
    demo.launch(server_name=GRADIO_HOST, server_port=GRADIO_PORT, share=False)
