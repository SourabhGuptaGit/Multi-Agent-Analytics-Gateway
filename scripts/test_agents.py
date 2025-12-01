import sys
from agents.nl_to_sql_agent import generate_sql_from_question
from core.config import settings

def test_nlp_to_sql_agent():
    # q = "Find Total SKU with value 'MEN5004-KR-L'"
    q = "Find Total SKU with value 'MEN5004-KR-L' in international_sales table"
    sql, schema = generate_sql_from_question(q, top_k=6)

    print("SQL:", sql)


if __name__ == "__main__":
    args_list = sys.argv
    if len(args_list) == 1:
        test_nlp_to_sql_agent()
    elif args_list[1] == "nlp_to_sql":
        test_nlp_to_sql_agent()
    else:
        print("Invalid args...")
    