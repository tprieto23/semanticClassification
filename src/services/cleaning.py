import re
import unicodedata
from collections import Counter
from pathlib import Path

import ftfy


SHORT_DOC_LINE_THRESHOLD = 200
HEADER_REPETITION_MIN = 3
HEADER_LEN_MIN = 15
HEADER_LEN_MAX = 150

PAGE_NUMBER_RE = re.compile(
    r"^\s*[-–—]?\s*\d{1,4}\s*[-–—]?\s*$"
    r"|^Página\s+\d+(\s+de\s+\d+)?\s*$"
    r"|^Page\s+\d+(\s+of\s+\d+)?\s*$",
    re.IGNORECASE,
)
SENTENCE_PUNCT_RE = re.compile(r"[.?!]")
LIST_PREFIX_RE = re.compile(r"^[a-zA-Z0-9]+[.\)]\s")
SENTENCE_END_CHARS = (".", "?", "!", ":", ";")

DOT_LEADER_RE = re.compile(r"\.{5,}")
NUMBERED_LINE_RE = re.compile(
    r"^\s*("
    r"\d+(\.\d+)*\.?\s+\S"
    r"|[a-zA-Z][.\)]\s+\S"
    r"|[IVXLCDM]+\.\s+\S"
    r"|[•·●○■□▪►‣]\s+\S"
    r")"
)
TOC_HEADER_RE = re.compile(
    r"^(CONTENIDO|ÍNDICE|INDICE|TABLE OF CONTENTS?|CONTENTS|TABLA DE CONTENIDOS?)\s*$",
    re.IGNORECASE,
)
TOC_FIRST_FRACTION = 0.15
TOC_MIN_BLOCK_LINES = 5
TOC_MIN_NUMBERED_RATIO = 0.7
TOC_MAX_LINE_LENGTH = 100


class CleaningError(RuntimeError):
    pass


def clean_text_layer1(text: str) -> tuple[str, dict]:
    """Apply universal Layer 1 cleaning rules.

    Rules (in order):
      1. Fix broken encoding (ftfy)
      2. Unicode NFC normalization (canonical accents)
      3. Remove invisible control characters (preserve \\n and \\t)
      4. Collapse multiple spaces/tabs to a single space
      5. Collapse 3+ consecutive newlines to 2 (preserve paragraphs)
      6. Strip whitespace at start/end of each line

    Returns:
        (cleaned_text, metrics_dict)
    """
    original_length = len(text)
    rules_applied: dict[str, dict] = {}

    # Rule 1: Fix broken encoding
    before = text
    text = ftfy.fix_text(text)
    rules_applied["1_encoding_fix"] = {
        "len_before": len(before),
        "len_after": len(text),
        "changed": text != before,
    }

    # Rule 2: Unicode NFC normalization
    before = text
    text = unicodedata.normalize("NFC", text)
    rules_applied["2_unicode_nfc"] = {
        "len_before": len(before),
        "len_after": len(text),
        "changed": text != before,
    }

    # Rule 3: Remove control characters (preserve \n and \t)
    before = text
    text = "".join(
        ch for ch in text
        if ch in ("\n", "\t") or unicodedata.category(ch)[0] != "C"
    )
    rules_applied["3_control_chars_removed"] = {
        "len_before": len(before),
        "len_after": len(text),
        "chars_removed": len(before) - len(text),
    }

    # Rule 4: Collapse multiple spaces/tabs to one space
    before = text
    text = re.sub(r"[ \t]+", " ", text)
    rules_applied["4_whitespace_collapsed"] = {
        "len_before": len(before),
        "len_after": len(text),
        "chars_removed": len(before) - len(text),
    }

    # Rule 5: Collapse 3+ newlines to 2
    before = text
    text = re.sub(r"\n{3,}", "\n\n", text)
    rules_applied["5_newlines_collapsed"] = {
        "len_before": len(before),
        "len_after": len(text),
        "chars_removed": len(before) - len(text),
    }

    # Rule 6: Strip each line
    before = text
    text = "\n".join(line.strip() for line in text.split("\n"))
    rules_applied["6_lines_stripped"] = {
        "len_before": len(before),
        "len_after": len(text),
        "chars_removed": len(before) - len(text),
    }

    cleaned_length = len(text)
    reduction = (
        (original_length - cleaned_length) / original_length
        if original_length > 0
        else 0.0
    )

    metrics = {
        "original_char_count": original_length,
        "cleaned_char_count": cleaned_length,
        "reduction_percentage": reduction,
        "rules_applied": rules_applied,
    }

    return text, metrics


