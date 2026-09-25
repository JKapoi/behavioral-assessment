"""
Free-text analysis for Behavioural Blueprint reflections.

Transparent, rule-based (no AI service, no internet): every match returns the exact
phrase that triggered it, so a coach can see and challenge each inference.

analyse_text(text) -> {
    "styles":   {"A": n, "B": n, "C": n, "D": n},     # style signals found
    "evidence": [(style, phrase), ...],                # the words behind each signal
    "themes":   {"Trust": [phrases], ...},            # cross-cutting relational themes
    "words":    int,
}
Edit STYLE_RULES / THEME_RULES to tune the vocabulary to your clients' language
(including Swahili, Sheng or French terms if useful).
"""

from __future__ import annotations

import re
from collections import Counter

NEGATORS = {"not", "no", "never", "dont", "don't", "doesnt", "doesn't", "didnt", "didn't", "cant", "can't",
            "cannot", "wont", "won't", "isnt", "isn't", "wasnt", "wasn't", "hardly", "rarely", "barely", "unable"}
NEGATING_PHRASES = re.compile(r"\b(struggle to|find it hard to|hard to|hard for me to|difficult to)\s*$")

# (regex, style if affirmed, style if negated or None)
STYLE_RULES = [
    # ---- A Secure ----
    (r"\btalk(ing)? (it |things )?(through|out)\b", "A", "C"),
    (r"\bcommunicat\w*", "A", "C"),
    (r"\b(trust|trusting)\b", "A", "D"),
    (r"\b(feel|feeling|am|being) (safe|secure|supported|comfortable)\b", "A", "D"),
    (r"\b(support|supported|supportive)\b", "A", None),
    (r"\b(rely|depend) on (them|people|others|my)\b", "A", "C"),
    (r"\bwork (it|things) out\b", "A", None),
    (r"\bexpress (my|how i)\b", "A", "C"),
    (r"\b(ask|asking) for (help|what i need|support)\b", "A", "C"),
    (r"\b(open up|opening up|share my feelings|be open)\b", "A", "C"),
    (r"\b(calm|balanced|at ease)\b", "A", None),
    (r"\bclose(r|ness)? (to|with) (them|people|others)\b", "A", "C"),
    # ---- B Anxious / Preoccupied ----
    (r"\babandon\w*", "B", None),
    (r"\b(leave|leaving|left) me\b", "B", None),
    (r"\b(reject\w*|replaced?|forgotten|ignored)\b", "B", None),
    (r"\breassur\w*", "B", None),
    (r"\b(needy|clingy|clingly|desperate)\b", "B", None),
    (r"\b(worry|worried|worrying|overthink\w*|anxious|anxiety|panic\w*)\b", "B", None),
    (r"\bnot (good )?enough\b", "B", None),
    (r"\b(jealous\w*|insecure|insecurity)\b", "B", None),
    (r"\b(lose|losing) (them|people|him|her|my partner)\b", "B", None),
    (r"\b(text|call|message|check)\w* (them |him |her )?(again|constantly|a lot|repeatedly|all the time)\b", "B", None),
    (r"\bwhere i stand\b", "B", None),
    (r"\b(people[- ]pleas\w*|over-?giv\w*)\b", "B", None),
    (r"\b(lonely|loneliness)\b", "B", None),
    # ---- C Avoidant / Dismissive ----
    (r"\b(need|want|take|give me) (some |more |my )?space\b", "C", None),
    (r"\b(withdraw\w*|pull(ing)? (back|away)|shut(ting)? down|go(ing)? quiet|disappear\w*|ghost\w*)\b", "C", None),
    (r"\bindependen\w*", "C", None),
    (r"\b(on my own|by myself|self[- ]relian\w*|self[- ]sufficien\w*)\b", "C", None),
    (r"\bdon'?t need (anyone|anybody|people|them)\b", "C", None),
    (r"\b(suffocat\w*|trapped|smother\w*|overwhelmed by (them|closeness))\b", "C", None),
    (r"\bkeep (it|things|my feelings|feelings|stuff) to myself\b", "C", None),
    (r"\b(distance|detach\w*|numb|emotionless)\b", "C", None),
    (r"\b(keep|stay|get|getting) busy\b", "C", None),
    (r"\b(private|reserved|guarded|closed off|cold)\b", "C", None),
    (r"\b(avoid\w*)\b", "C", None),
    (r"\bweak(ness)?\b", "C", None),
    # ---- D Disorganized / Fearful-Avoidant ----
    (r"\bpush(ing)? (them|people|him|her|others|everyone) away\b", "D", None),
    (r"\b(hot and cold|mixed signals|push[- ]pull|back and forth)\b", "D", None),
    (r"\b(confus\w*|unsure what i want|don'?t know what i want)\b", "D", None),
    (r"\b(scared|afraid|fear|terrified)\b", "D", None),
    (r"\b(hurt|betray\w*|trauma\w*|abuse\w*|cheated)\b", "D", None),
    (r"\bwant\w* (closeness|connection|love|them)\b[^.]{0,40}\bbut\b", "D", None),
    (r"\b(unsafe|unpredictable|chaos|chaotic)\b", "D", None),
    (r"\b(explode|blow up|lash out|freeze|froze|shut off)\b", "D", None),
    (r"\b(sabotag\w*|self[- ]destruct\w*)\b", "D", None),
    (r"\b(past|childhood|growing up)\b", "D", None),
]

