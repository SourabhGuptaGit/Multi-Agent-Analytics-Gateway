# from agents.validation_agent import validate_and_fix_sql
# from agents.nl_to_sql_agent import generate_sql_from_question

# # q = "Find Total SKU with value 'MEN5004-KR-L'"
# q = "Find Total SKU with value 'MEN5004-KR-L' in international_sales table"
# sql, schema_struct = generate_sql_from_question(q, top_k=8)
# print("Generated SQL:", sql)

# res = validate_and_fix_sql(sql, schema_struct, auto_fix=True)
# print("Validation result:", res)



from core.sql_executor import SQLExecutor

executor = SQLExecutor()

sql = "SELECT * FROM cloud_warehouse LIMIT 5"
# sql = "SELECT COUNT(*) AS total_sku FROM international_sales WHERE SKU = 'MEN5004-KR-L'"
result = executor.run_sql(sql)

print(result["rows"])
formatted = executor.format_results(result["df"])
print(formatted["markdown"])
