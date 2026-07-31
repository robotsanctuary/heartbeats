"""
ai_extractor.py

Reads messy, emoji-filled volunteer social media text and returns a
clean, structured JSON block using the OpenAI API's structured outputs
feature (a JSON schema the model is constrained to follow).

Usage:
    from ai_extractor import extract_pet_info
    result = extract_pet_info(caption_text)
    print(result)

Environment:
    OPENAI_API_KEY must be set.

Install:
    pip install openai
"""

import json
import os
from typing import Optional, TypedDict

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"

# JSON Schema the model's output is constrained to. Using strict mode
# guarantees the response always matches this shape -- no more regexing
# free-form text or hoping the model didn't wrap the JSON in prose.
PET_EXTRACTION_SCHEMA = {
    "name": "pet_extraction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "pet_id": {
                "type": ["string", "null"],
                "description": (
                    "The official shelter animal ID/kennel number, e.g. "
                    "'A123456', '#4521', 'ID 88213'. Null if not mentioned."
                ),
            },
            "deadline": {
                "type": ["string", "null"],
                "description": (
                    "The euthanasia/at-risk deadline mentioned in the post, "
                    "normalized to ISO 8601 (YYYY-MM-DD or YYYY-MM-DDTHH:MM:SS) "
                    "if a date/time is stated or clearly implied (e.g. 'due out "
                    "tomorrow 5pm'). Null if no deadline is mentioned."
                ),
            },
            "shelter_name": {
                "type": ["string", "null"],
                "description": (
                    "The name of the shelter or municipal animal services "
                    "department mentioned, e.g. 'Dallas Animal Services'. "
                    "Null if not mentioned."
                ),
            },
            "animal_name": {
                "type": ["string", "null"],
                "description": "The animal's given/shelter name, if stated.",
            },
            "animal_description": {
                "type": ["string", "null"],
                "description": (
                    "Short free-text description of the animal (breed, color, "
                    "age, size, temperament) useful for fuzzy-matching against "
                    "shelter records when no pet_id is present."
                ),
            },
            "confidence": {
                "type": "number",
                "description": (
                    "0.0-1.0 self-rated confidence that the extracted fields "
                    "are accurate given the source text."
                ),
            },
        },
        "required": [
            "pet_id",
            "deadline",
            "shelter_name",
            "animal_name",
            "animal_description",
            "confidence",
        ],
        "additionalProperties": False,
    },
}

SYSTEM_PROMPT = """You are a data-extraction assistant for an animal rescue \
aggregator. You will be given raw, messy text copied from a volunteer's \
social media post (Instagram/TikTok/X caption) about a shelter animal at \
risk of euthanasia.

Extract only what is explicitly stated or very clearly implied by the text. \
Rules:
- Do not guess or invent a pet_id. Only extract it if a shelter ID/kennel \
  number pattern is visibly present (letters+digits, '#' followed by \
  digits, "ID ####", etc).
- Normalize dates relative to the fact that you don't know "today's" date \
  from the post alone -- if the post says something relative like "tomorrow" \
  or "today at 5pm" without a stated absolute date, still extract the \
  relative phrase into animal_description instead of guessing an ISO date, \
  and leave deadline null. Only fill deadline when an explicit date is \
  present (e.g. "8/2", "Aug 2", "8/2/2026").
- Strip emojis, hashtags, and marketing fluff from animal_description; keep \
  only factual descriptive content.
- If multiple animals are mentioned in one post, extract only the first/ \
  primary animal being featured.
- Set confidence lower (below 0.5) if the text is ambiguous, or if you are \
  inferring rather than reading an explicit value.
"""


class PetExtraction(TypedDict):
    pet_id: Optional[str]
    deadline: Optional[str]
    shelter_name: Optional[str]
    animal_name: Optional[str]
    animal_description: Optional[str]
    confidence: float


def extract_pet_info(raw_text: str) -> PetExtraction:
    """
    Send raw social media caption text to GPT-4o mini and get back a
    validated, structured extraction.
    """
    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": PET_EXTRACTION_SCHEMA,
        },
        temperature=0,
    )

    content = response.choices[0].message.content
    return json.loads(content)


if __name__ == "__main__":
    # Quick manual test -- run: python ai_extractor.py
    sample_posts = [
        (
            "🚨🚨 URGENT URGENT 🚨🚨 Sweet boy Diesel (ID# A2145501) is on "
            "the list at Dallas Animal Services!! He is due out 8/2!! "
            "3yo pit mix, great with kids, SO scared in the shelter 😭 "
            "please share!! #adoptdontshop #dallasrescue"
        ),
        (
            "This girl needs OUT TODAY. Vegas shelter is slammed. Sweet "
            "senior lab mix, super mellow, would do great in an apartment. "
            "No id visible in the pic sorry, DM for more info 🙏"
        ),
    ]

    for post in sample_posts:
        print("--- RAW TEXT ---")
        print(post)
        print("--- EXTRACTED ---")
        print(json.dumps(extract_pet_info(post), indent=2))
        print()
