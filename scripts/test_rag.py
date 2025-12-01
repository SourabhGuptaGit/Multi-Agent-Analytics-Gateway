from core.rag import build_prompt_context

def test_build_prompt_context():
    q = "Which provider listed lowest storage cost?"
    context, schema_struct = build_prompt_context(q, top_k=6)
    print(context)               # See the block you will pass to the LLM
    print(schema_struct["recommended_columns"][:10])  # programmatic usage

test_build_prompt_context()