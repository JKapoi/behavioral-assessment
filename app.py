"""
Behavioural Blueprint Assessment (designed by Sylvia Lyne Njoki)
Shiny for Python app: questionnaire, reflection prompts, automatic scoring and visual results.

Run locally:
    pip install shiny matplotlib pandas numpy
    shiny run --reload app.py
Then open http://127.0.0.1:8000

Deploy: shinyapps.io (rsconnect deploy shiny .), Posit Connect, or any server running `shiny run`.
Saved responses go to responses.csv next to this file (used by the Group dashboard tab).

Emailing results: set these environment variables before starting the app to enable the
"Email my results" button on the Results page (it is hidden otherwise):
    SMTP_HOST       e.g. smtp.gmail.com
    SMTP_PORT       default 587 (STARTTLS); use 465 for implicit SSL
    SMTP_USER       login user (optional if the server does not need auth)
    SMTP_PASSWORD   login password / app password
    SMTP_FROM       sender address (defaults to SMTP_USER)
    SMTP_BCC        optional address(es), comma separated, that get a copy (e.g. the facilitator)
    SMTP_STARTTLS   set to 0 to skip STARTTLS on a non-465 port (local test servers only)
Free text ("Other" answers and the open box) is analysed by text_analysis.py, which must sit in the same folder.
"""

from __future__ import annotations

import asyncio
import html
import io
import random
import os
import re
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from shiny import App, reactive, render, req, ui  # noqa: E402

from text_analysis import STYLE_NAMES, analyse_many, analyse_text, compare_with_scores, top_words  # noqa: E402

# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
SECTIONS = [
    {"key": "A", "style": "Secure", "color": "#2F7D6D", "items": [
        "I find it relatively easy to get emotionally close to others.",
        "I am comfortable depending on people I trust, and having them depend on me.",
        "I don't spend much time worrying about being abandoned or about someone getting \"too close.\"",
        "I feel confident that the people who matter to me will be there when I need them.",
        "I can express my needs and feelings fairly openly in close relationships.",
        "I generally trust that people who care about me don't intend to hurt me.",
        "I'm comfortable both being alone and being close to someone.",
        "Disagreements in a relationship don't make me fear the relationship is ending."]},
    {"key": "B", "style": "Anxious / Preoccupied", "color": "#B7741B", "items": [
        "I often worry that others don't truly love me or won't stay.",
        "I need frequent reassurance that I am loved or valued.",
        "I frequently worry that people close to me will leave or lose interest.",
        "I sometimes want to be extremely close to someone, which can feel overwhelming to them.",
        "I get anxious or upset when someone close to me spends time away from me.",
        "I spend a lot of mental energy worrying about my relationships.",
        "My mood is strongly affected by how a relationship seems to be going.",
        "I notice myself acting \"needy\" or seeking constant contact, even when I don't want to."]},
    {"key": "C", "style": "Avoidant / Dismissive", "color": "#46679A", "items": [
        "I prefer not to depend on others, or have others depend on me.",
        "I feel uncomfortable when someone wants a lot of emotional closeness.",
        "I find it hard to trust others completely, even people close to me.",
        "I place a high value on independence and self-sufficiency over closeness.",
        "I tend to keep my feelings to myself rather than share them with others.",
        "I feel uneasy when a partner or friend wants more closeness than I do.",
        "It's important to me that I don't \"need\" anyone.",
        "I tend to withdraw or create distance when a relationship starts to feel too intense."]},
    {"key": "D", "style": "Disorganized / Fearful-Avoidant", "color": "#8C4A7E", "items": [
        "I want closeness, but I also find it hard to fully trust the people I'm close to.",
        "I sometimes push people away even when part of me wants them near.",
        "My feelings toward someone I'm close to can swing quickly between wanting them near and wanting distance.",
        "I find relationships confusing. I want connection but also fear getting hurt.",
        "I'm often unsure what I actually want from a relationship.",
        "Past experiences make me cautious about opening up, even when I'd like to.",
        "I can feel a strong pull toward someone and an urge to keep them at arm's length at the same time.",
        "I've been told, or sense, that I send mixed signals in close relationships."]},
]
SEC = {s["key"]: s for s in SECTIONS}

PROFILES = {
    "A": ("Generally comfortable with intimacy and independence. Trusts others, communicates needs directly, recovers well from conflict.",
          "Build on existing strengths; may still benefit from deepening self-awareness or navigating a specific relational challenge."),
    "B": ("Craves closeness and reassurance, often fears abandonment, may over-monitor a relationship's status.",
          "Building internal security and self-soothing skills, tolerating uncertainty, distinguishing anxiety-driven thoughts from present reality."),
    "C": ("Values independence, may minimize the importance of close relationships, uncomfortable with vulnerability.",
          "Building tolerance for closeness and interdependence, practicing sharing feelings and needs, recognizing withdrawal patterns."),
    "D": ("Wants closeness but also fears it, often linked to past relational hurt. May oscillate between pursuing and withdrawing.",
          "Building safety and predictability, slowing down reactive patterns, working with self-compassion around the push-pull dynamic."),
}

LIKERT = {"1": "1 Strongly disagree", "2": "2 Disagree", "3": "3 Neutral", "4": "4 Agree", "5": "5 Strongly agree"}
OTHER = "__other__"

# Each option: (text, style key it echoes; "" = none)
REFLECT = [
    ("R1", "Depending on people usually leads to...", [
        ("Feeling supported and closer to them", "A"), ("Worrying about whether they will still be there", "B"),
        ("Losing my independence or feeling trapped", "C"), ("Getting hurt or let down in the end", "D"),
        ("It depends a lot on the person", "A")]),
    ("R2", "When someone gets too close to me, I usually...", [
        ("Welcome it and enjoy the connection", "A"), ("Want even more closeness and reassurance", "B"),
        ("Pull back or need more space", "C"), ("Get busy with work or other things", "C"),
        ("Feel drawn in, then want to push them away", "D")]),
    ("R3", "The hardest thing for me in relationships is...", [
        ("Working through conflict or difficult conversations", "A"), ("Not knowing where I stand", "B"),
        ("Letting someone in and being vulnerable", "C"), ("Trusting that I won't get hurt", "D"),
        ("Asking for what I need", "B")]),
    ("R4", "People usually see me as...", [
        ("Warm and dependable", "A"), ("Caring, but sometimes intense or clingy", "B"),
        ("Independent, private or hard to read", "C"), ("Strong, the one who has it all together", "C"),
        ("Hot and cold, or hard to figure out", "D")]),
    ("R5", "Very few people know that I...", [
        ("Worry a lot about being left or replaced", "B"), ("Find closeness uncomfortable", "C"),
        ("Want closeness but am scared of it", "D"), ("Carry past experiences that still shape how I trust", "D"),
        ("Am more sensitive than I let on", "")]),
    ("R6", "When I feel emotionally unsafe, I tend to...", [
        ("Name it and talk it through", "A"), ("Seek reassurance or reach out repeatedly", "B"),
        ("Shut down or withdraw", "C"), ("Distract myself with work, my phone or keeping busy", "C"),
        ("Swing between reaching out and pulling away", "D")]),
]

DIFFICULTY_PROMPTS = {"R3"}   # "The hardest thing for me..." reverses the meaning of positive phrases

