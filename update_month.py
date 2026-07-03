#!/usr/bin/env python3
"""
WA Bitcoiners Vote — Monthly Update Tool

Usage:
    python3 update_month.py <YYYY-MM> <btc_close_usd> <poll_image_path>

Example:
    python3 update_month.py 2026-05 58553 /home/brendon/Dev/wa-bitcoiner-vote/monthly-2026/2026-05.png

What it does:
1. OCR/vision-extract poll participants from the screenshot
2. Apply the standard name changes (Roy→Nuadha, chris scaglioni→chris, etc.)
3. Compute monthly scoring (3pts correct, 1pt closest incorrect)
4. Update data/polls.json
5. Rebuild the May card + full standings table in index.html
6. (Optional, with --push) git add/commit/push to deploy to GitHub Pages

Standard name map lives in NAME_MAP below. Edit it when voters change handles.
"""

from __future__ import annotations
import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.resolve()
DATA_FILE = ROOT / "data" / "polls.json"
INDEX_HTML = ROOT / "index.html"

# ----------------------------------------------------------------------------
# Standard name map
# ----------------------------------------------------------------------------
# When a voter changes handle, add an entry here once and the rest of the
# pipeline (JSON + standings + card) will pick it up everywhere. Keys are
# case-insensitive. Apply in order; later entries win.
#
# History (do not delete — git log + this map are the canonical record):
#   Roy          → Nuadha
#   chris scaglioni → chris
#   Helen        → removed (per repo history)
#   Ayu Sophia   → Ayu
#   Ayu          → Looking Glass
NAME_MAP: dict[str, str] = {
    "roy": "Nuadha",
    "chris scaglioni": "chris",
    "chris_scaglioni": "chris",
    "chrisscaglioni": "chris",
    "ay sophia": "Looking Glass",
    "ayu sophia": "Looking Glass",
    "ayu": "Looking Glass",
}

# Voters who have explicitly left the poll — drop on sight
REMOVED_NAMES: set[str] = {"helen"}

MONTH_NAMES = {
    1: "January", 2: "February", 3: "March", 4: "April",
    5: "May", 6: "June", 7: "July", 8: "August",
    9: "September", 10: "October", 11: "November", 12: "December",
}


def normalize_name(raw: str) -> str:
    """Apply the NAME_MAP + drop REMOVED_NAMES. Raises if the name was removed."""
    cleaned = raw.strip()
    if cleaned.lower() in REMOVED_NAMES:
        raise ValueError(f"name '{cleaned}' is in REMOVED_NAMES — refusing to add")
    return NAME_MAP.get(cleaned.lower(), cleaned)


# ----------------------------------------------------------------------------
# Guess parsing
# ----------------------------------------------------------------------------
def parse_guess(guess: str) -> tuple[Optional[float], Optional[float]]:
    """Return (min, max) range. min/max can be 0 or +inf for open-ended ranges."""
    g = guess.strip().replace("–", "-")
    # Handle "x - y" or "x-y"
    if "-" in g and not g.startswith("<") and not g.startswith(">"):
        parts = g.split("-", 1)
        try:
            lo = _to_dollars(parts[0])
            hi = _to_dollars(parts[1])
            return (lo, hi)
        except ValueError:
            pass
    if g.startswith("<"):
        try:
            return (0.0, _to_dollars(g[1:]))
        except ValueError:
            pass
    if g.startswith(">"):
        try:
            return (_to_dollars(g[1:]), float("inf"))
        except ValueError:
            pass
    # Single value like "$80k"
    try:
        v = _to_dollars(g)
        return (v, v)
    except ValueError:
        pass
    return (None, None)


def _to_dollars(s: str) -> float:
    s = s.strip().replace("$", "").replace(",", "").replace("k", "000").replace("K", "000")
    return float(s)


# ----------------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------------
def score_month(participants: list[dict], actual_price: float) -> dict:
    """Return {correct: [...], closest: [...], others: [...]} with their ranges."""
    parsed = []
    for p in participants:
        lo, hi = parse_guess(p["guess"])
        parsed.append({**p, "guess_min": lo, "guess_max": hi})

    in_range = [p for p in parsed if p["guess_min"] is not None and p["guess_min"] <= actual_price <= p["guess_max"]]
    not_in_range = [p for p in parsed if p not in in_range]

    # Distance from the actual price to a non-correct guess (closest range wins 1pt)
    def diff(p):
        if p["guess_min"] is None:
            return float("inf")
        if actual_price < p["guess_min"]:
            return p["guess_min"] - actual_price
        if actual_price > p["guess_max"]:
            return actual_price - p["guess_max"]
        return 0

    if in_range:
        # Find the closest INCORRECT range from those who missed
        best = min(diff(p) for p in not_in_range) if not_in_range else float("inf")
        closest = [p for p in not_in_range if diff(p) == best]
        others = [p for p in not_in_range if p not in closest]
        return {"correct": in_range, "closest": closest, "others": others, "had_correct": True}

    # No correct guesses — closest range overall wins 1pt
    best = min(diff(p) for p in parsed) if parsed else float("inf")
    closest = [p for p in parsed if diff(p) == best]
    others = [p for p in parsed if p not in closest]
    return {"correct": [], "closest": closest, "others": others, "had_correct": False}


