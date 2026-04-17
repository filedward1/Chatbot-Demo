from google import genai
from dotenv import load_dotenv
from google.genai import types
import os
import json
import re
import logging
import time

import uuid
from datetime import datetime
from supabase import create_client, Client

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("lexa.chatbot")

# Current session ID
current_session_id = str(uuid.uuid4())
last_fetch_status = {}

last_llm_error = None
last_llm_error_at = None
last_llm_success = None
last_api_error = None

load_dotenv()


def _to_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _to_int(value, default=0):
    try:
        return int(value)
    except Exception:
        return default


def _to_optional_int(value):
    try:
        parsed = int(value)
        return parsed if parsed > 0 else None
    except Exception:
        return None


LLM_MODE = "gemini"

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")
CHAT_FAST_FAIL_SECONDS = _to_int(os.getenv("CHAT_FAST_FAIL_SECONDS", "35"), default=35)
INTENT_FAST_FAIL_SECONDS = _to_int(os.getenv("INTENT_FAST_FAIL_SECONDS", "20"), default=20)
TITLE_FAST_FAIL_SECONDS = _to_int(os.getenv("TITLE_FAST_FAIL_SECONDS", "12"), default=12)
LLM_MAX_OUTPUT_TOKENS = _to_optional_int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "0"))

# Optional task-specific caps. Falls back to LLM_MAX_OUTPUT_TOKENS if unset.
CHAT_MAX_OUTPUT_TOKENS = _to_optional_int(os.getenv("CHAT_MAX_OUTPUT_TOKENS", "0"))
JSON_MAX_OUTPUT_TOKENS = _to_int(os.getenv("JSON_MAX_OUTPUT_TOKENS", "240"), default=240)
TITLE_MAX_OUTPUT_TOKENS = _to_int(os.getenv("TITLE_MAX_OUTPUT_TOKENS", "48"), default=48)

# Speed/quality controls. Defaults favor faster replies by avoiding extra LLM calls.
ENABLE_INTENT_CLASSIFIER = _to_bool(os.getenv("ENABLE_INTENT_CLASSIFIER", "false"), default=False)
ENABLE_TROUBLESHOOTING_EXPANSION = _to_bool(os.getenv("ENABLE_TROUBLESHOOTING_EXPANSION", "false"), default=False)

# Initialize Supabase client
if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
    logger.error("Supabase credentials not found. Check your .env file.")
    exit()

supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

def reset_chat():
    global current_session_id

    current_session_id = str(uuid.uuid4())
    return current_session_id

# Create Gemini client only if key is available.
client = None
if os.getenv("GEMINI_API_KEY"):
    try:
        client = genai.Client()
    except Exception as e:
        logger.exception("Gemini client initialization failed")
        client = None

system_prompt = """
You are LEXA, which stands for Laptop EXpert Assistant.

Identity and tone:
- LEXA is modern, confident, and tech-savvy.
- LEXA specializes in expert laptop guidance and personalized support.
- Keep responses helpful, concise, and friendly.
- Speak in first person as LEXA when appropriate.

Name explanation for internal behavior alignment:
LEXA stands for Laptop EXpert Assistant. The name emphasizes expertise specifically in laptops - "LEX" directly highlighting "Laptop EXpert." LEXA represents smart, expert guidance that makes laptop shopping effortless.

Scope:
- Primary focus: laptop recommendations, specs, comparisons, and buying guidance.
- Secondary support: troubleshooting and aftersales support.

Instructions:
1. Identify what the user needs.
2. Recommend only from available products provided in the current prompt context.
3. If troubleshooting, give step-by-step solution.
4. Keep answer clear.
"""


def _generate_with_gemini(prompt: str, temperature: float = 0.2, max_output_tokens: int | None = None):
    if client is None:
        raise RuntimeError("Gemini is not configured (missing GEMINI_API_KEY).")

    resolved_max_tokens = max_output_tokens if max_output_tokens is not None else LLM_MAX_OUTPUT_TOKENS
    config_args = {
        "system_instruction": system_prompt,
        "temperature": temperature,
    }
    if resolved_max_tokens is not None:
        config_args["max_output_tokens"] = resolved_max_tokens

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(**config_args),
    )
    return (response.text or "").strip()


def _looks_truncated(text: str):
    cleaned = (text or "").strip()
    if len(cleaned) < 40:
        return False

    # Consider common complete endings as non-truncated.
    if re.search(r"[.!?)]['\"]?$", cleaned):
        return False

    # These endings are typically incomplete thoughts.
    if re.search(r"[,;:\-\(\[]['\"]?$", cleaned):
        return True

    trailing_word_match = re.search(r"([a-zA-Z0-9]+)['\"]?$", cleaned)
    trailing_word = (trailing_word_match.group(1).lower() if trailing_word_match else "")
    if trailing_word in {"a", "an", "the", "and", "or", "with", "for", "to", "like"}:
        return True

    # If the text ends on an unfinished word/phrase, treat it as truncated.
    return bool(re.search(r"[a-z0-9]$", cleaned.lower()))


def _mark_llm_error(error_text: str):
    global last_llm_error, last_llm_error_at
    last_llm_error = error_text
    last_llm_error_at = datetime.now().isoformat()


def _mark_llm_success(provider: str, model: str, elapsed_ms: int):
    global last_llm_success, last_llm_error, last_llm_error_at
    last_llm_success = {
        "provider": provider,
        "model": model,
        "elapsed_ms": elapsed_ms,
        "at": datetime.now().isoformat(),
    }
    last_llm_error = None
    last_llm_error_at = None


def get_llm_diagnostics():
    return {
        "config": {
            "llm_mode": LLM_MODE,
            "gemini_model": GEMINI_MODEL,
            "max_output_tokens": LLM_MAX_OUTPUT_TOKENS,
            "chat_max_output_tokens": CHAT_MAX_OUTPUT_TOKENS,
            "json_max_output_tokens": JSON_MAX_OUTPUT_TOKENS,
            "title_max_output_tokens": TITLE_MAX_OUTPUT_TOKENS,
            "enable_intent_classifier": ENABLE_INTENT_CLASSIFIER,
            "enable_troubleshooting_expansion": ENABLE_TROUBLESHOOTING_EXPANSION,
        },
        "runtime": {
            "last_llm_error": last_llm_error,
            "last_llm_error_at": last_llm_error_at,
            "last_llm_success": last_llm_success,
        },
    }