def _is_header_candidate(line: str) -> bool:
    """A line qualifies as a header by combined heuristics."""
    if not (HEADER_LEN_MIN < len(line) < HEADER_LEN_MAX):
        return False
    # No sentence punctuation in the middle (allowed at end)
    if SENTENCE_PUNCT_RE.search(line[:-1]):
        return False
    stripped = line.lstrip()
    if not stripped:
        return False
    # Must not start with lowercase
    if stripped[0].islower():
        return False
    # Must not be a list item like "a)", "1.", "I."
    if LIST_PREFIX_RE.match(stripped):
        return False
    return True


def clean_text_layer2(text: str) -> tuple[str, dict]:
    """Apply Layer 2 structural cleaning rules.

    2a. Remove lines that are only page numbers ("23", "Página 5", "- 12 -").
    2b. Remove repeated headers/footers detected by combined heuristics
        (frequency >= 3, length 15..150, no internal sentence punctuation,
         doesn't start with lowercase, not a list item).

    Skipped entirely if the document has fewer than SHORT_DOC_LINE_THRESHOLD
    non-empty lines (frequency-based detection is not reliable on short docs).

    Returns:
        (cleaned_text, metrics_dict)
    """
    lines = text.split("\n")
    non_empty = [line for line in lines if line.strip()]

    metrics: dict = {
        "skipped_layer2_short_doc": False,
        "pages_removed": 0,
        "headers_detected": [],
        "headers_removed_count": 0,
        "lines_before": len(lines),
        "lines_after": len(lines),
    }

    if len(non_empty) < SHORT_DOC_LINE_THRESHOLD:
        metrics["skipped_layer2_short_doc"] = True
        return text, metrics

    counter = Counter(non_empty)
    headers_set = {
        line
        for line, count in counter.items()
        if count >= HEADER_REPETITION_MIN and _is_header_candidate(line)
    }

    cleaned_lines: list[str] = []
    pages_removed = 0
    headers_removed = 0

    for line in lines:
        stripped = line.strip()
        if stripped and PAGE_NUMBER_RE.match(stripped):
            pages_removed += 1
            continue
        if stripped in headers_set:
            headers_removed += 1
            continue
        cleaned_lines.append(line)

    cleaned_text = "\n".join(cleaned_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    metrics["pages_removed"] = pages_removed
    metrics["headers_detected"] = sorted(headers_set)
    metrics["headers_removed_count"] = headers_removed
    metrics["lines_after"] = len(cleaned_text.split("\n"))

    return cleaned_text, metrics


def clean_text_layer2c(text: str) -> tuple[str, dict]:
    """Apply Layer 2c: rejoin sentences split across lines (typical of PDF columns).

    Joins line N with line N+1 if ALL conditions hold:
      - Line N does not end in .?!:;
      - Line N+1 starts with a lowercase letter
      - Line N+1 is not a list item (a), 1., etc.)
      - Both lines are within the same paragraph block (no blank line between)

    Skipped if document has fewer than SHORT_DOC_LINE_THRESHOLD non-empty lines.

    Returns:
        (rejoined_text, metrics_dict)
    """
    lines = text.split("\n")
    non_empty = [line for line in lines if line.strip()]

    metrics: dict = {
        "skipped_layer2c_short_doc": False,
        "sentences_rejoined": 0,
        "lines_before": len(lines),
        "lines_after": len(lines),
    }

    if len(non_empty) < SHORT_DOC_LINE_THRESHOLD:
        metrics["skipped_layer2c_short_doc"] = True
        return text, metrics

    result: list[str] = []
    rejoined = 0
    i = 0
    while i < len(lines):
        current = lines[i]
        if i + 1 >= len(lines):
            result.append(current)
            break

        next_line = lines[i + 1]
        stripped_current = current.rstrip()
        stripped_next = next_line.lstrip()

        # Both lines must be non-empty (no paragraph break between them)
        if stripped_current and stripped_next:
            ends_open = not stripped_current.endswith(SENTENCE_END_CHARS)
            starts_lower = stripped_next[0].islower()
            is_list_item = bool(LIST_PREFIX_RE.match(stripped_next))

            if ends_open and starts_lower and not is_list_item:
                result.append(stripped_current + " " + stripped_next)
                rejoined += 1
                i += 2
                continue

        result.append(current)
        i += 1

    rejoined_text = "\n".join(result)
    metrics["sentences_rejoined"] = rejoined
    metrics["lines_after"] = len(rejoined_text.split("\n"))

    return rejoined_text, metrics


def _is_numbered_line(line: str) -> bool:
    return bool(NUMBERED_LINE_RE.match(line.strip()))


def clean_text_layer3(text: str) -> tuple[str, dict]:
    """Apply Layer 3 editorial cleaning rules.

    3a. Remove lines containing dot leaders (5+ consecutive periods, typical of TOC entries
        like "Introducción .................. 5").
    3b. Remove TOC blocks at the start of the document. A block qualifies if:
        - Located within the first TOC_FIRST_FRACTION of the doc
        - Has >= TOC_MIN_BLOCK_LINES non-empty lines
        - >= TOC_MIN_NUMBERED_RATIO of those lines start with a numbered/list pattern
        - All lines are <= TOC_MAX_LINE_LENGTH chars
        Block 3b is skipped if doc < SHORT_DOC_LINE_THRESHOLD non-empty lines (consistent
        with Capa 2). 3a applies always (dot leaders are unambiguous).

    Returns:
        (cleaned_text, metrics_dict)
    """
    lines = text.split("\n")
    metrics: dict = {
        "dot_leader_lines_removed": 0,
        "toc_blocks_removed": 0,
        "toc_lines_removed": 0,
        "skipped_layer3b_short_doc": False,
    }

    # 3a: remove lines with dot leaders
    after_3a: list[str] = []
    for line in lines:
        if DOT_LEADER_RE.search(line):
            metrics["dot_leader_lines_removed"] += 1
        else:
            after_3a.append(line)
    lines = after_3a

    # 3b: detect and remove TOC blocks at start of doc
    non_empty_count = sum(1 for line in lines if line.strip())
    if non_empty_count < SHORT_DOC_LINE_THRESHOLD:
        metrics["skipped_layer3b_short_doc"] = True
        return "\n".join(lines), metrics

    cutoff = max(int(len(lines) * TOC_FIRST_FRACTION), TOC_MIN_BLOCK_LINES)
    indices_to_remove: set[int] = set()

    i = 0
    while i < cutoff:
        if not lines[i].strip() or not _is_numbered_line(lines[i]):
            i += 1
            continue

        block_indices = [i]
        consecutive_empty = 0
        j = i + 1
        while j < min(cutoff + 200, len(lines)):
            line = lines[j]
            stripped = line.strip()
            if not stripped:
                consecutive_empty += 1
                if consecutive_empty > 1:
                    break
                block_indices.append(j)
                j += 1
                continue
            consecutive_empty = 0
            if len(stripped) > TOC_MAX_LINE_LENGTH:
                break
            block_indices.append(j)
            j += 1

        block_non_empty = [lines[idx] for idx in block_indices if lines[idx].strip()]
        if len(block_non_empty) >= TOC_MIN_BLOCK_LINES:
            numbered_count = sum(1 for line in block_non_empty if _is_numbered_line(line))
            if numbered_count / len(block_non_empty) >= TOC_MIN_NUMBERED_RATIO:
                for idx in block_indices:
                    indices_to_remove.add(idx)
                # Also include preceding TOC header if any (CONTENIDO/ÍNDICE/...)
                prev_idx = i - 1
                while prev_idx >= 0 and not lines[prev_idx].strip():
                    prev_idx -= 1
                if prev_idx >= 0 and TOC_HEADER_RE.match(lines[prev_idx].strip()):
                    for k in range(prev_idx, i):
                        indices_to_remove.add(k)
                metrics["toc_blocks_removed"] += 1
                metrics["toc_lines_removed"] += len(block_non_empty)
        i = j

    final_lines = [
        line for idx, line in enumerate(lines) if idx not in indices_to_remove
    ]
    cleaned_text = "\n".join(final_lines)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", cleaned_text)

    return cleaned_text, metrics


def save_cleaned_text(text: str, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(text, encoding="utf-8")
