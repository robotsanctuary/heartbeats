"""
matching_logic.py

Takes the structured output of ai_extractor.extract_pet_info() plus the
raw post metadata (platform, url, poster handle) and decides one of
three outcomes:

  1. EXACT MATCH   -> pet_id found in `pets` table -> append a MediaSource row.
  2. NEW PENDING    -> pet_id present but not yet in `pets` (shelter scraper
                       hasn't caught up yet) -> create a PendingProfile row.
  3. FUZZY MATCH    -> no pet_id extracted -> compare animal_description
                       against active pets at the same shelter using an
                       LLM-judged similarity score. If confidence > 0.85,
                       auto-merge (attach media). Otherwise, park it in
                       PendingProfile for a human to review.

Install:
    pip install psycopg2-binary openai

Environment:
    LOCAL_DATABASE_URL   e.g. postgresql://user:pass@localhost:5432/animals
    OPENAI_API_KEY
"""

import json
import os
import uuid
from dataclasses import dataclass
from typing import Optional

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
DATABASE_URL = os.environ["LOCAL_DATABASE_URL"]

# Confidence bands. Anything at or above the upper bound auto-commits.
# Anything below the lower bound is treated as effectively "no match" /
# "don't trust this extraction." The band in between is genuinely
# ambiguous -- rather than guessing, it gets flagged for a human to
# glance at. This band is what keeps low-quality edge cases from slowly
# accumulating into bad data instead of silently corrupting the DB.
FUZZY_MATCH_AUTO_MERGE = 0.85
FUZZY_MATCH_REVIEW_FLOOR = 0.55

EXTRACTION_AUTO_TRUST = 0.75
EXTRACTION_REVIEW_FLOOR = 0.4


@dataclass
class SocialPost:
    platform: str            # "tiktok" | "instagram" | "x" | "facebook"
    url: str
    posted_by: Optional[str]
    raw_text: str


