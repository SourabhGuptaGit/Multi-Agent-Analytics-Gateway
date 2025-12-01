from agents.validation_agent import validate_and_fix_sql
from agents.nl_to_sql_agent import generate_sql_from_question

# q = "Find Total SKU with value 'MEN5004-KR-L'"
q = "Find Total SKU with value 'MEN5004-KR-L' in international_sales table"
sql, schema_struct = generate_sql_from_question(q, top_k=8)
print("Generated SQL:", sql)

res = validate_and_fix_sql(sql, schema_struct, auto_fix=True)
print("Validation result:", res)