def format_range(p: dict) -> str:
    """Render a range the way the poll image does: $60k - $75k, < $90k, > $120k.

    Falls back to $60,000 - $75,000 only when the value isn't a clean 'k' round number
    (e.g. a weird half-bracket from a malformed parse).
    """
    if p["guess_min"] is None:
        return p["guess"]

    def k_form(v: float) -> str:
        if v == float("inf"):
            return "inf"
        # Round to nearest int and check divisibility by 1000 to decide k vs full $
        iv = int(round(v))
        if iv > 0 and iv % 1000 == 0:
            return f"${iv // 1000}k"
        return f"${iv:,}"

    lo, hi = p["guess_min"], p["guess_max"]
    if hi == float("inf"):
        return f"> {k_form(lo)}"
    if lo == 0:
        return f"< {k_form(hi)}"
    return f"{k_form(lo)} - {k_form(hi)}"


def points_for_month(month_data: dict) -> list[dict]:
    """Return [{name, points, correct}] for each participant in a month."""
    price = month_data.get("bitcoin_usd_price")
    if not price:
        return []
    scored = score_month(month_data.get("participants", []), price)
    out = []
    for p in scored["correct"]:
        out.append({"name": p["name"], "points": 3, "correct": True})
    for p in scored["closest"]:
        out.append({"name": p["name"], "points": 1, "correct": False})
    for p in scored["others"]:
        out.append({"name": p["name"], "points": 0, "correct": False})
    return out


# ----------------------------------------------------------------------------
# Standings
# ----------------------------------------------------------------------------
def overall_standings(data: dict) -> list[dict]:
    """Aggregate points + correct-guesses across all months for every voter."""
    agg: dict[str, dict] = {}
    for month_data in data.get("monthly", {}).values():
        for row in points_for_month(month_data):
            name = row["name"]
            if name not in agg:
                agg[name] = {"name": name, "points": 0, "correct": 0}
            agg[name]["points"] += row["points"]
            if row["correct"]:
                agg[name]["correct"] += 1
    return sorted(agg.values(), key=lambda x: (-x["points"], -x["correct"], x["name"].lower()))


# ----------------------------------------------------------------------------
# Poll image → participants (vision via the CLI's native vision)
# ----------------------------------------------------------------------------
# This script does NOT call the vision model directly — the orchestrator does
# that pass and feeds the participants into update_month.py via a small JSON
# payload, OR the participants are hand-typed into the polls.json directly.
# The function below is a pure-data ingestion helper.

def load_participants_from_json(path: Path) -> list[dict]:
    """Read a participants list from a JSON file like [{"name": "Bren", "guess": "$60k-$75k"}, ...]"""
    data = json.loads(path.read_text())
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "participants" in data:
        return data["participants"]
    raise ValueError(f"Unexpected participants JSON shape in {path}")


# ----------------------------------------------------------------------------
# Polls.json update
# ----------------------------------------------------------------------------
def upsert_month(data: dict, month_key: str, btc_price: float, participants: list[dict]) -> dict:
    """Insert/replace the month entry. Applies NAME_MAP. Recomputes correct_range/notes."""
    normalized = []
    for p in participants:
        try:
            normalized.append({"name": normalize_name(p["name"]), "guess": p["guess"].strip()})
        except ValueError as e:
            print(f"  ⚠ {e}", file=sys.stderr)
    year, month = int(month_key[:4]), int(month_key[5:7])
    month_label = f"{MONTH_NAMES[month]} {year}"

    # Score to compute correct_range and notes
    scored = score_month(normalized, btc_price)
    if scored["had_correct"]:
        cr = format_range(scored["correct"][0])
        winners = ", ".join(p["name"] for p in scored["correct"])
        notes = (
            f"Price was ${btc_price:,.0f} USD. {winners} guessed {cr} (CORRECT - 3pts each)."
        )
        if scored["closest"]:
            closest_range = format_range(scored["closest"][0])
            closest_names = ", ".join(p["name"] for p in scored["closest"])
            notes += f" {closest_names} guessed {closest_range} (closest incorrect - 1pt each)."
        others = scored["others"]
        if others:
            notes += " Others (0pts)."
    else:
        cr = format_range(scored["closest"][0]) if scored["closest"] else "N/A"
        closest_names = ", ".join(p["name"] for p in scored["closest"])
        notes = (
            f"Price was ${btc_price:,.0f} USD — fell in a bracket no one picked. "
            f"{closest_names} guessed {cr} (closest incorrect - 1pt each). Others (0pts)."
        )

    data.setdefault("monthly", {})
    data["monthly"][month_key] = {
        "month": month_label,
        "bitcoin_usd_price": btc_price,
        "participants": normalized,
        "correct_range": cr,
        "notes": notes,
    }
    return data