def get_connection():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def _log_audit(
    cur,
    stage: str,
    action: str,
    input_text: Optional[str],
    model_output: Optional[dict],
    confidence: Optional[float],
    related_pet_id: Optional[str],
    post: Optional["SocialPost"],
) -> None:
    """
    Records every AI decision, win or lose. This table is what you query
    later to compute real accuracy (once a human has spot-checked a
    sample) and to watch confidence trends for signs of model drift --
    see accuracy_report.py.
    """
    cur.execute(
        """
        INSERT INTO audit_log
            (id, stage, action, input_text, model_output, confidence,
             related_pet_id, platform, url)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(uuid.uuid4()),
            stage,
            action,
            input_text,
            json.dumps(model_output) if model_output is not None else None,
            confidence,
            related_pet_id,
            post.platform if post else None,
            post.url if post else None,
        ),
    )


def process_extraction(extraction: dict, post: SocialPost) -> dict:
    """
    Main entry point. `extraction` is the dict returned by
    ai_extractor.extract_pet_info(). Returns a small result dict describing
    what action was taken, useful for logging/monitoring.
    """
    confidence = extraction.get("confidence", 0.0)

    # A low-confidence extraction is more dangerous than no extraction --
    # a wrong pet_id can silently attach a stranger's post to the wrong
    # animal's profile. Below the floor, don't act on it at all; just log
    # and park it for a human.
    if confidence < EXTRACTION_REVIEW_FLOOR:
        with get_connection() as conn:
            with conn.cursor() as cur:
                _create_pending_profile(
                    cur, extraction, post,
                    extracted_pet_id=extraction.get("pet_id"),
                    needs_review=True,
                    review_reason=f"low extraction confidence ({confidence:.2f})",
                )
                _log_audit(cur, "extraction", "FLAGGED_FOR_REVIEW",
                           post.raw_text, extraction, confidence, None, post)
                conn.commit()
        return {"action": "FLAGGED_FOR_REVIEW", "reason": "low_extraction_confidence", "confidence": confidence}

    pet_id = extraction.get("pet_id")

    if pet_id:
        return _handle_with_pet_id(pet_id, extraction, post)

    return _handle_without_pet_id(extraction, post)


# ---------------------------------------------------------------------
# Case 1 & 2: an explicit pet_id was extracted from the post
# ---------------------------------------------------------------------

def _handle_with_pet_id(pet_id: str, extraction: dict, post: SocialPost) -> dict:
    confidence = extraction.get("confidence", 0.0)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pet_id FROM pets WHERE pet_id = %s", (pet_id,))
            existing = cur.fetchone()

            if existing:
                _attach_media_source(cur, pet_id, post)
                _log_audit(cur, "extraction", "APPENDED_TO_EXISTING_PET",
                           post.raw_text, extraction, confidence, pet_id, post)
                conn.commit()
                return {"action": "APPENDED_TO_EXISTING_PET", "pet_id": pet_id}

            # Shelter scraper (Script A) hasn't ingested this ID yet.
            # Stage it as pending so the next scraper cycle can promote it.
            # A mid-confidence extraction still gets staged, but flagged,
            # so a human glances at it before it's treated as gospel.
            needs_review = confidence < EXTRACTION_AUTO_TRUST
            _create_pending_profile(
                cur, extraction, post, extracted_pet_id=pet_id,
                needs_review=needs_review,
                review_reason=f"unconfirmed pet_id, confidence {confidence:.2f}" if needs_review else None,
            )
            _log_audit(cur, "extraction", "CREATED_PENDING_PROFILE",
                       post.raw_text, extraction, confidence, pet_id, post)
            conn.commit()
            return {"action": "CREATED_PENDING_PROFILE", "extracted_pet_id": pet_id, "needs_review": needs_review}


# ---------------------------------------------------------------------
# Case 3: no pet_id -- attempt fuzzy matching against active listings
# ---------------------------------------------------------------------

def _handle_without_pet_id(extraction: dict, post: SocialPost) -> dict:
    description = extraction.get("animal_description")
    shelter_name = extraction.get("shelter_name")

    if not description:
        # Nothing usable to match on at all.
        with get_connection() as conn:
            with conn.cursor() as cur:
                _create_pending_profile(cur, extraction, post, extracted_pet_id=None)
                conn.commit()
        return {"action": "CREATED_PENDING_PROFILE", "reason": "no_description"}

    with get_connection() as conn:
        with conn.cursor() as cur:
            candidates = _fetch_active_candidates(cur, shelter_name)

            if not candidates:
                _create_pending_profile(cur, extraction, post, extracted_pet_id=None)
                conn.commit()
                return {"action": "CREATED_PENDING_PROFILE", "reason": "no_candidates"}

            best_match, probability = _llm_fuzzy_match(description, candidates)
            match_pet_id = best_match["pet_id"] if best_match else None

            # High confidence -> auto-merge.
            if best_match and probability >= FUZZY_MATCH_AUTO_MERGE:
                _attach_media_source(cur, match_pet_id, post)
                _log_audit(cur, "fuzzy_match", "FUZZY_MATCHED_AND_MERGED",
                           description, best_match, probability, match_pet_id, post)
                conn.commit()
                return {
                    "action": "FUZZY_MATCHED_AND_MERGED",
                    "pet_id": match_pet_id,
                    "probability": probability,
                }

            # Middle band -> genuinely ambiguous. Don't guess either way;
            # stage it and let a human confirm or reject the suggested match.
            if best_match and probability >= FUZZY_MATCH_REVIEW_FLOOR:
                _create_pending_profile(
                    cur, extraction, post, extracted_pet_id=None,
                    needs_review=True,
                    review_reason=f"possible match to {match_pet_id} at {probability:.2f} probability",
                )
                _log_audit(cur, "fuzzy_match", "FLAGGED_FOR_REVIEW",
                           description, best_match, probability, match_pet_id, post)
                conn.commit()
                return {
                    "action": "FLAGGED_FOR_REVIEW",
                    "possible_pet_id": match_pet_id,
                    "probability": probability,
                }

            # Low confidence -> treat as no match.
            _create_pending_profile(cur, extraction, post, extracted_pet_id=None)
            _log_audit(cur, "fuzzy_match", "CREATED_PENDING_PROFILE",
                       description, best_match, probability, match_pet_id, post)
            conn.commit()
            return {
                "action": "CREATED_PENDING_PROFILE",
                "reason": "fuzzy_match_below_threshold",
                "best_candidate": match_pet_id,
                "probability": probability,
            }


def _fetch_active_candidates(cur, shelter_name: Optional[str], limit: int = 25) -> list:
    """
    Narrow the fuzzy-match search space to active (AT_RISK / PENDING_VERIFICATION)
    pets, optionally scoped to the shelter mentioned in the post, to keep the
    LLM comparison cheap and accurate.
    """
    if shelter_name:
        cur.execute(
            """
            SELECT pet_id, name, breed, age, sex, description, shelter_name
            FROM pets
            WHERE status IN ('AT_RISK', 'PENDING_VERIFICATION')
              AND shelter_name ILIKE %s
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (f"%{shelter_name}%", limit),
        )
    else:
        cur.execute(
            """
            SELECT pet_id, name, breed, age, sex, description, shelter_name
            FROM pets
            WHERE status IN ('AT_RISK', 'PENDING_VERIFICATION')
            ORDER BY updated_at DESC
            LIMIT %s
            """,
            (limit,),
        )
    return cur.fetchall()