INTRO = (
    "This questionnaire helps you build an understanding of your relational patterns: how you tend to think, "
    "feel and behave in close relationships (romantic partners, close friends, family). It draws on four attachment "
    "styles used widely in coaching and therapeutic contexts: Secure, Anxious (Preoccupied), Avoidant (Dismissive) "
    "and Disorganized (Fearful-Avoidant)."
)
CLOSING = [
    "Thank you for taking the time to complete this questionnaire. Some of these questions may have invited you to "
    "revisit experiences or emotions that aren't always easy to reflect on. Your willingness to do so speaks to your "
    "courage and your commitment to understanding yourself more deeply.",
    "Please remember that this questionnaire is not a measure of your worth, nor is it intended to place you in a box. "
    "It is simply a starting point, a way for us to better understand the patterns you've developed, many of which were "
    "shaped by your experiences and served a purpose at some point in your life.",
    "Every pattern has a story, and every story deserves compassion. My hope is that, through our work together, you'll "
    "gain greater clarity, self-awareness, and practical tools to help you move toward the person you truly are.",
]

EXAMPLE = {"A": [4, 4, 3, 4, 3, 4, 4, 3], "B": [3, 4, 4, 3, 3, 4, 4, 2],
           "C": [2, 2, 3, 3, 4, 2, 2, 3], "D": [3, 2, 3, 3, 2, 4, 3, 2]}

RESPONSES_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "responses.csv")

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# ---------------------------------------------------------------------------
# Email (SMTP settings come from environment variables, see module docstring)
# ---------------------------------------------------------------------------
def smtp_configured() -> bool:
    return bool(os.environ.get("SMTP_HOST") and (os.environ.get("SMTP_FROM") or os.environ.get("SMTP_USER")))


def send_results_email(to: str, name: str, body: str, chart_png: bytes | None, filename: str) -> None:
    """Send the plain-text results summary, with the summary and chart attached. Raises on failure."""
    host = os.environ["SMTP_HOST"]
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER", "")
    sender = os.environ.get("SMTP_FROM") or user
    bcc = [a.strip() for a in os.environ.get("SMTP_BCC", "").split(",") if a.strip()]

    msg = EmailMessage()
    msg["Subject"] = "Your Behavioural Blueprint Assessment results"
    msg["From"] = sender
    msg["To"] = to
    greeting = f"Hello {name},\n\n" if name else "Hello,\n\n"
    msg.set_content(greeting + "Thank you for completing the Behavioural Blueprint Assessment. "
                    "Your results are below and attached.\n\n" + body
                    + "\n\nThis is a self-reflection and conversation-starting tool, "
                      "not a clinical or diagnostic instrument.\n")
    msg.add_attachment(body.encode("utf-8"), maintype="text", subtype="plain", filename=filename)
    if chart_png:
        msg.add_attachment(chart_png, maintype="image", subtype="png", filename="section_totals.png")

    ctx = ssl.create_default_context()
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=30, context=ctx)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
    with server:
        if port != 465 and os.environ.get("SMTP_STARTTLS", "1") != "0":
            server.starttls(context=ctx)
        if user:
            server.login(user, os.environ.get("SMTP_PASSWORD", ""))
        server.send_message(msg, to_addrs=[to, *bcc])


# ---------------------------------------------------------------------------
# Scoring (pure functions)
# ---------------------------------------------------------------------------
def fmt(v: float) -> str:
    """Show whole numbers without decimals and averages to one decimal place."""
    return f"{round(v, 1):g}"


def band(v: float) -> str:
    """Reading aid added in the digital version; the original tool uses the highest total only."""
    return "High" if v >= 28 else "Moderate" if v >= 17 else "Low"


def score(totals: dict[str, int]) -> dict:
    mx = max(totals.values())
    dom = [k for k in "ABCD" if totals[k] == mx]
    elevated = [k for k in "ABCD" if k not in dom and (totals[k] >= 28 or mx - totals[k] <= 3)]
    ranked = sorted("ABCD", key=lambda k: -totals[k])
    notes = []
    if len(dom) > 1:
        notes.append("Your highest totals are tied (" + " and ".join(SEC[k]["style"] for k in dom)
                     + "). The scoring rule gives no single dominant style, so read both profiles together.")
    if totals["B"] >= 28 and totals["C"] >= 28 and "D" not in dom:
        notes.append("Anxious (B) and Avoidant (C) are both high. Wanting closeness while guarding against it is the "
                     "push-pull pattern described under Disorganized / Fearful-Avoidant, so that profile is worth reading too.")
    if "A" in dom and any(totals[k] >= 28 for k in "BCD"):
        notes.append("Secure is highest, but another dimension is also high. This often shows up as a secure base with "
                     "specific situations or relationships that bring out a different pattern.")
    if mx < 17:
        notes.append("All four totals are low, so no dimension stands out strongly. The reflections and a conversation "
                     "may say more than the numbers.")
    gap = totals[ranked[0]] - totals[ranked[1]]
    if len(dom) == 1 and 0 < gap <= 3:
        notes.append(f"Your top two dimensions are only {fmt(gap)} point{'s' if gap != 1 else ''} apart. "
                     f"Treat {SEC[ranked[1]]['style']} as close to equally present.")
    return {"totals": totals, "max": mx, "dominant": dom, "elevated": elevated, "notes": notes}


def reflection_lean(picks: dict[str, tuple]) -> dict[str, int]:
    lean = {k: 0 for k in "ABCD"}
    for rid, _prompt, opts in REFLECT:
        tag = {text: key for text, key in opts}
        for p in picks.get(rid, ()):
            if tag.get(p):
                lean[tag[p]] += 1
    return lean


# ---------------------------------------------------------------------------
# Plots
# ---------------------------------------------------------------------------
INK, MUTED, SOFT, LINE = "#1D2927", "#5D6B68", "#E6EEEB", "#D9E0DD"


def plot_totals(totals: dict[str, int], title: str = ""):
    fig, ax = plt.subplots(figsize=(8, 3.4))
    for lo, hi, lab, a in [(8, 16.5, "Low", .35), (16.5, 27.5, "Moderate", .7), (27.5, 40, "High", 1)]:
        ax.axvspan(lo, hi, color=SOFT, alpha=a, lw=0)
        ax.text((lo + hi) / 2, -0.75, lab, ha="center", va="center", fontsize=9, color=MUTED)
    mx = max(totals.values())
    keys = list("ABCD")
    for i, k in enumerate(keys):
        v = totals[k]
        ax.barh(i, v - 8, left=8, height=.58, color=SEC[k]["color"], alpha=1 if v == mx else .65)
        ax.text(v + .4, i, f"{v:g}", va="center", fontsize=11, fontweight="bold", color=INK)
    ax.set_yticks(range(4), [f"{k} · {SEC[k]['style'].split(' /')[0]}" for k in keys], fontsize=11)
    ax.set_xlim(8, 42)
    ax.set_ylim(3.6, -1.1)
    ax.set_xticks([8, 16, 24, 32, 40])
    ax.tick_params(colors=MUTED, length=0)
    ax.grid(axis="x", color=LINE, lw=.8)
    ax.set_axisbelow(True)
    for s in ax.spines.values():
        s.set_visible(False)
    if title:
        ax.set_title(title, loc="left", fontsize=12, color=INK)
    fig.tight_layout()
    return fig