def _generate_text(
    prompt: str,
    use_quality_model: bool = False,
    temperature: float = 0.2,
    preferred_provider: str | None = None,
    fast_fail_seconds: int | None = None,
    use_fast_ctx: bool = False,
    max_output_tokens: int | None = None,
    allow_auto_continue: bool = False,
):
    provider_start = time.time()
    try:
        result = _generate_with_gemini(
            prompt,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        if allow_auto_continue and _looks_truncated(result):
            # Retry continuation up to two times when the draft still looks incomplete.
            for _ in range(2):
                continue_prompt = f"""
                Continue the text below from exactly where it ended.
                - Do not repeat earlier sentences.
                - Do not restart from the beginning.
                - End with a complete sentence.
                - Return only the continuation text.

                Text:
                {result}
                """
                continuation = _generate_with_gemini(
                    continue_prompt,
                    temperature=temperature,
                    max_output_tokens=min(260, max_output_tokens or CHAT_MAX_OUTPUT_TOKENS),
                )
                if continuation:
                    result = f"{result} {continuation}".strip()

                if not _looks_truncated(result):
                    break

        elapsed_ms = int((time.time() - provider_start) * 1000)
        _mark_llm_success("gemini", GEMINI_MODEL, elapsed_ms)
        return result
    except Exception as e:
        logger.exception("Gemini generation failed")
        _mark_llm_error(str(e))
        raise RuntimeError(f"Gemini API request failed: {e}")


def _extract_json_object(text: str):
    try:
        return json.loads(text)
    except Exception:
        pass

    match = re.search(r"\{[\s\S]*\}", text or "")
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            return None
    return None


def _generate_json(prompt: str, use_quality_model: bool = True, fast_fail_seconds: int | None = None):
    strict_prompt = (
        f"{prompt}\n\n"
        "Output rules:\n"
        "- Return valid JSON only.\n"
        "- Do not include markdown.\n"
        "- Do not include explanation text."
    )
    raw = _generate_text(
        strict_prompt,
        use_quality_model=use_quality_model,
        temperature=0.0,
        fast_fail_seconds=fast_fail_seconds,
        max_output_tokens=JSON_MAX_OUTPUT_TOKENS,
    )
    return _extract_json_object(raw)


print("Chatbot is running. Type 'exit' to quit.\n")
print(f"LLM mode: {LLM_MODE}")


def _fetch_rows(table_name: str, columns: str = "*"):
    """Fetch rows from a Supabase table and return a list."""
    global last_fetch_status
    try:
        response = supabase.table(table_name).select(columns).execute()
        rows = response.data or []
        last_fetch_status[table_name] = {
            "ok": True,
            "count": len(rows),
            "error": None,
            "checked_at": datetime.now().isoformat(),
        }
        return rows
    except Exception as e:
        logger.exception("Error fetching table '%s'", table_name)
        last_fetch_status[table_name] = {
            "ok": False,
            "count": 0,
            "error": str(e),
            "checked_at": datetime.now().isoformat(),
        }
        return []


def _table_fetch_failed(table_name: str):
    status = last_fetch_status.get(table_name) or {}
    return status.get("ok") is False


def _table_fetch_error(table_name: str):
    status = last_fetch_status.get(table_name) or {}
    return status.get("error")


def fetch_product_catalog():
    """Fetch product catalog data from Supabase laptop and printer tables."""
    laptops = _fetch_rows("laptop", "id,name,price,tags")
    printers = _fetch_rows("printer", "id,name,price,tags")
    return {
        "laptop": laptops,
        "printer": printers,
    }


def format_product_catalog(catalog: dict):
    """Create a compact readable product catalog text block for prompts."""
    laptop_rows = catalog.get("laptop", [])
    printer_rows = catalog.get("printer", [])

    lines = ["Laptops:"]

    def format_php_price(value):
        try:
            return f"Php (₱){int(value):,}"
        except Exception:
            return "Php (₱)N/A"

    if laptop_rows:
        for item in laptop_rows:
            lines.append(
                f"- {item.get('name', 'Unknown')} | price: {format_php_price(item.get('price'))} | tags: {item.get('tags', '')}"
            )
    else:
        lines.append("- None available")

    lines.append("\nPrinters:")
    if printer_rows:
        for item in printer_rows:
            lines.append(
                f"- {item.get('name', 'Unknown')} | price: {format_php_price(item.get('price'))} | tags: {item.get('tags', '')}"
            )
    else:
        lines.append("- None available")

    return "\n".join(lines)


def _parse_troubleshooting_steps(raw_steps):
    """Normalize troubleshooting steps from text/JSON into a list of step strings."""
    if isinstance(raw_steps, list):
        return [str(step).strip() for step in raw_steps if str(step).strip()]

    if raw_steps is None:
        return []

    if isinstance(raw_steps, str):
        text = raw_steps.strip()
        if not text:
            return []

        # Accept JSON array text if the DB stores steps as serialized JSON.
        if text.startswith("[") and text.endswith("]"):
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(step).strip() for step in parsed if str(step).strip()]
            except Exception:
                pass

        if "\n" in text:
            return [part.strip(" -\t") for part in text.splitlines() if part.strip()]

        if ";" in text:
            return [part.strip(" -\t") for part in text.split(";") if part.strip()]

        return [text]

    return [str(raw_steps).strip()]


def _get_first_present_value(row: dict, candidate_keys):
    """Return the first non-empty value from candidate keys in a row."""
    for key in candidate_keys:
        if key in row and row.get(key) not in (None, ""):
            return row.get(key)
    return None


def fetch_troubleshooting_entries():
    """Fetch troubleshooting rows from Supabase troubleshooting table."""
    # Use * because the schema includes spaced/parenthesized column names.
    rows = _fetch_rows("troubleshooting", "*")
    normalized = []
    for row in rows:
        issue = _get_first_present_value(
            row,
            ["Specific Device Issue", "specific_device_issue", "issue"],
        )
        sop_steps = _get_first_present_value(
            row,
            [
                "Advanced Technical Troubleshooting (SOP)",
                "advanced_technical_troubleshooting_sop",
                "advanced technical troubleshooting (sop)",
                "Advanced Technical Troubleshooting SOP",
                "steps",
            ],
        )

        normalized.append({
            "specific_issue": str(issue or "").strip(),
            "advanced_sop_steps": _parse_troubleshooting_steps(sop_steps),
        })
    return normalized


