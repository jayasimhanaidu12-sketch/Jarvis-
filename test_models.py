"""Quick script to test which Gemini models are available and working."""
from google import genai

client = genai.Client(api_key="AQ.Ab8RN6LjYDcQcl_GVsIjQVXDLXRRhN7kJ-1zejcwLCH_6INfMQ")

models_to_try = [
    "gemini-2.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-3-flash-preview",
]

for m in models_to_try:
    try:
        r = client.models.generate_content(model=m, contents="Say OK")
        print(f"  OK  {m} -> {r.text.strip()}")
    except Exception as e:
        print(f"  FAIL {m} -> {str(e)[:100]}")
