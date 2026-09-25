"""Query preprocessing, expansion, broad-query detection, and follow-up rewriting."""

import logging
import re
from dataclasses import dataclass, field

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Lightweight typo normalization for common student misspellings.
COMMON_TYPOS: dict[str, str] = {
    "libary": "library",
    "librery": "library",
    "librarry": "library",
    "attendence": "attendance",
    "scholorship": "scholarship",
    "scholorships": "scholarships",
    "exam timtable": "exam timetable",
    "timtable": "timetable",
    "hostal": "hostel",
    "facualty": "faculty",
    "departmant": "department",
    "examinaton": "examination",
    "examinations": "examination",
}

SPECIFIC_QUERY_INDICATORS: list[str] = [
    r"\btiming",
    r"\bschedule\b",
    r"\bdeadline\b",
    r"\bon monday\b",
    r"\bon tuesday\b",
    r"\bhow many\b",
    r"\bhow much\b",
    r"\bwhat time\b",
    r"\bwhat date\b",
    r"\bpercentage\b",
    r"\bminimum\b",
    r"\bmaximum\b",
]

BROAD_QUERY_PATTERNS: list[str] = [
    r"\btell me about\b",
    r"\btell me everything about\b",
    r"\bexplain\b",
    r"\bdescribe\b",
    r"\bwhat is\b",
    r"\bwhat are\b",
    r"\bgive me information about\b",
    r"\bcan you explain\b",
    r"\bhow does\b",
    r"\bhow do\b",
    r"\bwhat facilities\b",
    r"\bwhat services\b",
    r"\bwhat resources\b",
    r"\bi want to know\b",
    r"\bi want information\b",
    r"\bhelp me understand\b",
    r"\boverview of\b",
    r"\binformation about\b",
    r"\blearn about\b",
    r"\bwhat can (i|students|we) do\b",
    r"\bwhat does .+ offer\b",
    r"\bwhat does .+ provide\b",
]

GREETING_PATTERNS: list[str] = [
    r"^(hi|hello|hey|hiya|howdy)\b",
    r"^good (morning|afternoon|evening|day)\b",
    r"^greetings\b",
]

THANKS_PATTERNS: list[str] = [
    r"\bthank you\b",
    r"\bthanks\b",
    r"\bthx\b",
    r"\bappreciate it\b",
]

GOODBYE_PATTERNS: list[str] = [
    r"\b(bye|goodbye|see you|take care)\b",
    r"\bgood night\b",
]

HELP_REQUEST_PATTERNS: list[str] = [
    r"^(can you help|could you help|help me|i need help)\b",
    r"^what can you (do|help with)\??$",
    r"^how can you help\??$",
]

CLEARLY_OFF_TOPIC_PATTERNS: list[str] = [
    r"\bpresident of (the )?(united states|india|usa)\b",
    r"\bprime minister of\b",
    r"\bwho won the world cup\b",
    r"\btell me a joke\b",
    r"\bweather forecast\b",
    r"\bweather in\b",
    r"\bwhat is the weather\b",
    r"\bcapital of (?!the college\b)",
]

# Deterministic query expansion terms keyed by intent/category.
INTENT_EXPANSION_TERMS: dict[str, list[str]] = {
    "library": [
        "library services",
        "library facilities",
        "library resources",
        "book borrowing",
        "reading room",
        "digital library",
        "e-library",
        "library membership",
        "library rules",
    ],
    "attendance": [
        "attendance rules",
        "attendance requirement",
        "minimum attendance",
        "attendance policy",
        "attendance percentage",
    ],
    "examination": [
        "examination process",
        "semester exams",
        "exam schedule",
        "internal assessment",
        "exam rules",
        "evaluation",
    ],
    "scholarship": [
        "scholarship options",
        "scholarship eligibility",
        "financial aid",
        "scholarship application",
    ],
    "hostel": [
        "hostel facilities",
        "hostel rules",
        "hostel accommodation",
    ],
    "fees": [
        "fee structure",
        "tuition fees",
        "fee payment",
    ],
    "faculty": [
        "faculty members",
        "teachers",
        "professors",
    ],
    "department": [
        "departments",
        "department directory",
        "academic departments",
    ],
    "timetable": [
        "class schedule",
        "timetable",
        "lecture schedule",
    ],
    "academic": [
        "academic rules",
        "academic regulations",
        "academics",
    ],
    "admission": [
        "admission process",
        "admission requirements",
        "enrollment",
    ],
}

