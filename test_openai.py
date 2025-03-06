import openai
import os

openai.api_key = os.getenv("OPENAI_API_KEY")

if not openai.api_key:
    print("❌ ERROR: OpenAI API Key is missing!")
    exit()

try:
    models = openai.models.list()
    print("✅ API Key is valid! Available models:", [m.id for m in models.data])
except openai.AuthenticationError:
    print("❌ ERROR: Invalid API Key!")