def fetch_warranty_entries():
    """Fetch warranty rows from Supabase warranty table."""
    rows = _fetch_rows("warranty", "*")
    normalized = []
    for row in rows:
        brand = _get_first_present_value(
            row,
            ["Brand", "brand"],
        )
        warranty_link = _get_first_present_value(
            row,
            [
                "Warranty Lookup Link",
                "warranty_lookup_link",
                "warranty link",
                "warranty_lookup",
            ],
        )

        normalized.append({
            "brand": str(brand or "").strip(),
            "warranty_link": str(warranty_link or "").strip(),
        })
    return normalized


def _normalize_free_text(text: str):
    return " ".join((text or "").strip().lower().split())


def _contains_any(text: str, keywords):
    lowered = (text or "").lower()
    return any(word in lowered for word in keywords)


def _build_main_troubleshooting_idea(steps_list):
    """Collapse stored SOP content into one concise main idea sentence."""
    cleaned = [str(step).strip() for step in (steps_list or []) if str(step).strip()]
    if not cleaned:
        return ""
    if len(cleaned) == 1:
        return cleaned[0]
    return "; ".join(cleaned)


def _clean_step_text(step: str):
    text = str(step or "").strip()
    text = re.sub(r"^\d+[\.)]\s*", "", text)
    return text.strip()


def _format_troubleshooting_markdown(issue: str, main_idea: str, why_line: str, steps_list):
    cleaned_steps = []
    seen = set()
    main_norm = _normalize_free_text(main_idea)

    for raw in steps_list or []:
        step = _clean_step_text(raw)
        if not step:
            continue
        step_norm = _normalize_free_text(step)
        if step_norm == main_norm:
            continue
        if step_norm in seen:
            continue
        seen.add(step_norm)
        cleaned_steps.append(step)

    lines = [
        f"LEXA here. For issue '{issue}', follow this Advanced Technical Troubleshooting (SOP):",
        "",
        f"Main idea: {main_idea}",
    ]

    if why_line:
        lines.append(f"Why this helps: {why_line}")

    if cleaned_steps:
        lines.extend(["", "Steps:"])
        for idx, step in enumerate(cleaned_steps, start=1):
            lines.append(f"{idx}. {step}")

    return "\n".join(lines)


def _parse_expanded_troubleshooting_text(expanded_text: str, fallback_main_idea: str):
    lines = [line.strip() for line in (expanded_text or "").splitlines() if line.strip()]
    parsed_main_idea = fallback_main_idea
    why_line = ""
    steps = []

    for line in lines:
        lowered = line.lower()
        if lowered.startswith("main idea:"):
            parsed_main_idea = line.split(":", 1)[1].strip() or fallback_main_idea
            continue
        if lowered.startswith("why this helps:"):
            why_line = line.split(":", 1)[1].strip()
            continue
        if re.match(r"^\d+[\.)]\s+", line):
            steps.append(line)

    return parsed_main_idea, why_line, steps


def _expound_troubleshooting_idea(issue: str, main_idea: str):
    """Use configured LLM provider to expand a concise troubleshooting idea."""
    if not main_idea:
        return ""

    prompt = f"""
    You are LEXA (Laptop EXpert Assistant), helping with technical troubleshooting.

    Issue: {issue}
    Main troubleshooting idea: {main_idea}

    Expand the main idea into practical guidance for a non-technical user.

    Rules:
    - Start with: Main idea: <repeat the exact main idea>
    - Add one line after it: Why this helps: <one simple sentence>
    - Then provide 3-5 short numbered steps.
    - Each step should be specific and easy to follow (about 8-14 words).
    - Keep the full response concise and clear, with troubleshooting as the main content.
    - Mention one simple caution/safety reminder only if relevant.
    - Do not invent product-specific details that were not provided.
    - Do not include markdown headings, bullet symbols, or extra sections.
    - Do not advertise, cross-sell, suggest buying new devices, or suggest upgrades.
    - End with one short follow-up question asking for issue specifics (device model, exact error message, and when it happens) for more detailed troubleshooting.
    """

    try:
        return _generate_text(
            prompt,
            use_quality_model=True,
            fast_fail_seconds=CHAT_FAST_FAIL_SECONDS,
            max_output_tokens=CHAT_MAX_OUTPUT_TOKENS,
            allow_auto_continue=True,
        )
    except Exception:
        return ""


def _extract_recent_user_text(conversation_history=None):
    if not conversation_history:
        return ""

    user_texts = [
        m.get("content", "")
        for m in conversation_history[-8:]
        if m.get("role") == "user" and m.get("content")
    ]
    return "\n".join(user_texts)


def _resolve_brand(user_message: str, conversation_history, entries):
    known_brands = sorted(
        {
            item.get("brand", "").strip()
            for item in entries
            if item.get("brand", "").strip()
        },
        key=lambda x: x.lower(),
    )

    search_space = f"{_extract_recent_user_text(conversation_history)}\n{user_message}".lower()
    for brand in known_brands:
        if brand.lower() in search_space:
            return brand, known_brands

    return None, known_brands


def _resolve_issue(user_message: str, conversation_history, brand_entries):
    search_space = f"{_extract_recent_user_text(conversation_history)}\n{user_message}".lower()
    known_issues = sorted(
        {
            item.get("specific_issue", "").strip()
            for item in brand_entries
            if item.get("specific_issue", "").strip()
        },
        key=lambda x: x.lower(),
    )

    for issue in known_issues:
        if issue.lower() in search_space:
            return issue, known_issues

    # Fast deterministic pre-match to avoid an LLM call when wording still overlaps.
    def _norm_tokens(text: str):
        tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
        normalized = []
        for token in tokens:
            tok = token
            if len(tok) > 5 and tok.endswith("ing"):
                tok = tok[:-3]
            elif len(tok) > 4 and tok.endswith("ed"):
                tok = tok[:-2]
            elif len(tok) > 4 and tok.endswith("es"):
                tok = tok[:-2]
            elif len(tok) > 3 and tok.endswith("s"):
                tok = tok[:-1]
            if tok:
                normalized.append(tok)
        return set(normalized)

    search_tokens = _norm_tokens(search_space)
    best_issue = None
    best_overlap = 0
    for issue in known_issues:
        issue_tokens = _norm_tokens(issue)
        overlap = len(issue_tokens.intersection(search_tokens))
        if overlap > best_overlap:
            best_overlap = overlap
            best_issue = issue

    if best_issue and best_overlap >= 2:
        return best_issue, known_issues

    # Context-based resolver: infer the best issue from meaning using recent chat context.
    if known_issues:
        recent_context = _extract_recent_user_text(conversation_history)

        candidate_details = []
        for item in brand_entries:
            issue = (item.get("specific_issue") or "").strip()
            if not issue:
                continue

            steps_preview = [
                str(step).strip()
                for step in (item.get("advanced_sop_steps") or [])[:2]
                if str(step).strip()
            ]
            candidate_details.append({
                "issue": issue,
                "steps_preview": steps_preview,
            })

        issue_pick_prompt = f"""
        You are matching a user's device problem to one known troubleshooting issue.

        Conversation context (recent user messages):
        {recent_context or "(none)"}

        New user message:
        {user_message}

        Candidate troubleshooting issues and SOP hints:
        {json.dumps(candidate_details, ensure_ascii=True)}

        Return valid JSON only with this exact shape:
        {{"issue": "<one candidate issue or null>", "confidence": <0 to 1 number>}}

        Rules:
        - Use user intent and symptom meaning, not strict keyword overlap.
        - Select exactly one issue only if it is meaningfully supported by context.
        - If ambiguous or unsupported, set issue to null.
        - Confidence must reflect certainty.
        """

        try:
            pick = _generate_json(
                issue_pick_prompt,
                use_quality_model=True,
                fast_fail_seconds=INTENT_FAST_FAIL_SECONDS,
            ) or {}

            chosen_issue = str(pick.get("issue") or "").strip()
            confidence = float(pick.get("confidence", 0) or 0)

            if chosen_issue in known_issues and confidence >= 0.45:
                return chosen_issue, known_issues
        except Exception:
            logger.exception("Context-based issue resolution failed")

    return None, known_issues