# ----------------------------------------------------------------------------
# index.html regen
# ----------------------------------------------------------------------------
def render_standings_table(standings: list[dict], header_label: str) -> str:
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    rows = []
    for i, s in enumerate(standings, 1):
        if i in medals:
            medal = f'<span class="rank-{i}">{medals[i]}</span>'
        else:
            medal = f"{i}."
        pts_label = "pt" if s["points"] == 1 else "pts"
        rows.append(
            f'<tr><td>{medal}</td><td><strong>{s["name"]}</strong></td>'
            f'<td class="points">{s["points"]} {pts_label}</td>'
            f'<td><span class="wins">{s["correct"]} correct</span></td></tr>'
        )
    rows_html = "\n                    ".join(rows)
    return f"""<div class="card">
                <div class="card-header">
                    <h2 class="card-title">Overall Standings ({header_label})</h2>
                </div>
                <table>
                    <thead>
                        <tr>
                            <th>Rank</th>
                            <th>Name</th>
                            <th>Points</th>
                            <th>Correct</th>
                        </tr>
                    </thead>
                    <tbody>
                    {rows_html}
                    </tbody>
                </table>
            </div>"""


def render_month_card(month_key: str, month_data: dict) -> str:
    price = month_data["bitcoin_usd_price"]
    month_label = month_data["month"]
    scored = score_month(month_data["participants"], price)
    cr = month_data.get("correct_range", format_range(scored["correct"][0]) if scored["correct"] else (format_range(scored["closest"][0]) if scored["closest"] else "N/A"))

    if scored["correct"]:
        correct_section = f"""<div class="result-row correct">
                    <span style="font-size: 1.5rem;">🎯</span>
                    <div>
                        <strong style="color: #4ade80;">Correct: {cr}</strong>
                        <div style="margin-top: 10px;">
                            {''.join(f'<span class="correct-tag">{p["name"]}</span>' for p in scored["correct"])}
                        </div>
                    </div>
                </div>"""
        closest_section = ""
        if scored["closest"]:
            closest_range = format_range(scored["closest"][0])
            closest_section = f"""<div class="result-row closest">
                    <span style="font-size: 1.5rem;">📍</span>
                    <div>
                        <strong style="color: #ffb84d;">Closest Incorrect: {closest_range}</strong>
                        <div style="margin-top: 10px;">
                            {''.join(f'<span class="closest-tag">{p["name"]}</span>' for p in scored["closest"])}
                        </div>
                    </div>
                </div>"""
    else:
        correct_section = ""
        closest_range = format_range(scored["closest"][0]) if scored["closest"] else "N/A"
        closest_section = f"""<div class="result-row closest">
                    <span style="font-size: 1.5rem;">📍</span>
                    <div>
                        <strong style="color: #ffb84d;">Closest Incorrect: {closest_range}</strong>
                        <div style="margin-top: 10px;">
                            {''.join(f'<span class="closest-tag">{p["name"]}</span>' for p in scored["closest"])}
                        </div>
                    </div>
                </div>"""

    other_tags = ""
    others_to_show = scored["others"]
    for p in others_to_show:
        other_tags += f'<span class="guess-tag">{p["name"]}: {p["guess"]}</span>'

    incorrect_section = ""
    if other_tags:
        incorrect_section = f"""<div class="result-row incorrect">
                    <span style="font-size: 1.5rem;">❌</span>
                    <div>
                        <strong>Other Guesses</strong>
                        <div style="margin-top: 10px;">{other_tags}</div>
                    </div>
                </div>"""

    return f"""<!-- {month_label} -->
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">📅 {month_label}</h2>
                    <span class="price-badge">${price:,.0f} USD</span>
                </div>
                {correct_section}
                {closest_section}
                {incorrect_section}
            </div>"""


