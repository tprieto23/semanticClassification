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

URL_RE = re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

CREDIT_KEYWORD_RE = re.compile(
    r"^(?:"
    r"Autor(?:es|as|a)?"
    r"|Diseño"
    r"|Editor(?:ial|es)?"
    r"|Edita"
    r"|Edici[óo]n"
    r"|ISBN"
    r"|Coordinaci[óo]n(?:\s+t[ée]cnica)?"
    r"|Revisi[óo]n(?:\s+t[ée]cnica)?"
    r"|Cr[ée]dito[s]?"
    r"|Fotograf[íi]a"
    r"|Ilustraci[óo]n"
    r"|Citar\s+como"
    r"|C[óo]mo\s+citar"
    r"|Equipo(?:\s+t[ée]cnico)?"
    r"|Maquetaci[óo]n"
    r"|Impresi[óo]n"
    r"|Imprenta"
    r"|Dep[óo]sito\s+legal"
    r"|Primera\s+[Ee]dici[óo]n"
    r"|Hecho\s+el\s+[Dd]ep[óo]sito"
    r"|Seguimiento(?:\s+t[ée]cnico)?"
    r"|Editado\s+por"
    r"|Producido\s+por"
    r"|Publicado\s+por"
    r")\s*[:©]",
    re.IGNORECASE,
)
CREDIT_BARE_HEADER_RE = re.compile(
    r"^(?:CR[ÉE]DITOS|AUTORES|AUTORAS|EQUIPO\s+T[ÉE]CNICO|EDITORIAL)\s*$",
    re.IGNORECASE,
)
ACKNOWLEDGMENTS_RE = re.compile(
    r"^\s*(?:AGRADECIMIENTOS?|ACKNOWLEDG[EM]ENTS?|RECONOCIMIENTOS?)\s*$",
    re.IGNORECASE,
)

# 4e: Contact / footer lines
PHONE_RE = re.compile(r"\+\d{1,3}\s*[\(\)\d\s\-]{5,25}")
CONTACT_PREFIX_RE = re.compile(
    r"^(?:T[\s:]?[:.]?|Tel[\s:]?[:.]?|E[\s:]?[:.]?|Email[\s:]?[:.]?|Contacto[\s:]?[:.])",
    re.IGNORECASE,
)
ADDRESS_RE = re.compile(
    r"(?:Calle|Av\.?|Avenida|Jr\.|Jirón)\s*[.\w\s]+#\s*\d+|Of\.?\s*\d+|Oficina\s+\d+",
    re.IGNORECASE,
)
OFFICE_HEADER_RE = re.compile(
    r"^Oficina\s+(?:Regional|Central)\b",
    re.IGNORECASE,
)

# 4f: Template placeholders
TEMPLATE_PLACEHOLDER_RE = re.compile(
    r"Error!\s+(?:Bookmark|Reference\s+source)\s+not\s+(?:defined|found)",
    re.IGNORECASE,
)
TEMPLATE_LINE_RE = re.compile(
    r"^(?:Main\s+Title\s+Subtitle\s+Description|Click\s+here\s+to\s+enter\s+text)\s*$",
    re.IGNORECASE,
)

UPPERCASE_COVER_FIRST_FRACTION = 0.05
UPPERCASE_COVER_MIN_BLOCK = 4
CREDIT_FIRST_FRACTION = 0.15
CREDIT_LAST_FRACTION = 0.05
CREDIT_MIN_KEYWORDS_IN_BLOCK = 2
CREDIT_MAX_GAP_LINES = 3
CREDIT_EXTENSION_MAX_LINES = 50
CREDIT_MAX_NONKEYWORD_LINES = 5
CREDIT_NARRATIVE_MIN_CHARS = 120
CREDIT_NARRATIVE_MIN_PERIODS = 2
ACKNOWLEDGMENTS_MAX_BLOCK_LINES = 50


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
    # Must not be a long sentence (>10 words) — likely narrative content
    # repeated across pages in brochures, not a structural header.
    if len(stripped.split()) > 10:
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