def _is_warranty_request(user_message: str, conversation_history=None):
    text = f"{_extract_recent_user_text(conversation_history)}\n{user_message}".lower()
    return _contains_any(text, ["warranty", "guarantee", "rma", "claim", "coverage"])


def _is_support_request(user_message: str, conversation_history=None):
    text = f"{_extract_recent_user_text(conversation_history)}\n{user_message}".lower()
    return _contains_any(
        text,
        [
            "troubleshoot",
            "not working",
            "problem",
            "issue",
            "error",
            "fix",
            "repair",
            "warranty",
            "rma",
            "support",
            "paper jam",
            "out of paper",
            "paper tray",
            "toner",
            "ink",
            "won't print",
            "will not print",
        ],
    )


def _is_recommendation_request(user_message: str, conversation_history=None):
    text = f"{_extract_recent_user_text(conversation_history)}\n{user_message}".lower()
    return _contains_any(
        text,
        [
            "recommend",
            "suggest",
            "looking for",
            "need a laptop",
            "need a printer",
            "want a laptop",
            "want a printer",
            "best laptop",
            "best printer",
            "gaming",
            "aaa",
            "student laptop",
            "student printer",
            "for school",
        ],
    )


def _is_comparison_request(user_message: str, conversation_history=None):
    text = f"{_extract_recent_user_text(conversation_history)}\n{user_message}".lower()
    return _contains_any(
        text,
        [
            "which is better",
            "better between",
            "compare",
            "comparison",
            "vs",
            "versus",
            " or ",
        ],
    )


def _tokenize_text(text: str):
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _resolve_recommendation_product_type(user_message: str, conversation_history=None, intent_data=None):
    """Resolve whether recommendation should target laptops or printers."""
    intent_product_type = str((intent_data or {}).get("product_type") or "").strip().lower()
    if intent_product_type in {"laptop", "printer"}:
        return intent_product_type

    query_text = f"{_extract_recent_user_text(conversation_history)}\n{user_message}".lower()
    printer_clues = {
        "printer", "print", "printing", "ink", "toner", "paper", "ppm", "laser", "inkjet"
    }
    laptop_clues = {
        "laptop", "notebook", "gaming", "gpu", "rtx", "cpu", "school laptop"
    }

    query_tokens = _tokenize_text(query_text)
    if query_tokens.intersection(printer_clues):
        return "printer"
    if query_tokens.intersection(laptop_clues):
        return "laptop"

    return "laptop"


def _pick_comparison_candidates(user_message: str, conversation_history, catalog: dict, max_items: int = 2):
    laptops = catalog.get("laptop", []) or []
    query_text = f"{_extract_recent_user_text(conversation_history)}\n{user_message}".lower()
    query_tokens = _tokenize_text(query_text)

    direct = []
    for item in laptops:
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        if name.lower() in query_text:
            direct.append(item)

    if len(direct) >= max_items:
        return direct[:max_items]

    scored = []
    for item in laptops:
        name = str(item.get("name", "")).strip()
        tags = str(item.get("tags", "")).strip().lower()
        if not name:
            continue
        pool = _tokenize_text(f"{name} {tags}")
        overlap = len(pool.intersection(query_tokens))
        if overlap > 0:
            scored.append((overlap, item))

    scored.sort(key=lambda row: row[0], reverse=True)
    picks = list(direct)
    for _, item in scored:
        if item in picks:
            continue
        picks.append(item)
        if len(picks) >= max_items:
            break

    return picks[:max_items]