def regenerate_index_html(data: dict, header_label: str) -> None:
    """Rewrite the standings block and the monthly card list inside index.html.

    Strategy: surgical replacement of three markers:
      • The standings <div class="card"> block (between <div id="standings"> and </div> boundaries)
      • Each individual month card between <!-- MONTH_LABEL --> markers
      • New month cards inserted at the top of the <div id="monthly"> section
    """
    html = INDEX_HTML.read_text()

    # Standings
    standings = overall_standings(data)
    new_standings_block = render_standings_table(standings, header_label)
    # Find the <div id="standings"> ... </div> block (everything up to the next top-level div)
    new_html = re.sub(
        r'(<div id="standings" class="section active">)(.*?)(</div>\s*<div id="monthly")',
        lambda m: m.group(1) + "\n            " + new_standings_block + "\n        " + m.group(3),
        html,
        count=1,
        flags=re.DOTALL,
    )

    # Monthly cards: regenerate all months present in data
    sorted_months = sorted(data["monthly"].keys(), reverse=True)
    monthly_cards = "\n\n".join(render_month_card(k, data["monthly"][k]) for k in sorted_months)

    # Replace between <div id="monthly" class="section"> and </div>\n        <div id="yearly"
    new_html = re.sub(
        r'(<div id="monthly" class="section">)(.*?)(</div>\s*<div id="yearly")',
        lambda m: m.group(1) + "\n            " + monthly_cards + "\n        " + m.group(3),
        new_html,
        count=1,
        flags=re.DOTALL,
    )

    INDEX_HTML.write_text(new_html)
    print(f"  ✓ Wrote {INDEX_HTML}")


# ----------------------------------------------------------------------------
# Git push
# ----------------------------------------------------------------------------
def git_commit_and_push(message: str) -> None:
    subprocess.run(["git", "-C", str(ROOT), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(ROOT), "commit", "-m", message], check=True)
    subprocess.run(["git", "-C", str(ROOT), "push", "origin", "main"], check=True)
    print(f"  ✓ Pushed: {message}")


# ----------------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="WA Bitcoiners Vote monthly updater")
    ap.add_argument("month_key", help="e.g. 2026-05")
    ap.add_argument("btc_price", type=float, help="Closing USD price on the last day of the month")
    ap.add_argument("participants_json", help="Path to a JSON file with [{name, guess}, ...] OR '-' to read from stdin")
    ap.add_argument("--no-commit", action="store_true", help="Update files but skip git commit/push")
    ap.add_argument("--header-label", default=None, help="Standings header text, e.g. 'After May 2026'")
    args = ap.parse_args()

    if args.participants_json == "-":
        participants = json.loads(sys.stdin.read())
    else:
        participants = load_participants_from_json(Path(args.participants_json))

    header_label = args.header_label or f"After {MONTH_NAMES[int(args.month_key[5:7])]} {args.month_key[:4]}"

    data = json.loads(DATA_FILE.read_text())
    data = upsert_month(data, args.month_key, args.btc_price, participants)
    DATA_FILE.write_text(json.dumps(data, indent=2) + "\n")
    print(f"  ✓ Wrote {DATA_FILE}")

    regenerate_index_html(data, header_label)

    if not args.no_commit:
        msg = f"{MONTH_NAMES[int(args.month_key[5:7])]} {args.month_key[:4]}: BTC closed at ${args.btc_price:,.0f} - update monthly card and standings"
        try:
            git_commit_and_push(msg)
        except subprocess.CalledProcessError as e:
            print(f"  ⚠ Git push failed: {e}", file=sys.stderr)

    # Final stdout summary
    print()
    print("=" * 60)
    print(f"📅 {MONTH_NAMES[int(args.month_key[5:7])]} {args.month_key[:4]} — ${args.btc_price:,.0f} USD")
    print("=" * 60)
    for row in points_for_month(data["monthly"][args.month_key]):
        marker = "🎯" if row["correct"] else ("📍" if row["points"] == 1 else "  ")
        print(f"  {marker} {row['name']}: {row['points']} pts{' (correct)' if row['correct'] else ''}")
    print()
    print("📊 OVERALL STANDINGS")
    print("-" * 40)
    for i, s in enumerate(overall_standings(data), 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"  {medal} {i}. {s['name']}: {s['points']} pts ({s['correct']} correct)")


if __name__ == "__main__":
    main()