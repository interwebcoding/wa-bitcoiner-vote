#!/usr/bin/env python3
"""
WA Bitcoiners Vote - Point Calculator (USD)

Scoring System:
- 3 points for correct price range (actual price falls within their guessed range)
- 1 point for next closest range
"""

import json
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "polls.json"

def parse_guess(guess: str) -> tuple:
    """Parse a guess string into numeric range"""
    guess = guess.strip()
    
    if '-' in guess or '–' in guess:
        parts = guess.replace('–', '-').split('-')
        min_str = parts[0].strip().replace('$', '').replace('k', '000').replace('K', '000').strip()
        max_str = parts[1].strip().replace('$', '').replace('k', '000').replace('K', '000').strip()
        try:
            return (float(min_str), float(max_str))
        except:
            pass
    
    if '<' in guess:
        val = guess.replace('<', '').replace('$', '').replace('k', '000').replace('K', '000').strip()
        try:
            return (0, float(val))
        except:
            pass
    
    if 'k' in guess.lower():
        val = guess.replace('$', '').replace('k', '000').replace('K', '000').strip()
        try:
            val = float(val)
            return (val, val)
        except:
            pass
    
    return (None, None)

def is_in_range(price: float, range_min: float, range_max: float) -> bool:
    if range_min is None or range_max is None:
        return False
    return range_min <= price <= range_max

def calculate_monthly_points(participants: list, actual_price: float) -> dict:
    parsed = []
    for p in participants:
        guess_min, guess_max = parse_guess(p.get('guess', ''))
        parsed.append({
            'name': p['name'],
            'guess': p.get('guess', ''),
            'guess_min': guess_min,
            'guess_max': guess_max,
            'points': 0
        })
    
    correct = [p for p in parsed if is_in_range(actual_price, p['guess_min'], p['guess_max'])]
    
    if correct:
        for p in correct:
            p['points'] = 3
        correct_range = f"${correct[0]['guess_min']:,.0f} - ${correct[0]['guess_max']:,.0f}"
    else:
        correct = []
        closest_diff = float('inf')
        for p in parsed:
            if actual_price < p['guess_min']:
                diff = p['guess_min'] - actual_price
            elif actual_price > p['guess_max']:
                diff = actual_price - p['guess_max']
            else:
                diff = 0
            if diff < closest_diff:
                closest_diff = diff
                correct = [p]
            elif diff == closest_diff:
                correct.append(p)
        for p in correct:
            p['points'] = 3
        if correct:
            correct_range = f"${correct[0]['guess_min']:,.0f} - ${correct[0]['guess_max']:,.0f}"
        else:
            correct_range = "N/A"
    
    return {
        'actual_price': actual_price,
        'correct_range': correct_range,
        'participants': sorted(parsed, key=lambda x: -x['points'])
    }

def get_overall_standings(data: dict) -> list:
    standings = {}
    for month, month_data in data.get('monthly', {}).items():
        price = month_data.get('bitcoin_usd_price')
        if price:
            result = calculate_monthly_points(month_data.get('participants', []), price)
            for p in result['participants']:
                if p['name'] not in standings:
                    standings[p['name']] = {'name': p['name'], 'total_points': 0, 'correct_guesses': 0}
                standings[p['name']]['total_points'] += p['points']
                if p['points'] == 3:
                    standings[p['name']]['correct_guesses'] += 1
    return sorted(standings.values(), key=lambda x: (-x['total_points'], -x['correct_guesses']))

if __name__ == "__main__":
    data = json.loads(DATA_FILE.read_text())
    
    print("="*60)
    print("🦞 WA BITCOINER VOTE - RESULTS (USD)")
    print("="*60)
    
    print("\n📅 DECEMBER 2025")
    print("-"*40)
    dec = data['monthly']['2025-12']
    if dec.get('bitcoin_usd_price'):
        result = calculate_monthly_points(dec['participants'], dec['bitcoin_usd_price'])
        print(f"Bitcoin USD Price: ${result['actual_price']:,.0f}")
        print(f"Correct Range: {result['correct_range']}")
        print(f"\nParticipants:")
        for p in result['participants']:
            emoji = "🎯" if p['points'] == 3 else "  "
            print(f"  {emoji} {p['name']}: {p['guess']} - {p['points']} pts")
    
    print("\n" + "="*60)
    print("📊 MONTHLY STANDINGS")
    print("-"*40)
    standings = get_overall_standings(data)
    for i, s in enumerate(standings, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
        print(f"  {medal} {i}. {s['name']}: {s['total_points']} pts ({s['correct_guesses']} correct)")
    
    print("\n" + "="*60)
    print("🎯 YEARLY 2026 PREDICTIONS (USD)")
    print("-"*40)
    yearly = data['yearly']['2026']
    for p in yearly['participants']:
        print(f"  📌 {p['name']}: {p['guess']}")
    
    print("\n" + "="*60)
