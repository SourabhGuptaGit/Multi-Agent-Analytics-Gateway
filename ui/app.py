import gradio as gr
import requests
import json

API_URL = "http://localhost:8000/api/ask"   # FastAPI backend

# --------------- API CALL WRAPPER -------------------
def ask_backend(question):
    try:
        payload = {"question": question}

        response = requests.post(API_URL, json=payload, timeout=100)
        response.raise_for_status()
        data = response.json()

        final_answer = data.get("answer", "No answer generated.")
        sql_query = data.get("sql", "N/A")
        rows = data.get("rows", [])
        elapsed = data.get("elapsed_ms", None)

        formatted_rows = json.dumps(rows, indent=2)

        debug_block = (
            f"🧠 **Generated SQL:**\n```\n{sql_query}\n```\n\n"
            f"📊 **Rows Returned:**\n```\n{formatted_rows}\n```\n\n"
        )

        if elapsed is not None:
            debug_block += f"⏱️ *Execution Time:* {elapsed} ms"

        return final_answer, debug_block

    except Exception as e:
        return f"❌ Error: {str(e)}", ""


# ----------------- BUILD GRADIO UI -------------------
def build_ui():
    with gr.Blocks(title="Blend360 - DataOps LLM Assistant") as demo:

        gr.Markdown("# 🧠 Blend360 - Intelligent SQL Assistant")
        gr.Markdown(
            "Ask any question about your retail data — the system will:\n"
            "1️⃣ Perform RAG → 2️⃣ Convert NL→SQL → 3️⃣ Validate → 4️⃣ Execute → 5️⃣ Answer.\n"
        )

        with gr.Row():
            question = gr.Textbox(
                label="Ask a question",
                placeholder="Example: Total SKU for MEN5004-KR-L...",
                lines=1
            )

        ask_btn = gr.Button("Ask")
        answer_output = gr.Markdown(label="Final Answer")
        debug_output = gr.Markdown(label="SQL + Debug Info")

        ask_btn.click(
            fn=ask_backend,
            inputs=[question],
            outputs=[answer_output, debug_output]
        )

    return demo


if __name__ == "__main__":
    ui = build_ui()
    ui.launch(server_port=7860, debug=True)