def plot_items(ans: dict[str, list[int]]):
    fig, ax = plt.subplots(figsize=(8, 2.6))
    for r, k in enumerate("ABCD"):
        base = np.array(matplotlib.colors.to_rgb(SEC[k]["color"]))
        for c, v in enumerate(ans[k]):
            a = .12 + (v - 1) * .22
            col = 1 - a * (1 - base)
            ax.add_patch(plt.Rectangle((c + .06, r + .06), .88, .88, color=col))
            ax.text(c + .5, r + .5, fmt(v), ha="center", va="center", fontsize=10, fontweight="bold",
                    color="white" if v >= 3.5 else INK)
        ax.text(8.35, r + .5, fmt(sum(ans[k])), va="center", fontsize=11, color=INK)
    ax.set_xlim(0, 9)
    ax.set_ylim(4, 0)
    ax.set_xticks([i + .5 for i in range(8)] + [8.6], [str(i + 1) for i in range(8)] + ["Total"])
    ax.set_yticks([i + .5 for i in range(4)], list("ABCD"))
    for t, k in zip(ax.get_yticklabels(), "ABCD"):
        t.set_color(SEC[k]["color"])
        t.set_fontweight("bold")
    ax.xaxis.tick_top()
    ax.tick_params(length=0, colors=MUTED)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# Personal interpretation
# ---------------------------------------------------------------------------
BAND_TEXT = {
    "A": {"High": "You likely feel fairly settled in close relationships: able to get close, lean on people you trust "
                  "and ride out disagreements without fearing the relationship will end.",
          "Moderate": "You have a workable base of trust and openness. It may feel stronger in some relationships, or "
                      "in some seasons of life, than in others.",
          "Low": "Feeling safe, trusting and open in closeness may not come easily right now. That is information, "
                 "not a verdict: security is something people build over time."},
    "B": {"High": "Worry about being loved, left or replaced may take up a lot of your energy, and reassurance may "
                  "feel very important to you.",
          "Moderate": "Some worry about where you stand shows up, probably more when you are stressed or when a "
                      "relationship feels uncertain.",
          "Low": "Fear of being abandoned does not seem to drive much of how you behave in relationships."},
    "C": {"High": "Independence may feel safer than depending on others, and emotional closeness or sharing feelings "
                  "can feel uncomfortable or too intense.",
          "Moderate": "You value your independence and may pull back at times when closeness starts to feel like "
                      "too much.",
          "Low": "Closeness and depending on others do not seem to make you want to pull away."},
    "D": {"High": "You may feel a strong pull toward closeness alongside a fear of being hurt, which can show up as "
                  "reaching out and then pulling away. This pattern often has roots in past relational hurt.",
          "Moderate": "Some mixed feelings about closeness show up, perhaps in particular relationships or under "
                      "pressure.",
          "Low": "Mixed signals and push-pull patterns do not seem to be a strong feature for you."},
}

REFLECT_QUESTIONS = {
    "A": ["Which relationships feel easiest for me, and what makes them feel that way?",
          "In which situations does my sense of security wobble?"],
    "B": ["What story do I tell myself when someone is slow to reply or seems distant?",
          "How can I settle myself before I reach out for reassurance?"],
    "C": ["What happens in my body when someone wants more closeness than I do?",
          "What is one small feeling or need I could share with someone this week?"],
    "D": ["What tends to happen just before I pull away from someone I care about?",
          "What would help a relationship feel safe and predictable for me?"],
}

MIDPOINT = 24  # midpoint of the 8 to 40 section range


def quadrant(b: float, c: float) -> tuple[str, str]:
    """Place a person on the anxiety (B) by avoidance (C) map used in adult attachment research."""
    hi_b, hi_c = b >= MIDPOINT, c >= MIDPOINT
    if not hi_b and not hi_c:
        return "A", "Secure region: low worry about closeness and low discomfort with closeness"
    if hi_b and not hi_c:
        return "B", "Anxious / Preoccupied region: higher worry about closeness, comfortable being close"
    if not hi_b and hi_c:
        return "C", "Avoidant / Dismissive region: low worry, but more discomfort with closeness"
    return "D", "Fearful-Avoidant region: both worry about closeness and discomfort with it are raised"


def item_highlights(ans: dict[str, list[float]]) -> tuple[list, list]:
    """Strengths = Secure statements rated 4+; patterns to notice = B/C/D statements rated 4+."""
    strengths = sorted(((ans["A"][i], SEC["A"]["items"][i]) for i in range(8) if ans["A"][i] >= 4), reverse=True)[:4]
    patterns = sorted(((ans[k][i], SEC[k]["items"][i], k) for k in "BCD" for i in range(8) if ans[k][i] >= 4),
                      key=lambda x: -x[0])[:6]
    return strengths, patterns


def consistency(attempts: list[dict]) -> dict | None:
    if len(attempts) < 2:
        return None
    rng = {k: max(a["totals"][k] for a in attempts) - min(a["totals"][k] for a in attempts) for k in "ABCD"}
    worst = max(rng.values())
    label = ("very consistent" if worst <= 4 else "fairly consistent" if worst <= 8 else "quite variable")
    doms = [" & ".join(score(a["totals"])["dominant"]) for a in attempts]
    same = len(set(doms)) == 1
    return {"range": rng, "label": label, "dominants": doms, "same": same}


def plot_map(points: list[dict], avg: dict | None):
    """Anxiety (B) by avoidance (C) map with each attempt and the average."""
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    regions = [((8, 8), "A", "Secure"), ((MIDPOINT, 8), "C", "Avoidant /\nDismissive"),
               ((8, MIDPOINT), "B", "Anxious /\nPreoccupied"), ((MIDPOINT, MIDPOINT), "D", "Fearful-\nAvoidant")]
    for (x0, y0), k, lab in regions:
        ax.add_patch(plt.Rectangle((x0, y0), 16, 16, color=SEC[k]["color"], alpha=.10, lw=0))
        ax.text(x0 + 8, y0 + (1.4 if y0 == 8 else 14.6), lab, ha="center", va="center", fontsize=10,
                color=SEC[k]["color"], fontweight="bold")
    ax.axvline(MIDPOINT, color=LINE, lw=1)
    ax.axhline(MIDPOINT, color=LINE, lw=1)
    for p in points:
        ax.scatter(p["totals"]["C"], p["totals"]["B"], s=90, color="white", edgecolor=INK, lw=1.5, zorder=3)
        ax.text(p["totals"]["C"], p["totals"]["B"], str(p["n"]), ha="center", va="center", fontsize=8, zorder=4)
    if avg is not None:
        ax.scatter(avg["C"], avg["B"], s=260, marker="*", color=INK, zorder=5)
        ax.annotate("You" if len(points) <= 1 else "Average", (avg["C"], avg["B"]), xytext=(8, 8),
                    textcoords="offset points", fontsize=10, fontweight="bold", color=INK)
    ax.set_xlim(8, 40)
    ax.set_ylim(8, 40)
    ax.set_xticks([8, 16, 24, 32, 40])
    ax.set_yticks([8, 16, 24, 32, 40])
    ax.set_xlabel("Discomfort with closeness (Section C, avoidance)", color=MUTED)
    ax.set_ylabel("Worry about closeness (Section B, anxiety)", color=MUTED)
    ax.tick_params(colors=MUTED, length=0)
    for sp in ax.spines.values():
        sp.set_color(LINE)
    ax.set_aspect("equal")
    fig.tight_layout()
    return fig


