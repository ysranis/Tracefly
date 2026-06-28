import os
from dotenv import load_dotenv
load_dotenv()

# Test Anthropic connection
import anthropic
client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
message = client.messages.create(
    model="claude-sonnet-4-6",
    max_tokens=50,
    messages=[{"role": "user", "content": "Say 'TraceFly setup works!' and nothing else."}]
)
print("✅ Claude says:", message.content[0].text)

# Test database connection
import psycopg2
conn = psycopg2.connect(os.environ["DATABASE_URL"])
cursor = conn.cursor()
cursor.execute("SELECT version();")
version = cursor.fetchone()[0]
conn.close()
print(f"✅ Postgres connected: {version[:40]}...")

print("\n🚀 Setup complete! Ready to build.")
