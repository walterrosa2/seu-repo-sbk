from config import get_settings
s = get_settings()
print("OPENAI_API_KEY:", s.OPENAI_API_KEY[:15] + "...")