THEME_RULES = {
    "Trust": r"\b(trust\w*|betray\w*|cheat\w*|lie|lied|lying|honest\w*|loyal\w*)\b",
    "Fear of abandonment or rejection": r"\b(abandon\w*|leave me|left me|reject\w*|replaced?|lose (them|people)|forgotten|ignored)\b",
    "Need for space and independence": r"\b(space|independen\w*|on my own|alone|by myself|freedom|suffocat\w*|trapped)\b",
    "Conflict and repair": r"\b(conflict|argu\w*|fight\w*|disagree\w*|apolog\w*|forgive\w*|work (it|things) out|resolve)\b",
    "Vulnerability and expression": r"\b(vulnerab\w*|open up|express\w*|share\w*|feelings|emotions?|cry|crying)\b",
    "Past hurt and experiences": r"\b(past|childhood|growing up|parent\w*|father|mother|ex\b|trauma\w*|hurt)\b",
    "Self-worth": r"\b(not (good )?enough|worth\w*|deserv\w*|unlovable|insecur\w*|confiden\w*)\b",
    "Emotional regulation": r"\b(calm|panic\w*|anxious|anxiety|overwhelm\w*|angry|anger|explode|numb|shut down|freeze)\b",
    "Reassurance and contact": r"\b(reassur\w*|text\w*|call\w*|check\w* in|attention|contact)\b",
    "Faith and community": r"\b(god|pray\w*|church|mosque|faith|community|family)\b",
}

STOPWORDS = set("""a an the and or but if so of to in on at for with from by as is am are was were be been being it its
this that these those i me my mine myself you your he him his she her they them their we us our not no do does did
done have has had just very really too also can could would should will shall may might more most much many some any
all what when where who why how than then there here about into over out up down off again only own same such get got
feel feels felt usually tend people someone something things thing lot""".split())

STYLE_NAMES = {"A": "Secure", "B": "Anxious", "C": "Avoidant", "D": "Disorganized"}


def _negated(text: str, start: int) -> bool:
    """True if one of the three words just before the match negates it, within the same clause."""
    window = re.split(r"[.,;!?]|\band\b|\bbut\b|\bso\b", text[max(0, start - 40):start])[-1]
    if NEGATING_PHRASES.search(window):
        return True
    return any(w in NEGATORS for w in re.findall(r"[a-z']+", window)[-3:])


def analyse_text(text: str, difficulty: bool = False) -> dict:
    """difficulty=True for prompts like "The hardest thing for me is...", where a Secure-sounding
    phrase ("staying calm", "trusting people") names a struggle, so it is not counted as Secure."""
    t = (text or "").lower().replace("’", "'")
    styles = {k: 0 for k in "ABCD"}
    evidence: list[tuple[str, str]] = []
    for pattern, style, neg_style in STYLE_RULES:
        for m in re.finditer(pattern, t):
            target = style
            if _negated(t, m.start()):
                if neg_style is None:
                    # a negated B/C/D signal (e.g. "I don't worry") is dropped rather than guessed
                    continue
                target = neg_style
            if difficulty and target == "A":
                continue
            styles[target] += 1
            before = re.findall(r"[\w']+", t[max(0, m.start() - 30):m.start()])[-3:]
            snippet = (" ".join(before) + " " + m.group(0)).strip(" ,.;")
            evidence.append((target, snippet))
    themes = {}
    for name, pattern in THEME_RULES.items():
        hits = [m.group(0) for m in re.finditer(pattern, t)]
        if hits:
            themes[name] = sorted(set(hits))
    return {"styles": styles, "evidence": evidence, "themes": themes, "words": len(re.findall(r"[a-z']+", t))}


def analyse_many(texts: list[str], difficulty_flags: list[bool] | None = None) -> dict:
    """Combine several free-text answers into one summary."""
    difficulty_flags = difficulty_flags or [False] * len(texts)
    styles = {k: 0 for k in "ABCD"}
    evidence, themes = [], {}
    words = 0
    for x, dflag in zip(texts, difficulty_flags):
        r = analyse_text(x, dflag)
        for k in styles:
            styles[k] += r["styles"][k]
        evidence += r["evidence"]
        for th, hits in r["themes"].items():
            themes.setdefault(th, set()).update(hits)
        words += r["words"]
    return {"styles": styles, "evidence": evidence,
            "themes": {k: sorted(v) for k, v in themes.items()}, "words": words}


def top_words(texts: list[str], n: int = 15) -> list[tuple[str, int]]:
    c = Counter(w for x in texts for w in re.findall(r"[a-z']{3,}", (x or "").lower().replace("’", "'"))
                if w not in STOPWORDS)
    return c.most_common(n)


def compare_with_scores(dominant: list[str], lean: dict[str, int]) -> str | None:
    """One-line reading of whether reflections point the same way as the scores."""
    total = sum(lean.values())
    if total == 0:
        return None
    top = max(lean.values())
    lead = [k for k in "ABCD" if lean[k] == top]
    if set(lead) & set(dominant):
        return ("Your reflections point in the same direction as your scores ("
                + " / ".join(STYLE_NAMES[k] for k in lead) + ").")
    return ("Your reflections lean toward " + " / ".join(STYLE_NAMES[k] for k in lead)
            + " while your scores lean toward " + " / ".join(STYLE_NAMES[k] for k in dominant)
            + ". That difference is worth exploring in conversation.")
