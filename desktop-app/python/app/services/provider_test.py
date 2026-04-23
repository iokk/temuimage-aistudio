from google import genai
from google.genai import types


def test_provider_connection(api_key: str, title_model: str, base_url: str = "") -> tuple[bool, str]:
    try:
        client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(timeout=30000, base_url=base_url or None),
        )
        response = client.models.generate_content(
            model=title_model or "gemini-3.1-flash-lite-preview",
            contents=["Reply with the single word OK."],
            config=types.GenerateContentConfig(response_modalities=["TEXT"]),
        )
        text = response.text.strip() if response.text else "Connected"
        return True, text or "Connected"
    except Exception as exc:
        return False, str(exc)
