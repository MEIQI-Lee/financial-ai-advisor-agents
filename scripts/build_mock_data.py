from financial_ai_advisor_agents.database.seed import initialize_default_database


if __name__ == "__main__":
    path = initialize_default_database()
    print(f"Mock database created: {path}")