def plot_attempts(attempts: list[dict], avg: dict):
    fig, ax = plt.subplots(figsize=(8, 3.2))
    markers = ["o", "s", "^"]
    for i, k in enumerate("ABCD"):
        ax.hlines(i, 8, 40, color=LINE, lw=.8, zorder=1)
        for j, a in enumerate(attempts):
            ax.scatter(a["totals"][k], i, marker=markers[j % 3], s=60, facecolor="white",
                       edgecolor=SEC[k]["color"], lw=1.6, zorder=3, label=f"Attempt {a['n']}" if i == 0 else None)
        ax.scatter(avg[k], i, marker="|", s=500, color=SEC[k]["color"], lw=3, zorder=4,
                   label="Average" if i == 0 else None)
        ax.text(40.8, i, fmt(avg[k]), va="center", fontsize=10, fontweight="bold", color=INK)
    ax.set_yticks(range(4), [f"{k} · {SEC[k]['style'].split(' /')[0]}" for k in "ABCD"])
    ax.set_ylim(3.6, -0.6)
    ax.set_xlim(8, 42.5)
    ax.set_xticks([8, 16, 24, 32, 40])
    ax.tick_params(colors=MUTED, length=0)
    for sp in ax.spines.values():
        sp.set_visible(False)
    leg = ax.legend(loc="upper center", bbox_to_anchor=(.5, -.12), ncol=4, frameon=False, fontsize=9)
    for h in leg.legend_handles:
        try:
            h.set_edgecolor(MUTED)
            h.set_color(MUTED) if h.get_label() == "Average" else None
        except Exception:
            pass
    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
CSS = f"""
body {{ background:#F3F5F3; color:{INK}; }}
h1,h2,h3,h4 {{ font-family: Georgia, 'Times New Roman', serif; }}
.q-card {{ background:#fff; border:1px solid {LINE}; border-radius:10px; padding:12px 16px; margin-bottom:10px; }}
.q-card .shiny-input-radiogroup {{ margin-bottom:0; }}
.q-card .shiny-input-radiogroup > label {{ font-weight:500; margin-bottom:6px; }}
.q-card .radio-inline, .q-card .form-check-inline {{ margin-right:14px; font-size:.9rem; color:{MUTED}; }}
.verdict {{ background:#fff; border:1px solid {LINE}; border-radius:12px; padding:18px 20px; margin:10px 0 18px; }}
.style-name {{ font-family:Georgia,serif; font-size:1.8rem; line-height:1.2; margin:4px 0 10px; }}
.chip {{ display:inline-block; font-size:.8rem; font-weight:600; padding:2px 9px; border-radius:999px;
        border:1px solid currentColor; margin:0 6px 6px 0; }}
.profile {{ background:#fff; border:1px solid {LINE}; border-radius:10px; padding:12px 14px; height:100%; }}
.muted {{ color:{MUTED}; }}
.closing p {{ font-family:Georgia,serif; line-height:1.65; }}
.refl-card {{ background:#fff; border:1px solid {LINE}; border-radius:10px; padding:14px 16px; margin-bottom:12px; }}
.refl-card h5 {{ font-style:italic; font-family:Georgia,serif; }}
"""


def section_panel(sec: dict):
    cards = [
        ui.div(
            ui.input_radio_buttons(f"{sec['key']}{i + 1}", f"{i + 1}. {text}", LIKERT, selected=None, inline=True),
            class_="q-card",
        )
        for i, text in enumerate(sec["items"])
    ]
    nxt = "reflect" if sec["key"] == "D" else chr(ord(sec["key"]) + 1)
    return ui.nav_panel(
        f"Section {sec['key']}",
        ui.h4(f"Section {sec['key']}: rate each statement from 1 to 5"),
        ui.output_ui(f"missing_{sec['key']}"),
        *cards,
        ui.input_action_button(f"next_{sec['key']}", "Next section" if nxt != "reflect" else "Continue to reflection",
                               class_="btn-primary"),
        value=sec["key"],
    )


def reflect_panel():
    blocks = []
    for rid, prompt, opts in REFLECT:
        choices = {t: t for t, _ in opts}
        choices[OTHER] = "Other (write your own)"
        blocks.append(ui.div(
            ui.h5(f"“{prompt}”"),
            ui.input_checkbox_group(rid, None, choices),
            ui.panel_conditional(
                f"input.{rid} && input.{rid}.includes('{OTHER}')",
                ui.input_text_area(f"{rid}_other", None, placeholder="Finish the sentence in your own words",
                                   width="100%", rows=2),
            ),
            class_="refl-card",
        ))
    return ui.nav_panel(
        "Reflection",
        ui.h4("Self-reflection: complete the sentence"),
        ui.p("There isn't a correct answer. Tick every ending that fits, or choose “Other” to write your own. "
             "These answers sit alongside your scores and do not change them.", class_="muted"),
        *blocks,
        ui.div(
            ui.h5("Anything else you would like to share about how you relate to people close to you?"),
            ui.input_text_area("open_text", None, placeholder="Write as much or as little as you like",
                               width="100%", rows=4),
            class_="refl-card",
        ),
        ui.input_action_button("to_results", "See my results", class_="btn-primary"),
        value="reflect",
    )