def _is_uppercase_cover_line(line: str) -> bool:
    """A line qualifies as part of an uppercase cover block."""
    stripped = line.strip()
    if not stripped or len(stripped) < 2:
        return False
    letters = "".join(c for c in stripped if c.isalpha())
    if len(letters) < 2:
        return False
    return letters == letters.upper()


def _is_credit_line(line: str) -> bool:
    stripped = line.strip()
    if CREDIT_KEYWORD_RE.match(stripped):
        return True
    if CREDIT_BARE_HEADER_RE.match(stripped):
        return True
    return False


def _is_narrative_paragraph(line: str) -> bool:
    """A line is clearly narrative content (not a credit) if it's long and has multiple sentences."""
    stripped = line.strip()
    if len(stripped) < CREDIT_NARRATIVE_MIN_CHARS:
        return False
    # Count period-like sentence enders
    return stripped.count(".") >= CREDIT_NARRATIVE_MIN_PERIODS


def _is_contact_line(line: str) -> bool:
    """Detect if a line is a contact/footer line (phone, address, email).

    Conservative: only flags short lines that are predominantly contact info.
    """
    stripped = line.strip()
    if not stripped or len(stripped) > 150:
        return False

    has_phone = bool(PHONE_RE.search(stripped))
    has_email = bool(EMAIL_RE.search(stripped))
    has_address = bool(ADDRESS_RE.search(stripped))
    has_contact_prefix = bool(CONTACT_PREFIX_RE.match(stripped))
    has_office_header = bool(OFFICE_HEADER_RE.match(stripped))
    has_pipe = "|" in stripped

    # Case 1: explicit contact prefix + phone/email
    if has_contact_prefix and (has_phone or has_email):
        return True

    # Case 2: office header line (standalone)
    if has_office_header:
        return True

    # Case 3: address line with street + number + office
    if has_address:
        return True

    # Case 4: short line with pipe + phone (typical footer: "Org | +1 234 | email")
    if has_pipe and has_phone:
        return True

    # Case 5: short line that is mostly just a phone number
    if has_phone and len(stripped) < 40:
        return True

    return False


