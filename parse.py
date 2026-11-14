import os
import re
import time
from typing import Callable, List, Optional
from google import genai
from dotenv import load_dotenv

load_dotenv()

EXTRACTION_PROMPT_TEMPLATE = """You are an expert web scraping and information extraction assistant.
Your task is to extract specific information from the provided text content of a webpage.

User Request:
"{parse_description}"

Page Content Chunk:
====================
{chunk}
====================

Instructions:
1. Extract ONLY the information that directly matches the user's request.
2. Do not hallucinate, speculate, or fabricate any facts or numbers not present in the content chunk.
3. If this chunk does NOT contain any relevant information matching the request, reply strictly with: NO_MATCH_FOUND
4. Format the extracted information cleanly (e.g. Markdown tables, bulleted lists, or key-value pairs as requested).
5. If producing a table or list, output only the rows or items found in this chunk.
"""


def get_gemini_client(api_key: Optional[str] = None) -> genai.Client:
    """
    Initializes and returns a Google GenAI client.

    Args:
        api_key: Optional Gemini API key. Defaults to GEMINI_API_KEY environment variable.

    Returns:
        genai.Client instance.
    """
    key = api_key or os.getenv("GEMINI_API_KEY", "").strip()
    if not key or key == "your_gemini_api_key_here":
        raise ValueError(
            "Gemini API Key is missing. Please set GEMINI_API_KEY in your .env file "
            "or enter it in the sidebar."
        )
    return genai.Client(api_key=key)


def _call_gemini_with_retry(
    client: genai.Client,
    model: str,
    prompt: str,
    max_retries: int = 3,
    initial_backoff: float = 2.0,
) -> str:
    """
    Sends a prompt to Gemini with exponential backoff retry for rate limits (HTTP 429).
    """
    backoff = initial_backoff
    last_error = None

    for attempt in range(1, max_retries + 1):
        try:
            # Standard generate_content method
            if hasattr(client, "models") and hasattr(client.models, "generate_content"):
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text or ""

            # Fallback interactions method
            if hasattr(client, "interactions") and hasattr(client.interactions, "create"):
                interaction = client.interactions.create(
                    model=model,
                    input=prompt,
                )
                return interaction.output_text or ""

            raise AttributeError("Unable to locate a supported generation method on the genai client.")

        except Exception as e:
            last_error = e
            error_str = str(e).lower()
            # If rate limited (HTTP 429 / resource exhausted), back off and retry
            if "429" in error_str or "quota" in error_str or "resource_exhausted" in error_str:
                if attempt < max_retries:
                    time.sleep(backoff)
                    backoff *= 2.0
                    continue
            # For non-recoverable errors or max retries exceeded, raise
            if attempt == max_retries:
                raise last_error
            time.sleep(1.0)

    raise last_error or RuntimeError("Gemini call failed unexpectedly.")


def parse_chunk_with_gemini(
    chunk: str,
    parse_description: str,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
) -> str:
    """
    Parses a single text chunk with Gemini against the user's extraction description.
    """
    client = get_gemini_client(api_key=api_key)
    prompt = EXTRACTION_PROMPT_TEMPLATE.format(
        parse_description=parse_description,
        chunk=chunk,
    )

    result = _call_gemini_with_retry(client, model=model_name, prompt=prompt)
    if "NO_MATCH_FOUND" in result.strip():
        return ""
    return result.strip()


def consolidate_results(parsed_results: List[str]) -> str:
    """
    Merges multiple chunk outputs into a unified, clean document,
    deduplicating repetitive table headers if applicable.
    """
    if not parsed_results:
        return "No matching information found across any of the webpage chunks."

    if len(parsed_results) == 1:
        return parsed_results[0]

    # Check if results are markdown tables
    is_table = all(
        "|" in res.splitlines()[0] for res in parsed_results if res.splitlines()
    )

    if is_table:
        header_lines = []
        body_lines = []
        for i, res in enumerate(parsed_results):
            lines = [ln.strip() for ln in res.splitlines() if ln.strip() and "|" in ln]
            if not lines:
                continue
            if i == 0 and len(lines) >= 2:
                header_lines = lines[:2]  # Table header + divider
                body_lines.extend(lines[2:])
            else:
                # Omit duplicate header/divider in subsequent chunks
                start_idx = 2 if len(lines) >= 2 and set(lines[1]).issubset({"-", "|", ":", " "}) else 0
                body_lines.extend(lines[start_idx:])

        if header_lines:
            return "\n".join(header_lines + body_lines)

    # Standard clean section join
    return "\n\n---\n\n".join(parsed_results)


def parse_with_gemini(
    dom_chunks: List[str],
    parse_description: str,
    api_key: Optional[str] = None,
    model_name: str = "gemini-2.5-flash",
    progress_callback: Optional[Callable[[int, int], None]] = None,
    pacing_delay: float = 1.0,
) -> str:
    """
    Iterates through DOM chunks with rate-limit pacing and aggregates the extraction.

    Args:
        dom_chunks: List of text chunks from the cleaned webpage.
        parse_description: Instructions on what data to extract.
        api_key: Optional Gemini API key.
        model_name: Model identifier (default: 'gemini-2.5-flash').
        progress_callback: Optional callback func(current_index, total_chunks).
        pacing_delay: Delay in seconds between chunk calls to avoid RPM throttling.

    Returns:
        Aggregated, formatted extraction result.
    """
    if not dom_chunks:
        return "No content chunks available to parse."

    parsed_results = []
    total = len(dom_chunks)
    errors = []

    for i, chunk in enumerate(dom_chunks, 1):
        if progress_callback:
            progress_callback(i, total)

        try:
            extracted = parse_chunk_with_gemini(
                chunk=chunk,
                parse_description=parse_description,
                api_key=api_key,
                model_name=model_name,
            )
            if extracted:
                parsed_results.append(extracted)
        except Exception as e:
            errors.append(f"Chunk {i}: {e}")

        # Rate-limiting pacing pause between API requests
        if i < total and pacing_delay > 0:
            time.sleep(pacing_delay)

    output = consolidate_results(parsed_results)

    if errors:
        warning_note = f"\n\n> ⚠️ *Note: {len(errors)} chunk(s) experienced issues during parsing: {'; '.join(errors[:2])}*"
        output += warning_note

    return output