def _build_catalog_comparison(user_message: str, conversation_history, catalog: dict):
    picks = _pick_comparison_candidates(user_message, conversation_history, catalog, max_items=2)
    if len(picks) < 2:
        return _build_catalog_recommendation(user_message, conversation_history, catalog)

    perf_tokens = {
        "i7", "i9", "ryzen", "r7", "r9", "rtx", "gpu", "graphics", "gaming", "performance", "creator"
    }

    def format_php_price(value):
        try:
            return f"Php (P){int(value):,}"
        except Exception:
            return "Php (P)N/A"

    def score_item(item):
        tags = str(item.get("tags", "")).lower()
        tokens = _tokenize_text(f"{item.get('name', '')} {tags}")
        score = len(tokens.intersection(perf_tokens))
        try:
            price = int(item.get("price") or 0)
        except Exception:
            price = 0
        score += min(price // 50000, 4)
        return score

    a, b = picks[0], picks[1]
    a_score = score_item(a)
    b_score = score_item(b)
    winner = a if a_score >= b_score else b

    winner_name = winner.get("name", "Unknown")
    a_name = a.get("name", "Unknown")
    b_name = b.get("name", "Unknown")

    lines = [
        f"LEXA here. Between {a_name} and {b_name}, {winner_name} is the better choice for software creation based on our catalog data.",
        "",
        "Quick comparison:",
        f"- {a_name} | {format_php_price(a.get('price'))} | tags: {a.get('tags', '')}",
        f"- {b_name} | {format_php_price(b.get('price'))} | tags: {b.get('tags', '')}",
        "",
        "If you want, I can compare them specifically for coding, VMs, or game dev workloads.",
    ]

    return "\n".join(lines)


def _build_catalog_recommendation(user_message: str, conversation_history, catalog: dict, max_items: int = 3):
    laptops = catalog.get("laptop", []) or []
    if not laptops:
        return "LEXA here. I can't find laptop entries in the catalog right now."

    context_text = user_message
    query_tokens = _tokenize_text(context_text)
    query_lower = context_text.lower()

    performance_tokens = {"aaa", "gaming", "game", "games", "fps", "gpu", "graphics", "rtx"}
    student_tokens = {"student", "school", "class", "study", "budget"}
    portability_tokens = {"light", "portable", "thin", "travel", "battery", "ultrabook"}
    creator_tokens = {"create", "editing", "video", "software", "coding", "programming", "dev"}

    def infer_recommendation_theme():
        if query_tokens.intersection(performance_tokens):
            return "gaming"
        if query_tokens.intersection(student_tokens):
            return "budget"
        if query_tokens.intersection(portability_tokens):
            return "portable"
        if query_tokens.intersection(creator_tokens):
            return "productivity"
        return "general"

    theme = infer_recommendation_theme()

    if theme == "gaming":
        section_title = "Top Gaming Picks"
        intro = "If you want strong AAA performance, these are the best laptops from the database right now:"
        quick_guidance = [
            "Go for the highest-performance option if you want better AAA frame rates.",
            "Choose the more balanced pick if you want a mix of power and value.",
            "Pick the budget option only if you can lower graphics settings a bit.",
        ]
    elif theme == "budget":
        section_title = "Top Budget Picks"
        intro = "Here are the best value laptops from the database for your budget:"
        quick_guidance = [
            "Choose the best-balanced model if you want the safest all-around value.",
            "Pick the cheapest model if price is your top priority.",
            "Stretch your budget only if you need noticeably better performance or storage.",
        ]
    elif theme == "portable":
        section_title = "Top Portable Picks"
        intro = "Here are the most portable laptops I found in the database:"
        quick_guidance = [
            "Choose the lightest option if you travel often.",
            "Pick the battery-focused model if you need all-day use.",
            "Go for the balanced model if you still want some performance headroom.",
        ]
    elif theme == "productivity":
        section_title = "Top Productivity Picks"
        intro = "Here are the laptops that make the most sense for coding, software work, or content creation:"
        quick_guidance = [
            "Choose the strongest CPU/RAM combo for software work and multitasking.",
            "Pick the balanced option if you want a good mix of speed and value.",
            "Choose the lighter option if you care about portability as much as power.",
        ]
    else:
        section_title = "Recommended Laptops"
        intro = "Here are the best laptop options I found in the database:"
        quick_guidance = [
            "Pick the top-ranked model if you want the safest all-around choice.",
            "Choose the second option if you want a more balanced value pick.",
            "Choose the third option if your budget is tighter.",
        ]

    scored = []
    for item in laptops:
        name = str(item.get("name", "")).strip()
        tags = str(item.get("tags", ""))
        if not name:
            continue

        price = 0
        try:
            price = int(item.get("price") or 0)
        except Exception:
            price = 0

        name_tokens = _tokenize_text(name)
        tag_tokens = _tokenize_text(tags)
        token_pool = name_tokens.union(tag_tokens)

        score = 0
        score += len(query_tokens.intersection(token_pool)) * 2

        if query_tokens.intersection(performance_tokens):
            if token_pool.intersection(performance_tokens):
                score += 8
            # Slightly prefer stronger machines for gaming requests.
            score += min(price // 50000, 4)

        if query_tokens.intersection(student_tokens):
            if token_pool.intersection(student_tokens):
                score += 4
            # Slightly prefer lower cost for student/budget requests.
            if price > 0:
                score += max(0, 3 - min(price // 30000, 3))

        scored.append((score, price, item))

    scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    selected = [row[2] for row in scored[:max_items]]

    def summarize_best_for(item):
        tags = str(item.get("tags", "")).lower()
        tag_tokens = _tokenize_text(tags)

        if theme == "gaming":
            if tag_tokens.intersection(performance_tokens):
                return "AAA gaming, heavy multitasking, and higher graphics settings"
            return "general gaming with lower settings"

        if theme == "budget":
            if tag_tokens.intersection(student_tokens):
                return "students and everyday use on a tighter budget"
            return "budget-conscious everyday use"

        if theme == "portable":
            if tag_tokens.intersection(portability_tokens):
                return "travel, school, and all-day mobility"
            return "portable everyday use"

        if theme == "productivity":
            if tag_tokens.intersection(creator_tokens):
                return "software work, coding, and multitasking"
            return "general productivity and multitasking"

        return "general everyday productivity"

    def format_php_price(value):
        try:
            return f"Php (₱){int(value):,}"
        except Exception:
            return "Php (₱)N/A"

    lines = [
        "Hello! I'm LEXA, your Laptop EXpert Assistant.",
        "",
        intro,
        "",
        f"## {section_title}",
        "",
    ]

    for idx, item in enumerate(selected, start=1):
        lines.extend(
            [
                f"{idx}. **{item.get('name', 'Unknown')}**",
                f"   - **Price:** {format_php_price(item.get('price'))}",
                f"   - **Best For:** {summarize_best_for(item)}",
                f"   - **Tags:** {item.get('tags', '')}",
                "",
            ]
        )

    lines.extend(
        [
            "### LEXA's Quick Guidance",
            "",
        ]
    )

    for tip in quick_guidance:
        lines.append(f"- {tip}")

    lines.extend(
        [
            "",
            "Tell me your budget, and I can narrow this down further.",
        ]
    )

    return "\n".join(lines)


def _build_printer_recommendation(user_message: str, conversation_history, catalog: dict, max_items: int = 3):
    printers = catalog.get("printer", []) or []
    if not printers:
        return "LEXA here. I can't find printer entries in the catalog right now."

    context_text = f"{_extract_recent_user_text(conversation_history)}\n{user_message}"
    query_tokens = _tokenize_text(context_text)

    speed_tokens = {
        "fast", "faster", "speed", "quick", "ppm", "high", "performance", "efficient"
    }
    student_tokens = {"student", "students", "school", "class", "study", "budget", "affordable"}
    expensive_tokens = {"expensive", "premium", "high-end", "highend", "top", "best"}

    wants_fast = bool(query_tokens.intersection(speed_tokens))
    wants_student = bool(query_tokens.intersection(student_tokens))
    wants_expensive = (
        "most expensive" in context_text.lower()
        or "highest price" in context_text.lower()
        or bool(query_tokens.intersection(expensive_tokens))
    )

    def infer_theme():
        if wants_expensive:
            return "premium"
        if wants_student:
            return "student"
        if wants_fast:
            return "fast"
        return "general"

    theme = infer_theme()

    if theme == "premium":
        section_title = "Top Premium Printer Picks"
        intro = "If you want higher-end options, these are the strongest premium printers from the database:"
        quick_guidance = [
            "Pick the top-priced option if you want the most premium model available.",
            "Choose the second pick if you want strong value at a slightly lower cost.",
            "If speed matters, prioritize models tagged for faster printing.",
        ]
    elif theme == "student":
        section_title = "Top Student Printer Picks"
        intro = "Here are the best printer options for students and school work from the database:"
        quick_guidance = [
            "Choose the lowest running-cost option for frequent school printing.",
            "Pick the balanced model if you want both value and consistent speed.",
            "Go for all-in-one capability if you need scanning for assignments.",
        ]
    elif theme == "fast":
        section_title = "Top Fast Printer Picks"
        intro = "If speed is your priority, these are the best fast printer options I found in the database:"
        quick_guidance = [
            "Choose the highest-ranked speed-focused model for quicker large print jobs.",
            "Pick the balanced option if you want speed without overspending.",
            "Check paper capacity and duty cycle if you print frequently.",
        ]
    else:
        section_title = "Recommended Printers"
        intro = "Here are the best printer options I found in the database:"
        quick_guidance = [
            "Pick the top-ranked model for the safest all-around choice.",
            "Choose the second pick if you want better value.",
            "Tell me your budget so I can narrow this to one best option.",
        ]

    def parse_price(item):
        try:
            return int(item.get("price") or 0)
        except Exception:
            return 0

    def score_item(item):
        name = str(item.get("name", "")).strip().lower()
        tags = str(item.get("tags", "")).strip().lower()
        token_pool = _tokenize_text(f"{name} {tags}")
        price = parse_price(item)

        score = len(query_tokens.intersection(token_pool)) * 2

        if wants_fast:
            if token_pool.intersection(speed_tokens):
                score += 8
            if re.search(r"\b(\d{2,3})\s*ppm\b", tags):
                score += 4

        if wants_student:
            if token_pool.intersection(student_tokens):
                score += 5
            if price > 0:
                score += max(0, 4 - min(price // 3000, 4))

        if wants_expensive:
            score += min(price // 5000, 8)

        return score, price

    scored = []
    for item in printers:
        if not str(item.get("name", "")).strip():
            continue
        score, price = score_item(item)
        scored.append((score, price, item))

    if wants_expensive and wants_fast:
        scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
    elif wants_expensive:
        scored.sort(key=lambda row: row[1], reverse=True)
    else:
        scored.sort(key=lambda row: (row[0], -row[1]), reverse=True)

    selected = [row[2] for row in scored[:max_items]]

    def summarize_best_for(item):
        tags = str(item.get("tags", "")).lower()
        tag_tokens = _tokenize_text(tags)

        if theme == "premium":
            if tag_tokens.intersection(speed_tokens):
                return "premium printing with stronger speed for heavier workloads"
            return "premium everyday and office printing"

        if theme == "student":
            if tag_tokens.intersection(speed_tokens):
                return "student use with faster assignment and document printing"
            return "school requirements, reviewers, and regular home printing"

        if theme == "fast":
            return "high-volume or time-sensitive printing tasks"

        return "general home and office printing"

    def format_php_price(value):
        try:
            return f"Php (P){int(value):,}"
        except Exception:
            return "Php (P)N/A"

    lines = [
        "Hello! I'm LEXA, your Laptop EXpert Assistant.",
        "",
        intro,
        "",
        f"## {section_title}",
        "",
    ]

    for idx, item in enumerate(selected, start=1):
        lines.extend(
            [
                f"{idx}. **{item.get('name', 'Unknown')}**",
                f"   - **Price:** {format_php_price(item.get('price'))}",
                f"   - **Best For:** {summarize_best_for(item)}",
                f"   - **Tags:** {item.get('tags', '')}",
                "",
            ]
        )

    lines.extend(
        [
            "### LEXA's Quick Guidance",
            "",
        ]
    )

    for tip in quick_guidance:
        lines.append(f"- {tip}")

    lines.extend(
        [
            "",
            "Tell me your estimated monthly print volume, and I can narrow this down further.",
        ]
    )

    return "\n".join(lines)


def get_catalog_diagnostics():
    """Return a quick health snapshot for Supabase-backed catalog tables."""
    catalog = fetch_product_catalog()
    warranty_rows = fetch_warranty_entries()
    troubleshooting_rows = fetch_troubleshooting_entries()

    laptop_rows = catalog.get("laptop", [])
    printer_rows = catalog.get("printer", [])

    return {
        "catalog_counts": {
            "laptop": len(laptop_rows),
            "printer": len(printer_rows),
            "warranty": len(warranty_rows),
            "troubleshooting": len(troubleshooting_rows),
        },
        "sample_rows": {
            "laptop": [
                {
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "tags": item.get("tags"),
                }
                for item in laptop_rows[:3]
            ],
            "printer": [
                {
                    "name": item.get("name"),
                    "price": item.get("price"),
                    "tags": item.get("tags"),
                }
                for item in printer_rows[:3]
            ],
            "warranty": [
                {
                    "brand": item.get("brand"),
                    "warranty_link": item.get("warranty_link"),
                }
                for item in warranty_rows[:3]
            ],
            "troubleshooting": [
                {
                    "specific_issue": item.get("specific_issue"),
                    "steps_count": len(item.get("advanced_sop_steps", [])),
                }
                for item in troubleshooting_rows[:3]
            ],
        },
        "fetch_status": last_fetch_status,
    }


def handle_troubleshooting(user_message, conversation_history=None):
    warranty_data = fetch_warranty_entries()
    troubleshooting_data = fetch_troubleshooting_entries()

    warranty_failed = _table_fetch_failed("warranty")
    troubleshooting_failed = _table_fetch_failed("troubleshooting")

    if troubleshooting_failed and not troubleshooting_data:
        logger.error("Troubleshooting table fetch failed: %s", _table_fetch_error("troubleshooting"))
        return "LEXA here. I can't access troubleshooting records right now. Please try again shortly."

    if not warranty_data and not troubleshooting_data:
        return "LEXA here. Troubleshooting and warranty records are currently empty. Please ask your admin to populate the tables."

    if _is_warranty_request(user_message, conversation_history):
        if not warranty_data:
            if warranty_failed:
                logger.error("Warranty table fetch failed: %s", _table_fetch_error("warranty"))
                return "LEXA here. I can't access warranty records right now. Please try again shortly."

            return "LEXA here. Warranty records are empty right now. Please ask your admin to add warranty entries."

        resolved_brand, known_brands = _resolve_brand(user_message, conversation_history, warranty_data)
        if not resolved_brand:
            brand_list = ", ".join(known_brands[:10]) if known_brands else "available brands"
            return (
                "LEXA here. I can help with warranty lookup, but I need the brand first. "
                f"Please tell me the brand (for example: {brand_list})."
            )

        warranty_link = ""
        for item in warranty_data:
            if _normalize_free_text(item.get("brand", "")) == _normalize_free_text(resolved_brand) and item.get("warranty_link"):
                warranty_link = item.get("warranty_link")
                break

        if warranty_link:
            return (
                f"LEXA here. For {resolved_brand}, use this warranty lookup link:\n"
                f"{warranty_link}"
            )

        return f"LEXA here. I found {resolved_brand}, but there is no warranty lookup link saved yet."

    if not troubleshooting_data:
        if troubleshooting_failed:
            logger.error("Troubleshooting table fetch failed: %s", _table_fetch_error("troubleshooting"))
            return "LEXA here. I can't access troubleshooting records right now. Please try again shortly."

        return "LEXA here. Troubleshooting records are empty right now. Please ask your admin to add SOP entries."

    resolved_issue, known_issues = _resolve_issue(user_message, conversation_history, troubleshooting_data)
    if not resolved_issue:
        issue_hint = ", ".join(known_issues[:8]) if known_issues else "the exact issue"
        return (
            "LEXA here. Tell me the specific device issue so I can provide the SOP "
            f"(for example: {issue_hint})."
        )

    matched_entry = None
    for item in troubleshooting_data:
        if _normalize_free_text(item.get("specific_issue", "")) == _normalize_free_text(resolved_issue):
            matched_entry = item
            break

    steps_list = (matched_entry or {}).get("advanced_sop_steps", [])
    if not steps_list:
        return (
            f"LEXA here. I found the issue '{resolved_issue}', "
            "but no Advanced Technical Troubleshooting (SOP) steps are saved yet."
        )

    main_idea = _build_main_troubleshooting_idea(steps_list)

    if not ENABLE_TROUBLESHOOTING_EXPANSION:
        # Faster path: return stored SOP directly without another model roundtrip.
        return _format_troubleshooting_markdown(
            resolved_issue,
            main_idea,
            "",
            steps_list,
        )

    expanded_guidance = _expound_troubleshooting_idea(resolved_issue, main_idea)
    if expanded_guidance:
        parsed_main_idea, why_line, parsed_steps = _parse_expanded_troubleshooting_text(
            expanded_guidance,
            fallback_main_idea=main_idea,
        )
        if not parsed_steps:
            parsed_steps = steps_list
        return _format_troubleshooting_markdown(
            resolved_issue,
            parsed_main_idea,
            why_line,
            parsed_steps,
        )

    # Fallback if LLM expansion fails.
    return _format_troubleshooting_markdown(
        resolved_issue,
        main_idea,
        "",
        steps_list,
    )

def extract_intent(user_message, conversation_history=None):
    context_block = ""
    if conversation_history:
        formatted = "\n".join(
            [f"{m['role'].capitalize()}: {m['content']}" for m in conversation_history[-6:]]
        )
        context_block = f"Recent conversation:\n{formatted}\n\n"

    intent_prompt = f"""
    {context_block}Analyze this message:

    "{user_message}"

    Extract:
    - intent (recommendation, troubleshooting, aftersales, product_detail, warranty, or general)
    - product_type (laptop, printer, or the specific product name/type being referred to based on the conversation; use "unknown" only if truly unclear)
    - support_type (technical, warranty, or unknown)
    - brand (brand referenced by the user, if any; otherwise null)
    - issue (specific device issue if provided; otherwise null)
    - features (list)
    - context_product (if this is a follow-up about a previously discussed product, name it here; otherwise null)

    Use the recent conversation to resolve vague references (e.g. "its price", "give me the specs", "what about the warranty").
    Return JSON only.
    """

    return _generate_json(
        intent_prompt,
        use_quality_model=True,
        fast_fail_seconds=INTENT_FAST_FAIL_SECONDS,
    )

def create_conversation_in_db():
    # """Create a new conversation record in the database (or use existing if it already exists)"""
    try:
        response = supabase.table("conversation").upsert({
            "id": current_session_id,
            "created_at": datetime.now().isoformat()
        }).execute()
        return response.data
    except Exception as e:
        logger.exception("Failed to create conversation record")
        # Even if upsert fails, the record may still exist
        return None


def get_conversation_title(session_id: str):
    """Return the stored title for a conversation, if available."""
    try:
        response = supabase.table("conversation").select("title").eq("id", session_id).single().execute()
        if response.data and response.data.get("title"):
            return response.data.get("title")
    except Exception:
        pass

    return None


def set_conversation_title(session_id: str, title: str):
    """Store/update the conversation title in Supabase."""
    try:
        supabase.table("conversation").update({"title": title}).eq("id", session_id).execute()
        return True
    except Exception:
        # If this fails, we ignore it; the chat will still work without a title.
        return False


def maybe_generate_title_for_session(session_id: str):
    """Generate a short conversation title based on the first few messages."""
    # Don't regenerate if a title already exists.
    existing_title = get_conversation_title(session_id)
    if existing_title:
        return existing_title

    # Pull the first few messages for context.
    conv = get_conversation_messages(session_id)
    messages = conv.get("messages", [])
    if not messages:
        return None

    # Build a deterministic fallback title from the first user message.
    first_user_message = ""
    for msg in messages:
        if msg.get("role") == "user" and msg.get("content"):
            first_user_message = msg.get("content", "").strip()
            break

    fallback_title = "New Conversation"
    if first_user_message:
        fallback_title = " ".join(first_user_message.split())
        if len(fallback_title) > 80:
            fallback_title = fallback_title[:80].rsplit(" ", 1)[0]
        if not fallback_title:
            fallback_title = "New Conversation"

    # Use up to the first 4 messages (user+bot pairs) to create a title.
    sample = messages[:4]
    formatted = "\n".join([f"{m['role'].capitalize()}: {m['content']}" for m in sample])

    prompt = f"""
    You are an assistant that generates a short, descriptive title for a conversation.
    Provide a concise title (2-6 words) that summarizes the topic of the conversation.

    Conversation:
    {formatted}

    Return only the title (no quotes or punctuation around it).
    """

    try:
        title = _generate_text(
            prompt,
            use_quality_model=False,
            fast_fail_seconds=TITLE_FAST_FAIL_SECONDS,
            max_output_tokens=TITLE_MAX_OUTPUT_TOKENS,
        ).strip().strip('"').strip("'")
        if not title:
            title = fallback_title

        # Keep it reasonably short.
        if len(title) > 80:
            title = title[:80].rsplit(" ", 1)[0]

        if not title:
            title = fallback_title

        set_conversation_title(session_id, title)
        return title
    except Exception:
        # If LLM title generation fails, still set a deterministic fallback title.
        set_conversation_title(session_id, fallback_title)
        return fallback_title


def set_current_session(session_id: str):
    """Set the current session id and ensure it exists in the DB."""
    global current_session_id
    current_session_id = session_id

    try:
        supabase.table("conversation").upsert({
            "id": current_session_id,
            "created_at": datetime.now().isoformat()
        }).execute()
    except Exception:
        logger.warning(f"Could not upsert conversation record for session {session_id}")
        # Continue anyway; the session can still work even if the record wasn't created

def save_message_to_db(role, content):
    # """Save a message to the database"""
    # Ensure a conversation record exists before saving any messages.
    create_conversation_in_db()

    try:
        response = supabase.table("messages").insert({
            "id": str(uuid.uuid4()),
            "conversation_id": current_session_id,
            "role": role,
            "content": content,
            "created_at": datetime.now().isoformat()
        }).execute()

        return response.data
    except Exception as e:
        logger.exception("Error saving message")
        return None
    
def get_bot_response(user_message, session_id=None):
    global current_session_id

    # If the client is continuing an existing conversation, switch to that session.
    if session_id:
        set_current_session(session_id)

    # Fetch recent messages so vague follow-ups can be resolved with context.
    conv = get_conversation_messages(current_session_id)
    recent_messages = conv.get("messages", [])[-6:]

    intent_data = None
    if ENABLE_INTENT_CLASSIFIER:
        try:
            intent_data = extract_intent(user_message, conversation_history=recent_messages)
        except Exception:
            logger.exception("Intent extraction failed; continuing with heuristic routing")
            intent_data = None

    intent_name = (intent_data or {}).get("intent", "")
    if intent_name in {"troubleshooting", "aftersales", "warranty"} or _is_support_request(user_message, recent_messages):
        bot_reply = handle_troubleshooting(user_message, conversation_history=recent_messages)
    elif _is_comparison_request(user_message, recent_messages):
        catalog = fetch_product_catalog()
        bot_reply = _build_catalog_comparison(user_message, recent_messages, catalog)
    elif _is_recommendation_request(user_message, recent_messages):
        catalog = fetch_product_catalog()
        recommendation_type = _resolve_recommendation_product_type(
            user_message,
            conversation_history=recent_messages,
            intent_data=intent_data,
        )
        if recommendation_type == "printer":
            bot_reply = _build_printer_recommendation(user_message, recent_messages, catalog)
        else:
            bot_reply = _build_catalog_recommendation(user_message, recent_messages, catalog)
    else:
        catalog = fetch_product_catalog()
        products_context = format_product_catalog(catalog)

        # Build a conversation context block so the LLM can resolve follow-up references.
        context_block = ""
        if recent_messages:
            formatted_history = "\n".join(
                [f"{m['role'].capitalize()}: {m['content']}" for m in recent_messages]
            )
            context_block = f"Recent conversation:\n{formatted_history}\n\n"

        prompt = f"""
        {context_block}User message: {user_message}

        User intent:
        {intent_data}

        Available products:
        {products_context}

        Instructions:
        - Respond as LEXA (Laptop EXpert Assistant) with a modern, confident, tech-savvy tone.
        - Keep recommendations focused on laptops and practical buying guidance whenever relevant.
        - If this is a follow-up question referring to a previously recommended product (e.g. "give me the price", "what are the specs", "show me the warranty"), identify that product from the conversation context and answer specifically about it.
        - For support questions, collect brand first, then identify the specific issue before giving technical guidance.
        - Do not ask for clarification if the referenced product is clear from the conversation history.
        - Provide a structured, clear response.
        """
        try:
            bot_reply = _generate_text(
                prompt,
                use_quality_model=True,
                fast_fail_seconds=CHAT_FAST_FAIL_SECONDS,
                max_output_tokens=CHAT_MAX_OUTPUT_TOKENS,
                allow_auto_continue=True,
            )
        except Exception as e:
            logger.exception("Primary response generation failed")
            error_str = str(e)
            bot_reply = (
                "LEXA here. I can't reach the Gemini API right now. "
                "Please retry in a few seconds."
            )
            # Store error details globally so the endpoint can send it separately
            global last_api_error
            last_api_error = error_str

    # Save messages to Supabase
    save_message_to_db("user", user_message)
    save_message_to_db("bot", bot_reply)

    # Generate a short conversation title once we have at least one user + bot exchange.
    maybe_generate_title_for_session(current_session_id)

    return bot_reply

def get_conversation_history():
    # """Fetch all conversations from the database"""
    try:
        response = supabase.table("conversation").select("*").execute()
        conversations_dict = {}
        
        for conv in response.data:
            conv_id = conv["id"]
            title = conv.get("title") or get_conversation_title(conv_id)
            conversations_dict[conv_id] = {
                "created_at": conv["created_at"],
                "title": title,
                "messages": []
            }
        
        return conversations_dict
    except Exception as e:
        logger.exception("Error fetching conversation history")
        return {}

def get_conversation_messages(session_id):
    # """Fetch messages for a specific conversation"""
    try:
        response = supabase.table("messages").select("*").eq("conversation_id", session_id).order("created_at").execute()
        
        messages = []
        for msg in response.data:
            messages.append({
                "role": msg["role"],
                "content": msg["content"],
                "created_at": msg["created_at"]
            })
        
        return {
            "id": session_id,
            "messages": messages
        }
    except Exception as e:
        logger.exception("Error fetching messages")
        return {"id": session_id, "messages": []}


def delete_conversation(session_id: str):
    """Delete a conversation and all of its messages."""
    try:
        supabase.table("messages").delete().eq("conversation_id", session_id).execute()
        supabase.table("conversation").delete().eq("id", session_id).execute()
        return True
    except Exception as e:
        logger.exception("Error deleting conversation")
        return False