# Map filename fragments to intent categories for metadata-aware boosting.
FILENAME_CATEGORY_MAP: dict[str, str] = {
    "library": "library",
    "readingroom": "library",
    "reading_room": "library",
    "attendance": "attendance",
    "examination": "examination",
    "exam": "examination",
    "evaluation": "examination",
    "scholarship": "scholarship",
    "hostel": "hostel",
    "fees": "fees",
    "fee": "fees",
    "faculty": "faculty",
    "department": "department",
    "timetable": "timetable",
    "academic": "academic",
    "admission": "admission",
    "canteen": "general",
    "playground": "general",
}


@dataclass
class ProcessedQuery:
    original: str
    normalized: str
    retrieval_query: str
    expanded_queries: list[str] = field(default_factory=list)
    is_broad: bool = False
    conversation_context: str = ""


@dataclass
class ConversationalMatch:
    kind: str  # greeting, thanks, goodbye, help, off_topic
    response: str


GREETING_RESPONSE = (
    "Hi! I'm your college student assistant. "
    "What would you like to know about attendance, exams, library, fees, or other college services?"
)

THANKS_RESPONSE = "You're welcome! Let me know if you need anything else."

GOODBYE_RESPONSE = "Goodbye! Feel free to come back anytime you have college-related questions."

HELP_RESPONSE = (
    "I'm your college AI assistant. I can help with attendance, examinations, library services, "
    "fees, scholarships, departments, faculty, timetables, hostel, admission, and academic rules. "
    "What would you like to know?"
)

OFF_TOPIC_RESPONSE = (
    "I'm a college student assistant and can help with college-related questions such as "
    "attendance, exams, library, fees, departments, and academic rules. "
    "Please ask me something about your college."
)


