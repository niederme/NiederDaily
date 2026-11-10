"""Small, conservative source-semantics checks for optional opening prose.

These checks omit a risky paragraph rather than rewrite it. They do not claim
that arbitrary generated prose is factually verified. No source reads or I/O.
"""
from __future__ import annotations

import re

_PICKUP = re.compile(r"\b(?:pick[ -]?ups?|pick(?:ing)?\s+up|collect(?:ing)?)\b", re.I)
_ERRAND = re.compile(r"\b(?:pick[ -]?ups?|pick(?:ing)?\s+up|collect(?:ing)?|errands?|"
                     r"stop(?:ping)?\s+(?:at|by)|swing\s+by|visit|fit\b.{0,35}\bin|"
                     r"grab\b.{0,25}\b(?:way|before|after)|run\s+to)\b", re.I)
_URGENCY = re.compile(r"\b(?:urgent|urgently|priority|prioritize|must|needs?\s+to|"
                      r"can'?t\s+wait|cannot\s+wait|before\s+it|worth\s+(?:a|the)\s+call|"
                      r"don'?t\s+(?:put|leave)|should|ought|time\s+to)\b", re.I)
_AGE = re.compile(r"\b(?:\d+|one|two|three|four|five|six|seven|several|a\s+few)\s+"
                  r"(?:days?|weeks?|months?)\b", re.I)
_ACTIONS = {
    "call": re.compile(r"\b(?:call(?:ing)?|phone|ring|contact(?:ing)?)\b", re.I),
    "order": re.compile(r"\b(?:order(?:ing)?|buy(?:ing)?|purchas(?:e|ing)|refill(?:ing)?)\b", re.I),
    "book": re.compile(r"\b(?:book(?:ing)?|schedul(?:e|ing)|arrang(?:e|ing))\b", re.I),
    "pay": re.compile(r"\b(?:pay(?:ing)?|settle|payment)\b", re.I),
}
_STOP = set("a an the and or at by for of to in on from your you is it its this that with "
            "check reminder task today tomorrow home up pick pickup delivery deliveries package packages "
            "order call review prepare buy book due overdue list store shop".split())


def _tokens(text):
    return {w for w in re.findall(r"[a-z0-9]+", str(text).casefold()) if w not in _STOP and len(w) > 1}


def calendar_kind(event):
    """Source identity is authoritative; a carrier word alone is not."""
    if (event.get("calendar") or "").strip().casefold() == "parcel":
        title = event.get("title") or ""
        ready = re.search(r"\b(?:available|ready) for (?:pickup|collection)\b", title, re.I)
        negated = re.search(r"\b(?:not|isn.t|unavailable)\b", title, re.I)
        return "pickup" if ready and not negated else "delivery"
    if _PICKUP.search(event.get("title") or ""):
        return "pickup"
    return "calendar entry (purpose unconfirmed)"


def package_context(packages):
    """Allowlist already-sanitized fresh display rows, never raw source fields."""
    if not isinstance(packages, dict) or packages.get("freshness") != "fresh":
        return []
    facts = []
    for row in packages.get("shipments", [])[:20]:
        if not isinstance(row, dict):
            continue
        fact = {k: row.get(k) for k in ("company", "item", "carrier_code", "status")}
        expected = row.get("expected_delivery")
        if isinstance(expected, dict):
            fact["expected_delivery"] = {k: expected.get(k) for k in
                                         ("date", "time", "end_date", "end_time", "timezone")}
        facts.append(fact)
    return facts


def opening_rejection(text, events, reminders=None, packages=None):
    """Return a non-private reason for omission, or None. Ambiguity fails closed."""
    deliveries = [e for e in events if calendar_kind(e) == "delivery"]
    pickups = [e for e in events if calendar_kind(e) == "pickup"
               or calendar_kind(e) != "delivery" and _ERRAND.search(e.get("title") or "")]
    facts = package_context(packages)
    delivery_tokens = set().union(*(_tokens(e.get("title", "")) for e in deliveries),
                                 *(_tokens(" ".join(str(v or "") for v in f.values())) for f in facts))
    reminder_rows = [r for bucket in ("today", "overdue", "upcoming")
                     for r in (reminders or {}).get(bucket, []) if isinstance(r, dict)]
    # Keep paragraph-wide checks where a pronoun could refer to an earlier source.
    if deliveries or facts:
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            tokens = _tokens(sentence)
            references_delivery = bool(tokens & delivery_tokens) or bool(re.search(
                r"\b(?:packages?|deliver(?:y|ies)|shipments?|them|those|it|both)\b", sentence, re.I))
            explicit = []
            if _ERRAND.search(sentence):
                explicit = [e for e in pickups if _tokens(e.get("title", "")) & tokens]
                if (not explicit or re.search(r"\b(?:delivery|deliveries|shipments?|packages?)\b", sentence, re.I)
                        or re.search(r"\b(?:two|both|\d+)\s+(?:\w+\s+)?pick[ -]?ups?\b", sentence, re.I)):
                    return "delivery_as_errand"
            # Do not convert an estimated window into a precise appointment.
            if references_delivery and not explicit and re.search(r"\b(?:at|by|for)\s+(?:\d{1,2}(?::\d{2})?\s*(?:a\.?m\.?|p\.?m\.?)?|noon|midnight)\b", sentence, re.I):
                return "delivery_exact_time"
    previous_matching = []
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        matching = [r for r in reminder_rows if _tokens(r.get("title", "")) & _tokens(sentence)]
        if matching:
            previous_matching = matching
        elif previous_matching and (re.search(r"\b(?:it|that|this|them|those|they)\b", sentence, re.I)
                                    or _URGENCY.search(sentence)):
            matching = previous_matching
        else:
            previous_matching = []
            continue
        # Due date alone establishes neither urgency nor age of the underlying need.
        if _AGE.search(sentence):
            return "reminder_inferred_age"
        if _URGENCY.search(sentence):
            return "reminder_inferred_urgency"
        for action in _ACTIONS.values():
            if action.search(sentence) and not all(action.search(r.get("title", "")) for r in matching):
                return "reminder_changed_action"
    return None