def clean_text_layer4(text: str) -> tuple[str, dict]:
    """Apply Layer 4 editorial cleaning.

    Sub-rules in order:
      4a. Remove URLs and emails (anywhere in text — inline or whole-line)
      4c. Remove uppercase cover blocks at start (first 5%) — ≥4 consecutive UPPERCASE lines
      4b. Remove credit blocks at start (first 15%) or end (last 5%) —
          ≥2 credit-keyword lines within ≤3 lines of each other
      4d. Remove acknowledgments sections — explicit header to next section title
      4e. Remove contact/footer lines (phone, address, email prefixes)
      4f. Remove template placeholders (Error! Bookmark not defined, etc.)
      Final: re-normalize whitespace and collapse 3+ newlines

    4a/4e/4f apply always. 4b/4c/4d skipped if doc < SHORT_DOC_LINE_THRESHOLD lines.

    Returns:
        (cleaned_text, metrics_dict)
    """
    lines = text.split("\n")
    metrics: dict = {
        "urls_removed": 0,
        "emails_removed": 0,
        "uppercase_cover_blocks_removed": 0,
        "uppercase_cover_lines_removed": 0,
        "credit_blocks_removed": 0,
        "credit_lines_removed": 0,
        "acknowledgments_blocks_removed": 0,
        "acknowledgments_lines_removed": 0,
        "contact_lines_removed": 0,
        "template_placeholders_removed": 0,
        "skipped_layer4_short_doc": False,
    }

    # 4a: URLs y emails (always)
    for i, line in enumerate(lines):
        urls = URL_RE.findall(line)
        emails = EMAIL_RE.findall(line)
        if urls:
            metrics["urls_removed"] += len(urls)
            line = URL_RE.sub("", line)
        if emails:
            metrics["emails_removed"] += len(emails)
            line = EMAIL_RE.sub("", line)
        lines[i] = line

    non_empty_count = sum(1 for line in lines if line.strip())
    if non_empty_count < SHORT_DOC_LINE_THRESHOLD:
        metrics["skipped_layer4_short_doc"] = True
        result = _renormalize(lines)
        return result, metrics

    indices_to_remove: set[int] = set()

    # 4c: Uppercase cover blocks (first 5% of doc)
    cutoff_5pct = max(int(len(lines) * UPPERCASE_COVER_FIRST_FRACTION), UPPERCASE_COVER_MIN_BLOCK + 5)
    i = 0
    while i < cutoff_5pct:
        if not _is_uppercase_cover_line(lines[i]):
            i += 1
            continue
        block_indices = [i]
        consecutive_empty = 0
        j = i + 1
        while j < min(cutoff_5pct + 10, len(lines)):
            stripped = lines[j].strip()
            if not stripped:
                consecutive_empty += 1
                if consecutive_empty > 1:
                    break
                block_indices.append(j)
                j += 1
                continue
            consecutive_empty = 0
            if not _is_uppercase_cover_line(lines[j]):
                break
            block_indices.append(j)
            j += 1
        block_non_empty = [lines[idx] for idx in block_indices if lines[idx].strip()]
        if len(block_non_empty) >= UPPERCASE_COVER_MIN_BLOCK:
            for idx in block_indices:
                indices_to_remove.add(idx)
            metrics["uppercase_cover_blocks_removed"] += 1
            metrics["uppercase_cover_lines_removed"] += len(block_non_empty)
        i = j

    # 4b: Credit blocks at start (first 15%) and end (last 5%)
    cutoff_start = int(len(lines) * CREDIT_FIRST_FRACTION)
    cutoff_end_start = int(len(lines) * (1 - CREDIT_LAST_FRACTION))

    def _detect_credit_blocks(scan_start: int, scan_end: int) -> None:
        i = scan_start
        while i < scan_end:
            if i in indices_to_remove or not _is_credit_line(lines[i]):
                i += 1
                continue
            # Phase A — detect core block (≥2 keywords within CREDIT_MAX_GAP_LINES)
            block_start = i
            keyword_count = 1
            last_keyword_idx = i
            block_end = i
            j = i + 1
            while j < min(scan_end, i + 80):
                if j in indices_to_remove:
                    j += 1
                    continue
                stripped = lines[j].strip()
                if not stripped:
                    block_end = j
                    j += 1
                    continue
                if _is_credit_line(lines[j]):
                    keyword_count += 1
                    last_keyword_idx = j
                    block_end = j
                    j += 1
                    continue
                if j - last_keyword_idx <= CREDIT_MAX_GAP_LINES:
                    block_end = j
                    j += 1
                    continue
                break
            if keyword_count < CREDIT_MIN_KEYWORDS_IN_BLOCK:
                i = block_end + 1
                continue
            # Phase B — extend block forward through credit-like lines
            # Stop when we see CREDIT_MAX_NONKEYWORD_LINES consecutive lines without
            # a credit keyword, OR a section title, OR a narrative paragraph
            non_keyword_streak = 0
            k = block_end + 1
            extension_limit = min(scan_end, block_end + 1 + CREDIT_EXTENSION_MAX_LINES)
            while k < extension_limit:
                if k in indices_to_remove:
                    k += 1
                    continue
                stripped = lines[k].strip()
                if not stripped:
                    block_end = k
                    k += 1
                    continue
                if NUMBERED_LINE_RE.match(stripped) or ACKNOWLEDGMENTS_RE.match(stripped):
                    break
                if _is_narrative_paragraph(lines[k]):
                    break
                if _is_credit_line(lines[k]):
                    non_keyword_streak = 0
                    block_end = k
                    k += 1
                    continue
                non_keyword_streak += 1
                if non_keyword_streak >= CREDIT_MAX_NONKEYWORD_LINES:
                    break
                block_end = k
                k += 1
            lines_in_block = 0
            for idx in range(block_start, block_end + 1):
                if idx not in indices_to_remove and lines[idx].strip():
                    lines_in_block += 1
                indices_to_remove.add(idx)
            metrics["credit_blocks_removed"] += 1
            metrics["credit_lines_removed"] += lines_in_block
            i = block_end + 1

    _detect_credit_blocks(0, cutoff_start)
    _detect_credit_blocks(cutoff_end_start, len(lines))

    # 4d: Acknowledgments
    for idx_header in range(len(lines)):
        if idx_header in indices_to_remove:
            continue
        if not ACKNOWLEDGMENTS_RE.match(lines[idx_header].strip()):
            continue
        j = idx_header + 1
        while j < len(lines) and j - idx_header < ACKNOWLEDGMENTS_MAX_BLOCK_LINES:
            stripped = lines[j].strip()
            if not stripped:
                j += 1
                continue
            if _is_uppercase_cover_line(lines[j]) and len(stripped) > 5:
                break
            if NUMBERED_LINE_RE.match(stripped):
                break
            j += 1
        lines_in_block = 0
        for idx in range(idx_header, j):
            if idx not in indices_to_remove and lines[idx].strip():
                lines_in_block += 1
            indices_to_remove.add(idx)
        metrics["acknowledgments_blocks_removed"] += 1
        metrics["acknowledgments_lines_removed"] += lines_in_block

    # 4e: Contact/footer lines (always — short standalone contact info)
    for i, line in enumerate(lines):
        if i in indices_to_remove:
            continue
        if _is_contact_line(line):
            indices_to_remove.add(i)
            metrics["contact_lines_removed"] += 1

    # 4f: Template placeholders (always)
    i = 0
    while i < len(lines):
        if i in indices_to_remove:
            i += 1
            continue
        stripped = lines[i].strip()

        # Remove exact template lines
        if TEMPLATE_LINE_RE.match(stripped):
            indices_to_remove.add(i)
            metrics["template_placeholders_removed"] += 1
            i += 1
            continue

        # Remove inline single-line placeholders
        if TEMPLATE_PLACEHOLDER_RE.search(lines[i]):
            lines[i] = TEMPLATE_PLACEHOLDER_RE.sub("", lines[i])
            metrics["template_placeholders_removed"] += 1
            i += 1
            continue

        # Handle multi-line placeholders: "Error!\nReference source not found."
        if "Error!" in lines[i] and i + 1 < len(lines):
            combined = lines[i].strip() + " " + lines[i + 1].strip()
            if TEMPLATE_PLACEHOLDER_RE.search(combined):
                # Remove the placeholder text from both lines
                lines[i] = lines[i].replace("Error!", "").strip()
                lines[i + 1] = re.sub(
                    r"(?:Bookmark|Reference\s+source)\s+not\s+(?:defined|found)\.?",
                    "",
                    lines[i + 1],
                    flags=re.IGNORECASE,
                ).strip()
                metrics["template_placeholders_removed"] += 1
                # Mark next line for removal if now empty
                if not lines[i + 1].strip():
                    indices_to_remove.add(i + 1)
                if not lines[i].strip():
                    indices_to_remove.add(i)
        i += 1

    final_lines = [
        line for idx, line in enumerate(lines) if idx not in indices_to_remove
    ]
    result = _renormalize(final_lines)
    return result, metrics


def _renormalize(lines: list[str]) -> str:
    """After Layer 4 removals, clean up double spaces and excess newlines."""
    text = "\n".join(lines)
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def save_cleaned_text(text: str, output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(text, encoding="utf-8")
