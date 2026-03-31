import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent))

from openai import OpenAI
from config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.OPENAI_API_KEY, organization=settings.OPENAI_ORG)

def test_variant(name, input_data):
    print(f"\n--- Testing Variant: {name} ---")
    try:
        resp = client.responses.create(
            model="gpt-4o",
            input=input_data,
            temperature=0.0
        )
        print(f"✅ Success: {resp.output_text[:50]}...")
    except Exception as e:
        print(f"❌ Failure: {str(e)[:200]}")

# 1. Base64 dummy image
dummy_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="

# V1: OpenAI Standard (List of Dicts with Role/Content-List) - ALREADY FAILED 400
# V2: List of Parts (Gemini style)
v2_input = [
    "O que tem nesta imagem?",
    {"inline_data": {"mime_type": "image/png", "data": dummy_b64}}
]

# V3: List of Dicts with Role/Parts
v3_input = [
    {"role": "user", "parts": ["Hi", {"inline_data": {"mime_type": "image/png", "data": dummy_b64}}]}
]

# V5: Single dict with role/content (String content) - TO CONFIRM TEXT WORKS
v5_input = [{"role": "user", "content": "Hi (Text Only)"}]

# V6: List of Dicts with Role/Content (Content is list of Gemini Parts WITHOUT 'type')
v6_input = [
    {
        "role": "user",
        "content": [
            {"text": "O que tem nesta imagem?"},
            {"inline_data": {"mime_type": "image/png", "data": dummy_b64}}
        ]
    }
]

# V8: Final discovery - using input_text and input_image types
v8_input = [
    {
        "role": "user",
        "content": [
            {"type": "input_text", "input_text": "O que tem nesta imagem?"},
            {
                "type": "input_image", 
                "input_image": {
                    "mime_type": "image/png", 
                    "data": dummy_b64
                }
            }
        ]
    }
]

if __name__ == "__main__":
    test_variant("V5 (Text Only)", v5_input)
    test_variant("V8 (input_text/input_image)", v8_input)