app_ui = ui.page_navbar(
    ui.nav_panel(
        "Start",
        ui.div(
            ui.h2("Behavioural Blueprint Assessment"),
            ui.p("A reflective tool for behaviour change work. Designed by Sylvia Lyne Njoki.", class_="muted"),
            ui.p(INTRO),
            ui.p("Answer honestly and intuitively, based on how you generally feel across close relationships (not just "
                 "one relationship), rather than how you think you “should” feel. There are no right or wrong "
                 "answers. Allow about 15 to 20 minutes."),
            ui.p(ui.strong("Rating scale: "), "1 Strongly disagree, 2 Disagree, 3 Neutral / Sometimes true, "
                 "4 Agree, 5 Strongly agree."),
            ui.p(ui.strong("Not sure about your answers? "), "You can take the statements up to 3 times. Your final "
                 "result is based on the average of your attempts, and the results page shows how consistent they were."),
            ui.p("This is a self-reflection and conversation-starting tool, not a clinical or diagnostic instrument.",
                 class_="muted"),
            ui.input_text("name", "Your name or initials (optional)"),
            ui.div(
                ui.input_action_button("begin", "Begin Section A", class_="btn-primary"),
                " ",
                ui.input_action_button("example", "Fill with example answers", class_="btn-outline-secondary"),
            ),
            style="max-width:760px",
        ),
        value="start",
    ),
    *[section_panel(s) for s in SECTIONS],
    reflect_panel(),
    ui.nav_panel("Results", ui.output_ui("results"), value="results"),
    ui.nav_panel("Group dashboard", ui.output_ui("dashboard"), value="dashboard"),
    title="Behavioural Blueprint",
    id="nav",
    header=ui.tags.style(CSS),
    fillable=False,
)


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------
def server(input, output, session):
    saved_flag = reactive.value(0)   # bump to refresh the dashboard after saving

    def answers() -> dict[str, list]:
        out = {}
        for s in SECTIONS:
            vals = []
            for i in range(8):
                v = input[f"{s['key']}{i + 1}"]()
                vals.append(int(v) if v not in (None, "") else None)
            out[s["key"]] = vals
        return out

    def missing(key: str) -> list[int]:
        return [i + 1 for i, v in enumerate(answers()[key]) if v is None]

    def picks() -> dict[str, tuple]:
        return {rid: tuple(p for p in (input[rid]() or ()) if p != OTHER) for rid, _, _ in REFLECT}

    def others() -> dict[str, str]:
        return {rid: (input[f"{rid}_other"]() or "").strip() if OTHER in (input[rid]() or ()) else ""
                for rid, _, _ in REFLECT}

    # ---- navigation ----
    @reactive.effect
    @reactive.event(input.begin)
    def _begin():
        ui.update_navset("nav", selected="A")

    def make_next(key: str):
        nxt = "reflect" if key == "D" else chr(ord(key) + 1)

        @reactive.effect
        @reactive.event(input[f"next_{key}"])
        def _go():
            if not missing(key):
                ui.update_navset("nav", selected=nxt)
            else:
                ui.notification_show(f"Section {key}: rate statement(s) {', '.join(map(str, missing(key)))} to continue.",
                                     type="warning", duration=4)

    for s in SECTIONS:
        make_next(s["key"])

    def make_missing(key: str):
        @output(id=f"missing_{key}")
        @render.ui
        def _m():
            n = 8 - len(missing(key))
            return ui.p(f"{n} of 8 answered", class_="muted")

    for s in SECTIONS:
        make_missing(s["key"])

    def signal_chips(an):
        if not an or not an["evidence"]:
            return ui.p("No clear style signals in this answer.", class_="muted", style="font-size:.85rem")
        chips_html = "".join(f"<span class='chip' style='color:{SEC[k]['color']}'>{STYLE_NAMES[k]}: \u201c{html.escape(ph)}\u201d</span>"
                       for k, ph in an["evidence"])
        return ui.div(ui.HTML(chips_html), style="margin-top:4px")

    def free_text_block(r):
        tx = r["text"]
        if tx["words"] == 0:
            return ui.div(
                ui.h4("Free-text analysis", style="margin-top:18px"),
                ui.p("No free text was written. Choosing \u201cOther\u201d or using the open box gives the analysis more "
                     "to work with.", class_="muted"))
        la, lt = r["lean_all"], r["lean_text"]
        rows = "".join(
            f"<tr><td style='color:{SEC[k]['color']};font-weight:600'>{SEC[k]['style']}</td>"
            f"<td>{r['lean'][k]}</td><td>{lt[k]}</td><td><b>{la[k]}</b></td></tr>" for k in "ABCD")
        themes = "".join(f"<span class='chip' style='color:{INK}'>{th} ({html.escape(', '.join(h))})</span>"
                         for th, h in tx["themes"].items()) or "<span class='muted'>No recurring themes detected.</span>"
        parts = [
            ui.h4("Free-text analysis", style="margin-top:18px"),
            ui.p(f"{tx['words']} words of free text analysed. Each signal quotes the words that triggered it. The rules are "
                 "simple keyword patterns with negation handling, so treat them as prompts to check with the person, "
                 "not as conclusions.", class_="muted"),
        ]
        if r["open"]:
            parts += [ui.p(ui.strong("Open answer: "), r["open"]), signal_chips(r["per_text"].get("OPEN"))]
        parts += [
            ui.h5("Relational themes mentioned", style="margin-top:12px"),
            ui.HTML(themes),
            ui.h5("Reflection signals by style", style="margin-top:12px"),
            ui.HTML("<table class='table table-sm' style='max-width:560px'><thead><tr><th>Style</th>"
                    "<th>Endings ticked</th><th>Free text</th><th>Combined</th></tr></thead><tbody>"
                    + rows + "</tbody></table>"),
        ]
        if r["agreement"]:
            parts.append(ui.p(ui.strong(r["agreement"])))
        return ui.div(*parts)

    @reactive.effect
    @reactive.event(input.to_results)
    def _to_results():
        ui.update_navset("nav", selected="results")

    @reactive.effect
    @reactive.event(input.example)
    def _example():
        rng = random.Random()
        for k, vals in EXAMPLE.items():
            for i, v in enumerate(vals):
                v2 = min(5, max(1, v + rng.choice([-1, 0, 0, 0, 1])))   # small variation between attempts
                ui.update_radio_buttons(f"{k}{i + 1}", selected=str(v2))
        demo = {"R1": [REFLECT[0][2][1][0]], "R2": [REFLECT[1][2][0][0]], "R3": [REFLECT[2][2][1][0], OTHER],
                "R4": [REFLECT[3][2][1][0]], "R5": [REFLECT[4][2][4][0]], "R6": [REFLECT[5][2][1][0]]}
        for rid, sel in demo.items():
            ui.update_checkbox_group(rid, selected=sel)
        ui.update_text_area("R3_other", value="Staying calm when plans change at the last minute")
        ui.update_navset("nav", selected="reflect")

    # ---- attempts ----
    MAX_ATTEMPTS = 3
    attempts = reactive.value([])   # kept attempts: {"n", "ans", "totals", "time"}

    @reactive.calc
    def live():
        """The attempt currently being filled in, once every statement is rated."""
        a = answers()
        if any(v is None for vals in a.values() for v in vals):
            return None
        if len(attempts()) >= MAX_ATTEMPTS:
            return None
        return {"n": len(attempts()) + 1, "ans": a, "totals": {k: sum(v) for k, v in a.items()}, "kept": False}

    @reactive.calc
    def all_attempts():
        lst = [dict(x, kept=True) for x in attempts()]
        if live() is not None:
            lst.append(live())
        return lst

    @reactive.calc
    def reflections():
        oth = others()
        open_txt = (input.open_text() or "").strip()
        per_text = {rid: analyse_text(oth[rid], rid in DIFFICULTY_PROMPTS) for rid, _, _ in REFLECT if oth[rid]}
        if open_txt:
            per_text["OPEN"] = analyse_text(open_txt)
        texts = [oth[rid] for rid, _, _ in REFLECT if oth[rid]] + ([open_txt] if open_txt else [])
        flags = [rid in DIFFICULTY_PROMPTS for rid, _, _ in REFLECT if oth[rid]] + ([False] if open_txt else [])
        text_an = analyse_many(texts, flags)
        lean_opts = reflection_lean(picks())
        return {"lean": lean_opts, "lean_text": text_an["styles"],
                "lean_all": {k: lean_opts[k] + text_an["styles"][k] for k in "ABCD"},
                "text": text_an, "per_text": per_text, "open": open_txt, "picks": picks(), "others": oth}

    @reactive.calc
    def result():
        """Final basis: the average of every attempt so far (a single attempt is its own average)."""
        lst = all_attempts()
        if not lst:
            return None
        n = len(lst)
        totals = {k: round(sum(a["totals"][k] for a in lst) / n, 1) for k in "ABCD"}
        ans = {k: [round(sum(a["ans"][k][i] for a in lst) / n, 2) for i in range(8)] for k in "ABCD"}
        sc = score(totals)
        rf = reflections()
        return {"attempts": lst, "n": n, "ans": ans, **sc, **rf,
                "agreement": compare_with_scores(sc["dominant"], rf["lean_all"]),
                "consistency": consistency(lst)}

    def reset_statements():
        for s in SECTIONS:
            for i in range(8):
                ui.update_radio_buttons(f"{s['key']}{i + 1}", choices=LIKERT, selected=None, inline=True)

    @reactive.effect
    @reactive.event(input.keep_retake)
    def _keep_retake():
        lv = live()
        if lv is None:
            return
        attempts.set(attempts() + [{"n": lv["n"], "ans": lv["ans"], "totals": lv["totals"],
                                    "time": datetime.now().strftime("%H:%M")}])
        reset_statements()
        ui.notification_show(f"Attempt {lv['n']} kept. Rate the statements again for attempt {lv['n'] + 1}.",
                             type="message", duration=5)
        ui.update_navset("nav", selected="A")

    @reactive.effect
    @reactive.event(input.keep_finish)
    def _keep_finish():
        lv = live()
        if lv is None:
            return
        attempts.set(attempts() + [{"n": lv["n"], "ans": lv["ans"], "totals": lv["totals"],
                                    "time": datetime.now().strftime("%H:%M")}])
        reset_statements()
        ui.notification_show(f"Attempt {lv['n']} kept. Your final result below uses all your attempts.",
                             type="message", duration=5)

    @reactive.effect
    @reactive.event(input.start_over)
    def _start_over():
        attempts.set([])
        reset_statements()
        ui.update_navset("nav", selected="A")

    # ---- results page ----
    def attempt_bar(r):
        """Status strip: which attempt this is and what the person can do next."""
        kept = len(attempts())
        lv = live()
        items = []
        if lv is not None:
            msg = (f"You have completed attempt {lv['n']} of up to {MAX_ATTEMPTS}. If you felt unsure about some "
                   "answers, you can keep this attempt and answer the statements again. Your final result will be "
                   "the average of all your attempts.")
            btns = []
            if lv["n"] < MAX_ATTEMPTS:
                btns.append(ui.input_action_button("keep_retake", f"Keep attempt {lv['n']} and retake",
                                                   class_="btn-primary"))
            btns.append(ui.input_action_button("keep_finish", f"Keep attempt {lv['n']} and finish",
                                               class_="btn-outline-primary"))
            items = [ui.p(msg), ui.div(*btns, style="display:flex;gap:8px;flex-wrap:wrap")]
        elif kept:
            done = kept >= MAX_ATTEMPTS
            msg = (f"You have kept {kept} attempt{'s' if kept > 1 else ''}. "
                   + ("That is the maximum. " if done else
                      f"You can still retake the statements (up to {MAX_ATTEMPTS} attempts) from Section A. ")
                   + "The result below is based on the average.")
            items = [ui.p(msg), ui.input_action_button("start_over", "Clear all attempts and start over",
                                                       class_="btn-outline-secondary btn-sm")]
        return ui.div(*items, class_="verdict", style="background:#F7FAF9")

    def verdict_block(r):
        t = r["totals"]
        basis = ("your answers" if r["n"] == 1 else f"the average of your {r['n']} attempts")
        dom_html = " &amp; ".join(f"<span style='color:{SEC[k]['color']}'>{SEC[k]['style']}</span>" for k in r["dominant"])
        chips = "".join(f"<span class='chip' style='color:{SEC[k]['color']}'>{k} · {SEC[k]['style'].split(' /')[0]} "
                        f"{fmt(t[k])}/40 · {band(t[k])}</span>" for k in "ABCD")
        out = [
            ui.p(("Co-dominant tendencies" if len(r["dominant"]) > 1 else "Your dominant tendency")
                 + f", based on {basis}", class_="muted", style="margin:0"),
            ui.div(ui.HTML(dom_html), class_="style-name"),
            ui.HTML(chips),
        ]
        if r["elevated"]:
            out.append(ui.p(ui.HTML("Also elevated: " + ", ".join(
                f"<b style='color:{SEC[k]['color']}'>{SEC[k]['style']}</b> ({fmt(t[k])})" for k in r["elevated"])
                + ". It is common and expected for more than one dimension to be raised.")))
        out += [ui.p(n, style="font-size:.95rem") for n in r["notes"]]
        return ui.div(*out, class_="verdict")

    def attempts_block(r):
        if r["n"] < 2:
            return None
        c = r["consistency"]
        head = "".join(f"<th style='color:{SEC[k]['color']}'>{k} {SEC[k]['style'].split(' /')[0]}</th>" for k in "ABCD")
        rows = "".join(
            f"<tr><td>Attempt {a['n']}{'' if a.get('kept') else ' (not yet kept)'}</td>"
            + "".join(f"<td>{a['totals'][k]}</td>" for k in "ABCD")
            + "<td>" + " & ".join(STYLE_NAMES[x] for x in score(a["totals"])["dominant"]) + "</td></tr>"
            for a in r["attempts"])
        rows += ("<tr style='font-weight:700;border-top:2px solid #999'><td>Average</td>"
                 + "".join(f"<td>{fmt(r['totals'][k])}</td>" for k in "ABCD")
                 + f"<td>{' & '.join(SEC[x]['style'].split(' /')[0] for x in r['dominant'])}</td></tr>")
        rng = ", ".join(f"{SEC[k]['style'].split(' /')[0]} {fmt(c['range'][k])}" for k in "ABCD")
        stable = ("Your dominant style was the same in every attempt, which makes the result more dependable."
                  if c["same"] else
                  "Your dominant style changed between attempts. That usually means two patterns are close in "
                  "strength, or that your answers depend on which relationship you had in mind. The average is the "
                  "fairer reading, and the difference is worth talking through.")
        return ui.div(
            ui.h4("Your attempts"),
            ui.HTML("<table class='table table-sm' style='max-width:720px'><thead><tr><th></th>" + head
                    + "<th>Highest</th></tr></thead><tbody>" + rows + "</tbody></table>"),
            ui.output_plot("attempts_plot", height="300px"),
            ui.p(ui.strong(f"Your answers were {c['label']} across attempts. "),
                 f"Largest change per section (points): {rng}. {stable}"),
        )

    def understanding_block(r):
        t = r["totals"]
        qk, qtext = quadrant(t["B"], t["C"])
        strengths, patterns = item_highlights(r["ans"])
        ordered = sorted("ABCD", key=lambda k: -t[k])
        reading = [ui.div(
            ui.p(ui.strong(f"{SEC[k]['style']} · {fmt(t[k])}/40 · {band(t[k])}"),
                 style=f"color:{SEC[k]['color']};margin:0"),
            ui.p(BAND_TEXT[k][band(t[k])], style="margin:2px 0 10px"),
        ) for k in ordered]
        map_note = (f"On this map you sit in the {qtext.split(':')[0]} ({qtext.split(': ')[1]}). "
                    f"Worry about closeness is {fmt(t['B'])} and discomfort with closeness is {fmt(t['C'])}.")
        if qk not in r["dominant"]:
            map_note += (f" This differs from your highest total ({' & '.join(SEC[k]['style'] for k in r['dominant'])}), "
                         "because the map looks only at Sections B and C. Reading both views together gives the "
                         "fuller picture.")
        s_list = ([ui.tags.li(f"{txt} (rated {fmt(v)})") for v, txt in strengths]
                  or [ui.tags.li("No Secure statement was rated 4 or higher. Look at which ones came closest in "
                                 "the grid above.")])
        p_list = ([ui.tags.li(ui.span(f"{txt} (rated {fmt(v)}, ", ui.span(SEC[k]['style'].split(' /')[0],
                                                                                 style=f"color:{SEC[k]['color']};font-weight:600"), ")"))
                   for v, txt, k in patterns]
                  or [ui.tags.li("None of the Anxious, Avoidant or Disorganized statements were rated 4 or higher.")])
        qs = [q for k in r["dominant"] for q in REFLECT_QUESTIONS[k]]
        return ui.div(
            ui.h4("Understanding your scores", style="margin-top:18px"),
            ui.p("What each score may mean for you, from strongest to weakest:", class_="muted"),
            *reading,
            ui.h4("Where you sit on the attachment map", style="margin-top:18px"),
            ui.p("Adult attachment research often describes people on two dimensions: how much they worry about "
                 "closeness (anxiety) and how uncomfortable they are with it (avoidance). This map uses your Section B "
                 "and Section C totals for those two dimensions. The lines mark the midpoint of the scale (24). "
                 "It is an interpretive aid added to this digital version.", class_="muted"),
            ui.output_plot("map_plot", height="440px"),
            ui.p(map_note),
            ui.layout_columns(
                ui.div(ui.h5("Strengths to build on"), ui.tags.ul(*s_list), class_="profile"),
                ui.div(ui.h5("Patterns worth noticing"), ui.tags.ul(*p_list), class_="profile"),
                col_widths=(6, 6),
            ),
            ui.div(ui.h5("Questions to sit with"), ui.tags.ul(*[ui.tags.li(q) for q in qs]),
                   class_="profile", style="margin-top:12px"),
        )

    @render.ui
    def results():
        r = result()
        if r is None:
            gaps = [f"Section {k}: {', '.join(map(str, missing(k)))}" for k in "ABCD" if missing(k)]
            return ui.div(ui.h4("Almost there"), ui.p("Rate every statement to see your results. Still to answer:"),
                          ui.tags.ul(*[ui.tags.li(g) for g in gaps]))
        t = r["totals"]
        profiles = []
        for s in SECTIONS:
            k = s["key"]
            hit, el = k in r["dominant"], k in r["elevated"]
            tag = " · your highest" if hit else " · also elevated" if el else ""
            profiles.append(ui.div(
                ui.p(ui.strong(f"Section {k} · {fmt(t[k])}/40{tag}"), style=f"color:{s['color']};margin:0;font-size:.85rem"),
                ui.h5(s["style"]),
                ui.p(PROFILES[k][0], style="font-size:.93rem"),
                ui.p(ui.strong("Coaching focus: "), PROFILES[k][1], style="font-size:.93rem"),
                class_="profile",
                style=f"border:2px solid {s['color']}" if hit else "",
            ))

        refl_items = []
        for rid, prompt, opts in REFLECT:
            tag = {x: y for x, y in opts}
            chips_r = "".join(
                f"<span class='chip' style='color:{SEC[tag[p]]['color'] if tag.get(p) else MUTED}'>{p}</span>"
                for p in r["picks"][rid])
            body = [ui.HTML(chips_r)] if chips_r else []
            if r["others"][rid]:
                body.append(ui.p(r["others"][rid]))
                body.append(signal_chips(r["per_text"].get(rid)))
            if not body:
                body = [ui.p("Not answered", class_="muted")]
            refl_items.append(ui.div(ui.p(f"“{prompt}”", class_="muted", style="font-style:italic;margin:8px 0 4px"),
                                     *body, style=f"border-bottom:1px solid {LINE};padding-bottom:8px"))
        lean = r["lean"]
        lean_txt = ", ".join(f"{lean[k]} {SEC[k]['style'].split(' /')[0]}" for k in "ABCD" if lean[k])
        title = "Your results" if r["n"] == 1 else f"Your final result (average of {r['n']} attempts)"

        return ui.div(
            ui.h3(title),
            attempt_bar(r),
            verdict_block(r),
            attempts_block(r),
            ui.h4("Section totals"),
            ui.p("Each section ranges from 8 to 40. Shading marks Low (8 to 16), Moderate (17 to 27) and High (28 to 40), "
                 "a reading aid added to this digital version; the original tool scores on the highest total only."
                 + (" Totals shown are averages across your attempts." if r["n"] > 1 else ""), class_="muted"),
            ui.output_plot("totals_plot", height="320px"),
            ui.h4("Item by item"),
            ui.p("Each cell is one statement's rating" + (" (averaged across attempts)" if r["n"] > 1 else "")
                 + ". Darker cells are stronger agreement.", class_="muted"),
            ui.output_plot("items_plot", height="250px"),
            understanding_block(r),
            ui.h4("All four possible outcomes", style="margin-top:18px"),
            ui.p("The section with the highest total generally reflects the dominant style. Attachment style is a "
                 "tendency, not a fixed category, and can vary by relationship or life stage.", class_="muted"),
            ui.layout_columns(*profiles, col_widths=(6, 6, 6, 6)),
            ui.h4("Your reflections", style="margin-top:18px"),
            ui.p("Reflections are answered once and carried across attempts.", class_="muted") if r["n"] > 1 else None,
            ui.p(f"Endings you chose echo these themes: {lean_txt}. This is a prompt for conversation, not a score.",
                 class_="muted") if lean_txt else None,
            *refl_items,
            free_text_block(r),
            ui.div(
                ui.input_action_button("save", "Save my response", class_="btn-primary"),
                " ",
                ui.download_button("download", "Download results (.txt)", class_="btn-outline-secondary"),
                style="margin:18px 0",
            ),
            email_block(),
            ui.div(ui.h4("Before you go"), *[ui.p(p) for p in CLOSING], class_="closing",
                   style=f"border-top:1px solid {LINE};padding-top:14px"),
            style="max-width:900px",
        )

    @render.plot
    def totals_plot():
        r = result()
        req(r)
        return plot_totals(r["totals"])

    @render.plot
    def items_plot():
        r = result()
        req(r)
        return plot_items(r["ans"])

    @render.plot
    def map_plot():
        r = result()
        req(r)
        return plot_map(r["attempts"] if r["n"] > 1 else [], r["totals"])

    @render.plot
    def attempts_plot():
        r = result()
        req(r and r["n"] > 1)
        return plot_attempts(r["attempts"], r["totals"])

    def summary_text(r: dict) -> str:
        t = r["totals"]
        lines = ["Behavioural Blueprint Assessment: results", ""]
        if input.name():
            lines.append(f"Name: {input.name()}")
        lines.append("Based on: " + ("1 attempt" if r["n"] == 1 else f"average of {r['n']} attempts"))
        lines.append(("Co-dominant: " if len(r["dominant"]) > 1 else "Dominant: ")
                     + " & ".join(SEC[k]["style"] for k in r["dominant"]))
        lines.append("")
        for k in "ABCD":
            lines.append(f"Section {k} {SEC[k]['style']}: {fmt(t[k])}/40 ({band(t[k])}). {BAND_TEXT[k][band(t[k])]}")
        if r["elevated"]:
            lines.append("Also elevated: " + ", ".join(SEC[k]["style"] for k in r["elevated"]))
        lines += [""] + r["notes"]
        qk, qtext = quadrant(t["B"], t["C"])
        lines += ["", f"Attachment map (B anxiety {fmt(t['B'])}, C avoidance {fmt(t['C'])}): {qtext}"]
        if r["n"] > 1:
            c = r["consistency"]
            lines += ["", "Attempts"]
            for a in r["attempts"]:
                lines.append(f"Attempt {a['n']}: " + ", ".join(f"{k} {a['totals'][k]}" for k in "ABCD"))
            lines.append(f"Consistency: {c['label']}; dominant style "
                         + ("the same in every attempt" if c["same"] else "changed between attempts"))
        strengths, patterns = item_highlights(r["ans"])
        if strengths:
            lines += ["", "Strengths to build on"] + [f"- {txt} ({fmt(v)})" for v, txt in strengths]
        if patterns:
            lines += ["", "Patterns worth noticing"] + [f"- {txt} ({fmt(v)}, {STYLE_NAMES[k]})" for v, txt, k in patterns]
        lines += ["", "Reflections"]
        for rid, prompt, _ in REFLECT:
            parts = list(r["picks"][rid]) + ([f"Other: {r['others'][rid]}"] if r["others"][rid] else [])
            lines.append(f"{prompt} {'; '.join(parts) if parts else '(not answered)'}")
        if r["open"]:
            lines.append(f"Open answer: {r['open']}")
        tx = r["text"]
        if tx["words"]:
            lines += ["", "Free-text analysis",
                      "Signals: " + ("; ".join(f"{STYLE_NAMES[k]} ('{ph}')" for k, ph in tx["evidence"]) or "none"),
                      "Themes: " + (", ".join(tx["themes"]) or "none"),
                      "Combined reflection lean (ticked + text): "
                      + ", ".join(f"{STYLE_NAMES[k]} {r['lean_all'][k]}" for k in "ABCD")]
            if r["agreement"]:
                lines.append(r["agreement"])
        return "\n".join(lines)

    @render.download(filename=lambda: f"blueprint_results_{datetime.now():%Y%m%d_%H%M}.txt")
    def download():
        r = result()
        req(r)
        yield summary_text(r)

    # ---- email ----
    def email_block():
        if not smtp_configured():
            return None
        return ui.div(
            ui.h4("Email my results"),
            ui.p("Get a copy of this report (summary and chart) in your inbox.", class_="muted"),
            ui.div(
                ui.input_text("email", None, placeholder="you@example.com", width="320px"),
                ui.input_task_button("send_email", "Email my results", label_busy="Sending...",
                                     class_="btn-outline-primary"),
                style="display:flex;gap:10px;align-items:flex-start;flex-wrap:wrap",
            ),
            style="margin:0 0 18px",
        )

    @reactive.extended_task
    async def email_task(to, name, body, png, filename):
        await asyncio.to_thread(send_results_email, to, name, body, png, filename)
        return to

    @reactive.effect
    @reactive.event(input.send_email)
    def _send_email():
        r = result()
        if r is None:
            ui.notification_show("Answer all statements before emailing your results.", type="warning")
            return
        to = (input.email() or "").strip()
        if not EMAIL_RE.match(to):
            ui.notification_show("Please enter a valid email address.", type="warning")
            return
        fig = plot_totals(r["totals"], "Section totals")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=150)
        plt.close(fig)
        email_task(to, (input.name() or "").strip(), summary_text(r), buf.getvalue(),
                   f"blueprint_results_{datetime.now():%Y%m%d_%H%M}.txt")

    @reactive.effect
    def _email_done():
        status = email_task.status()
        if status == "success":
            ui.notification_show(f"Results sent to {email_task.result()}.", type="message")
        elif status == "error":
            try:
                email_task.result()
            except Exception as e:  # noqa: BLE001
                print(f"Email failed: {e!r}", flush=True)
            ui.notification_show("Sorry, the email could not be sent. Please download your results instead.",
                                 type="error", duration=8)

    @reactive.effect
    @reactive.event(input.save)
    def _save():
        r = result()
        if r is None:
            ui.notification_show("Answer all statements before saving.", type="warning")
            return
        row = {"submitted": datetime.now().isoformat(timespec="seconds"), "name": input.name(),
               "attempts": r["n"],
               **{f"total_{k}": r["totals"][k] for k in "ABCD"},          # average across attempts
               "dominant": " & ".join(SEC[k]["style"] for k in r["dominant"]),
               "elevated": ", ".join(SEC[k]["style"] for k in r["elevated"]),
               "map_region": quadrant(r["totals"]["B"], r["totals"]["C"])[1].split(":")[0],
               "consistency": r["consistency"]["label"] if r["consistency"] else "",
               **{f"attempt{a['n']}_{k}": a["totals"][k] for a in r["attempts"] for k in "ABCD"},
               **{f"{k}{i + 1}": v for k in "ABCD" for i, v in enumerate(r["ans"][k])},
               **{rid: "; ".join(r["picks"][rid]) for rid, _, _ in REFLECT},
               **{f"{rid}_other": r["others"][rid] for rid, _, _ in REFLECT},
               "open_text": r["open"],
               **{f"text_{k}": r["lean_text"][k] for k in "ABCD"},
               **{f"reflect_{k}": r["lean_all"][k] for k in "ABCD"},
               "text_themes": "; ".join(r["text"]["themes"]),
               "text_signals": "; ".join(f"{STYLE_NAMES[k]}: {ph}" for k, ph in r["text"]["evidence"])}
        new_df = pd.DataFrame([row])
        if os.path.exists(RESPONSES_CSV):
            new_df = pd.concat([pd.read_csv(RESPONSES_CSV), new_df], ignore_index=True)  # tolerates new columns
        new_df.to_csv(RESPONSES_CSV, index=False)
        saved_flag.set(saved_flag() + 1)
        ui.notification_show("Response saved.", type="message")

    # ---- group dashboard ----
    @reactive.calc
    def group_df():
        saved_flag()
        if not os.path.exists(RESPONSES_CSV):
            return None
        return pd.read_csv(RESPONSES_CSV)

    @render.ui
    def dashboard():
        df = group_df()
        if df is None or df.empty:
            return ui.div(ui.h4("Group dashboard"), ui.p("No saved responses yet. Use “Save my response” on the "
                                                         "Results tab to add one.", class_="muted"))
        counts = {k: int(df["dominant"].fillna("").str.contains(SEC[k]["style"].split(" /")[0], regex=False).sum())
                  for k in "ABCD"}
        rows = "".join(f"<tr><td style='color:{SEC[k]['color']};font-weight:600'>{k} {SEC[k]['style']}</td>"
                       f"<td>{df[f'total_{k}'].mean():.1f}</td><td>{counts[k]}</td>"
                       f"<td>{int((df[f'total_{k}'] >= 28).sum())}</td></tr>" for k in "ABCD")
        return ui.div(
            ui.h4("Group dashboard"),
            ui.p(f"{len(df)} saved response{'s' if len(df) != 1 else ''}. Tied highest totals count toward each tied style.",
                 class_="muted"),
            ui.HTML("<table class='table table-sm' style='max-width:640px'><thead><tr><th>Section</th>"
                    "<th>Average total</th><th>Dominant for</th><th>High (28+) for</th></tr></thead><tbody>"
                    + rows + "</tbody></table>"),
            ui.output_plot("group_plot", height="320px"),
            group_text_block(df),
            ui.download_button("download_all", "Download all responses (.csv)", class_="btn-outline-secondary"),
            style="max-width:900px",
        )

    def group_text_block(df):
        txt_cols = [c for c in df.columns if c.endswith("_other") or c == "open_text"]
        texts = [str(x) for c in txt_cols for x in df[c].dropna() if str(x).strip()]
        if not texts:
            return ui.p("No free text saved yet.", class_="muted")
        an = analyse_many(texts)
        theme_counts = {}
        for x in texts:
            for th in analyse_text(x)["themes"]:
                theme_counts[th] = theme_counts.get(th, 0) + 1
        th_rows = "".join(f"<tr><td>{th}</td><td>{n}</td></tr>"
                          for th, n in sorted(theme_counts.items(), key=lambda kv: -kv[1]))
        words = ", ".join(f"{w} ({n})" for w, n in top_words(texts))
        style_line = ", ".join(f"{STYLE_NAMES[k]} {an['styles'][k]}" for k in "ABCD")
        return ui.div(
            ui.h4("Free text across the group", style="margin-top:18px"),
            ui.p(f"{len(texts)} free-text answers, {an['words']} words. Style signals: {style_line}.", class_="muted"),
            ui.HTML("<table class='table table-sm' style='max-width:520px'><thead><tr><th>Theme</th>"
                    "<th>Answers mentioning it</th></tr></thead><tbody>" + (th_rows or "<tr><td colspan=2>None</td></tr>")
                    + "</tbody></table>"),
            ui.p(ui.strong("Most used words: "), words),
        )

    @render.plot
    def group_plot():
        df = group_df()
        req(df is not None and not df.empty)
        return plot_totals({k: round(float(df[f"total_{k}"].mean()), 1) for k in "ABCD"}, "Average section totals")

    @render.download(filename="blueprint_responses.csv")
    def download_all():
        df = group_df()
        req(df is not None)
        buf = io.StringIO()
        df.to_csv(buf, index=False)
        yield buf.getvalue()


app = App(app_ui, server)
