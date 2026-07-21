from src.config.settings import settings

print("Project:", settings.project_name)
print("Version:", settings.version)
print("Provider:", settings.llm_provider)
print("Model:", settings.llm_model)
print("Database:", settings.database_path)