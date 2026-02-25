---
task: 04-gpt4o-mini-parsing
status: done
depends: [03-fetch-soundcloud-details]
files:
  - path: scripts/enrich_metadata.py
    action: modify
---

# GPT-4o-mini Metadata Parsing

## Context
Send the extracted SoundCloud fields to GPT-4o-mini for intelligent parsing. The AI will extract clean, structured metadata from the often messy SoundCloud data.

## Files to Modify/Create
- scripts/enrich_metadata.py (modify)

## Implementation Details

### OpenAI Client Setup
```python
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
```

### Prompt Structure
```python
SYSTEM_PROMPT = """You are a music metadata parser. Parse SoundCloud track data into clean, structured metadata.

Rules:
- If username matches label_name or common label patterns (Records, Music, Recordings), don't include as artist
- Extract featured artists from "feat.", "ft.", "featuring", "with" patterns in title
- Identify remix artist from "(X Remix)", "(X Edit)", "(X Bootleg)", "[X Mix]" patterns
- Clean title: remove artist prefix, [Free DL], promo text, but keep remix attribution
- Genre: use the genre from SoundCloud as-is (preserve original)
- Year: prefer release_year, fall back to created_at year"""

def build_user_prompt(sc_data: dict) -> str:
    # Safely extract fields with fallbacks
    description = sc_data.get('description') or ''
    description_preview = description[:500] if description else '(none)'

    return f"""Parse this SoundCloud track:

- Title: {sc_data.get('title') or '(unknown)'}
- Username (uploader): {sc_data.get('username') or '(unknown)'}
- Metadata Artist: {sc_data.get('metadata_artist') or '(none)'}
- Description: {description_preview}
- Genre: {sc_data.get('genre') or '(none)'}
- Label: {sc_data.get('label_name') or '(none)'}
- Release Year: {sc_data.get('release_year') or '(none)'}
- Tags: {sc_data.get('tag_list') or '(none)'}
- Created: {sc_data.get('created_at') or '(unknown)'}

Return JSON with exactly these fields:
{{"title": "...", "original_artists": [...], "featured_artists": [...], "remix_artist": "..." or null, "genre": "...", "year": ... or null}}"""
```

### API Call
```python
def parse_with_ai(sc_data: dict) -> tuple[dict, dict]:
    """Parse SC data with GPT-4o-mini. Returns (parsed_result, usage_stats)."""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(sc_data)},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,  # Low temp for consistent parsing
    )

    result = json.loads(response.choices[0].message.content)
    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    return result, usage
```

### Expected Output Structure
```python
{
    "title": "Track Name (Someone Remix)",
    "original_artists": ["Artist1", "Artist2"],
    "featured_artists": ["Singer"],
    "remix_artist": "Someone",
    "genre": "House",
    "year": 2024,
    "label": "Label Records"
}
```

## Verification
```bash
uv run python scripts/enrich_metadata.py /path/to/track.mp3 --dry-run
```

Expected: Script prints parsed metadata from AI, plus token usage stats.
