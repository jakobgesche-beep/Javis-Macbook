import anthropic
import json


def evaluate_output(task: str, output: str, api_key: str) -> dict:
    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Du bist ein Code-Reviewer. Bewerte ob diese Aufgabe erfolgreich erledigt wurde.

Aufgabe: {task}

Output von Claude Code:
{output}

Antworte NUR mit diesem JSON-Format:
{{
  "status": "gut" oder "nachbessern",
  "grund": "Kurze Begründung",
  "verbesserungs_prompt": "Nur wenn status=nachbessern: konkreter Verbesserungs-Prompt"
}}"""

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}]
    )

    text = message.content[0].text.strip()
    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        return json.loads(text[start:end])
    except Exception:
        return {"status": "nachbessern", "grund": "JSON-Parse-Fehler", "verbesserungs_prompt": task}