def normalize_whitespace(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def apply_typo_corrections(text: str) -> str:
    corrected = text
    lower = text.lower()
    for typo, replacement in COMMON_TYPOS.items():
        if typo in lower:
            corrected = re.sub(re.escape(typo), replacement, corrected, flags=re.IGNORECASE)
    return corrected


def normalize_query(text: str) -> str:
    """Normalize query while preserving natural-language meaning."""
    cleaned = normalize_whitespace(text)
    cleaned = apply_typo_corrections(cleaned)
    return cleaned


def _matches_any(text: str, patterns: list[str]) -> bool:
    normalized = text.lower().strip()
    return any(re.search(pattern, normalized) for pattern in patterns)


def detect_broad_query(text: str) -> bool:
    normalized = text.lower().strip()
    if _matches_any(normalized, SPECIFIC_QUERY_INDICATORS):
        return False
    if _matches_any(normalized, BROAD_QUERY_PATTERNS):
        return True
    # Short exploratory questions without specific detail keywords.
    words = normalized.split()
    if len(words) <= 8 and any(
        phrase in normalized
        for phrase in ("about the", "about our", "about library", "about attendance", "about exam")
    ):
        return True
    return False


def infer_category_from_filename(filename: str) -> str | None:
    name = filename.lower().replace("-", "_")
    for fragment, category in FILENAME_CATEGORY_MAP.items():
        if fragment in name:
            return category
    return None


def expand_query(query: str, intent_hint: str | None) -> list[str]:
    """Generate lightweight retrieval sub-queries without LLM calls."""
    if not intent_hint or intent_hint in {"general", "unknown"}:
        return []

    terms = INTENT_EXPANSION_TERMS.get(intent_hint, [])
    if not terms:
        return []

    normalized = query.lower()
    expansions: list[str] = []
    for term in terms:
        if term.lower() not in normalized:
            expansions.append(term)

    # Limit expansions to avoid excessive retrieval work.
    return expansions[:4]


def _extract_topic_from_message(message: str) -> str | None:
    """Extract a likely topic noun from an assistant/user college message."""
    lowered = message.lower()
    for category, terms in INTENT_EXPANSION_TERMS.items():
        if category in lowered:
            return category
        for term in terms:
            if term in lowered:
                return category
    for fragment, category in FILENAME_CATEGORY_MAP.items():
        if fragment in lowered:
            return category
    return None


def _contains_topic_marker(normalized: str) -> bool:
    for category in INTENT_EXPANSION_TERMS:
        if re.search(rf"\b{re.escape(category)}\b", normalized):
            return True
    for terms in INTENT_EXPANSION_TERMS.values():
        for term in terms:
            if term in normalized:
                return True
    for fragment in FILENAME_CATEGORY_MAP:
        if re.search(rf"\b{re.escape(fragment)}\b", normalized):
            return True
    return False


def _needs_context_rewrite(question: str) -> bool:
    """Detect short follow-up questions that lack explicit topic keywords."""
    normalized = question.lower().strip()
    words = normalized.split()
    if len(words) > 12:
        return False

    if _contains_topic_marker(normalized):
        return False

    follow_up_starters = (
        "how many",
        "how much",
        "when",
        "where",
        "what about",
        "and what",
        "can i",
        "do i",
        "is there",
        "are there",
        "which",
        "who",
    )
    return normalized.startswith(follow_up_starters) or "?" in normalized


def rewrite_follow_up_query(
    question: str,
    history: list[tuple[str, str]],
    intent_hint: str | None,
) -> str:
    """Rewrite follow-up questions using recent conversation context."""
    if not history or not _needs_context_rewrite(question):
        return question

    topic = intent_hint if intent_hint and intent_hint not in {"general", "unknown"} else None
    if topic is None:
        for role, message in reversed(history):
            topic = _extract_topic_from_message(message)
            if topic:
                break

    if topic is None:
        return question

    topic_label = topic.replace("_", " ")
    return (
        f"According to the college {topic_label} policy and services, {question.rstrip('?')}? "
        f"Provide information related to college {topic_label}."
    )


def build_conversation_context(history: list[tuple[str, str]], max_turns: int | None = None) -> str:
    window = max_turns or settings.chat_history_window
    if not history or window <= 0:
        return ""

    recent = history[-window:]
    lines: list[str] = []
    for role, message in recent:
        label = "Student" if role == "user" else "Assistant"
        lines.append(f"{label}: {message.strip()}")
    return "\n".join(lines)


def match_conversational(question: str) -> ConversationalMatch | None:
    normalized = normalize_whitespace(question)
    if _matches_any(normalized, GREETING_PATTERNS) and len(normalized.split()) <= 6:
        return ConversationalMatch(kind="greeting", response=GREETING_RESPONSE)
    if _matches_any(normalized, THANKS_PATTERNS) and len(normalized.split()) <= 8:
        return ConversationalMatch(kind="thanks", response=THANKS_RESPONSE)
    if _matches_any(normalized, GOODBYE_PATTERNS):
        return ConversationalMatch(kind="goodbye", response=GOODBYE_RESPONSE)
    if _matches_any(normalized, HELP_REQUEST_PATTERNS):
        return ConversationalMatch(kind="help", response=HELP_RESPONSE)
    if _matches_any(normalized, CLEARLY_OFF_TOPIC_PATTERNS):
        return ConversationalMatch(kind="off_topic", response=OFF_TOPIC_RESPONSE)
    return None


def process_query(
    question: str,
    history: list[tuple[str, str]] | None = None,
    intent_hint: str | None = None,
) -> ProcessedQuery:
    """Build a retrieval-ready query from the student question and recent history."""
    original = question.strip()
    normalized = normalize_query(original)
    history = history or []

    is_broad = detect_broad_query(normalized)
    retrieval_query = rewrite_follow_up_query(normalized, history, intent_hint)
    expanded = expand_query(retrieval_query, intent_hint)

    if is_broad and intent_hint and intent_hint not in {"general", "unknown"}:
        category_label = intent_hint.replace("_", " ")
        overview_query = f"college {category_label} services facilities rules overview"
        if overview_query not in expanded:
            expanded.insert(0, overview_query)

    conversation_context = build_conversation_context(history)

    return ProcessedQuery(
        original=original,
        normalized=normalized,
        retrieval_query=retrieval_query,
        expanded_queries=expanded,
        is_broad=is_broad,
        conversation_context=conversation_context,
    )


def log_rag_debug(
    *,
    question: str,
    intent: str,
    raw_intent: str,
    confidence: float,
    rewritten_query: str,
    is_broad: bool,
    top_chunks: list,
    llm_called: bool,
) -> None:
    if not settings.rag_debug:
        return

    top_score = top_chunks[0].score if top_chunks else 0.0
    top_docs = [
        f"{chunk.filename}(score={chunk.score:.3f})"
        for chunk in top_chunks[:3]
    ]
    logger.info(
        "RAG debug | question=%r intent=%s raw_intent=%s confidence=%.3f "
        "rewritten=%r broad=%s top_score=%.3f chunks=%d top_docs=%s llm=%s",
        question,
        intent,
        raw_intent,
        confidence,
        rewritten_query,
        is_broad,
        top_score,
        len(top_chunks),
        top_docs,
        llm_called,
    )