FUZZY_MATCH_SCHEMA = {
    "name": "fuzzy_match_result",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "best_match_pet_id": {
                "type": ["string", "null"],
                "description": "pet_id of the closest matching candidate, or null if none plausibly match.",
            },
            "probability": {
                "type": "number",
                "description": "0.0-1.0 probability that best_match_pet_id refers to the same animal as the post description.",
            },
            "reasoning": {
                "type": "string",
                "description": "One sentence explaining the match or lack thereof.",
            },
        },
        "required": ["best_match_pet_id", "probability", "reasoning"],
        "additionalProperties": False,
    },
}


def _llm_fuzzy_match(post_description: str, candidates: list) -> tuple[Optional[dict], float]:
    """
    Ask the model to compare the social post's animal description against
    a shortlist of active shelter listings and return the best match plus
    a calibrated probability. Returns (candidate_row_or_None, probability).
    """
    candidate_summaries = [
        {
            "pet_id": c["pet_id"],
            "name": c["name"],
            "breed": c["breed"],
            "age": c["age"],
            "sex": c["sex"],
            "description": c["description"],
        }
        for c in candidates
    ]

    user_prompt = (
        "Social media post description of an at-risk animal:\n"
        f'"{post_description}"\n\n'
        "Candidate active shelter listings (JSON):\n"
        f"{json.dumps(candidate_summaries, indent=2)}\n\n"
        "Which candidate, if any, most likely refers to the same animal? "
        "Only choose a match if breed, size/age, and any distinguishing "
        "details are consistent. If nothing plausibly matches, return "
        "best_match_pet_id: null and probability: 0."
    )

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a careful matching assistant for an animal "
                    "shelter database. Be conservative: only report high "
                    "probability when details clearly align."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_schema", "json_schema": FUZZY_MATCH_SCHEMA},
        temperature=0,
    )

    result = json.loads(response.choices[0].message.content)
    match_id = result["best_match_pet_id"]
    probability = result["probability"]

    matched_row = next((c for c in candidates if c["pet_id"] == match_id), None)
    return matched_row, probability


# ---------------------------------------------------------------------
# Shared writers
# ---------------------------------------------------------------------

def _attach_media_source(cur, pet_id: str, post: SocialPost) -> None:
    cur.execute(
        """
        INSERT INTO media_sources (id, pet_id, platform, url, posted_by, raw_text)
        VALUES (%s, %s, %s, %s, %s, %s)
        ON CONFLICT (pet_id, url) DO NOTHING
        """,
        (str(uuid.uuid4()), pet_id, post.platform, post.url, post.posted_by, post.raw_text),
    )


def _create_pending_profile(
    cur,
    extraction: dict,
    post: SocialPost,
    extracted_pet_id: Optional[str],
    needs_review: bool = False,
    review_reason: Optional[str] = None,
) -> None:
    cur.execute(
        """
        INSERT INTO pending_profiles
            (id, extracted_pet_id, shelter_name_guess, description,
             deadline_guess, platform, url, posted_by, raw_text,
             needs_review, review_reason)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            str(uuid.uuid4()),
            extracted_pet_id,
            extraction.get("shelter_name"),
            extraction.get("animal_description"),
            extraction.get("deadline"),
            post.platform,
            post.url,
            post.posted_by,
            post.raw_text,
            needs_review,
            review_reason,
        ),
    )


if __name__ == "__main__":
    # Example wiring of ai_extractor -> matching_logic
    from ai_extractor import extract_pet_info

    sample_raw_text = (
        "🚨 Diesel (A2145501) is due out 8/2 at Dallas Animal Services! "
        "3yo pit mix, great with kids 😭 share share share!"
    )
    extraction = extract_pet_info(sample_raw_text)
    post = SocialPost(
        platform="instagram",
        url="https://instagram.com/p/example123",
        posted_by="@dallasrescuevolunteer",
        raw_text=sample_raw_text,
    )
    result = process_extraction(extraction, post)
    print(result)
