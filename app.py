#!/usr/bin/env python3
"""
WA Bitcoiners Vote - Beautiful Results Website
"""

import json
from pathlib import Path
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

DATA_FILE = Path(__file__).parent / "data" / "polls.json"

def load_data():
    return json.loads(DATA_FILE.read_text())

def calculate_monthly(data, month_key, actual_price):
    """Calculate monthly results"""
    participants = data['monthly'][month_key].get('participants', [])
    
    parsed = []
    for p in participants:
        guess = p.get('guess', '')
        # Parse guess
        if '-' in guess or '–' in guess:
            parts = guess.replace('–', '-').split('-')
            try:
                min_val = float(parts[0].replace('$','').replace('k','000').replace('K','000').strip())
                max_val = float(parts[1].replace('$','').replace('k','000').replace('K','000').strip())
                in_range = min_val <= actual_price <= max_val
            except:
                in_range = False
        elif '<' in guess:
            val = float(guess.replace('<','').replace('$','').replace('k','000').replace('K','000').strip())
            in_range = actual_price < val
        else:
            in_range = False
        
        parsed.append({
            'name': p['name'],
            'guess': guess,
            'correct': in_range
        })
    
    return parsed

def get_standings(data):
    """Calculate overall standings"""
    standings = {}
    
    for month, month_data in data.get('monthly', {}).items():
        price = month_data.get('bitcoin_aud_price')
        if price:
            for p in month_data.get('participants', []):
                name = p['name']
                if name not in standings:
                    standings[name] = {'name': name, 'points': 0, 'wins': 0, 'months': []}
                
                # Check if correct
                guess = p.get('guess', '')
                correct = False
                if '-' in guess or '–' in guess:
                    parts = guess.replace('–', '-').split('-')
                    try:
                        min_val = float(parts[0].replace('$','').replace('k','000').replace('K','000').strip())
                        max_val = float(parts[1].replace('$','').replace('k','000').replace('K','000').strip())
                        correct = min_val <= price <= max_val
                    except:
                        pass
                
                if correct:
                    standings[name]['points'] += 3
                    standings[name]['wins'] += 1
                
                standings[name]['months'].append({
                    'month': month_data.get('month', month),
                    'price': price,
                    'guess': guess,
                    'correct': correct
                })
    
    return sorted(standings.values(), key=lambda x: (-x['points'], -x['wins']))

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>WA Bitcoiners Vote 🦞</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
            min-height: 100vh;
            color: #fff;
            padding: 40px 20px;
        }
        
        .container { max-width: 1000px; margin: 0 auto; }
        
        header {
            text-align: center;
            margin-bottom: 50px;
            animation: fadeInDown 0.8s ease;
        }
        
        @keyframes fadeInDown {
            from { opacity: 0; transform: translateY(-20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        h1 {
            font-size: 3rem;
            background: linear-gradient(90deg, #f7931a, #ff6b6b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 10px;
        }
        
        .subtitle { color: #8892b0; font-size: 1.1rem; }
        
        .tabs { display: flex; justify: center; gap: 10px; margin-bottom: 40px; flex-wrap: wrap; }
        
        .tab {
            padding: 12px 30px;
            border: none;
            border-radius: 50px;
            background: rgba(255,255,255,0.1);
            color: #fff;
            cursor: pointer;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        .tab:hover { background: rgba(255,255,255,0.2); }
        .tab.active { background: linear-gradient(90deg, #f7931a, #ff6b6b); }
        
        .section { display: none; animation: fadeIn 0.5s ease; }
        .section.active { display: block; }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        .card {
            background: rgba(255,255,255,0.05);
            border-radius: 20px;
            padding: 30px;
            margin-bottom: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            flex-wrap: wrap;
            gap: 10px;
        }
        
        .card-title { font-size: 1.5rem; color: #f7931a; }
        
        .price-badge {
            background: linear-gradient(90deg, #f7931a, #ff6b6b);
            padding: 8px 20px;
            border-radius: 50px;
            font-weight: bold;
        }
        
        .standings-table {
            width: 100%;
            border-collapse: collapse;
        }
        
        .standings-table th, .standings-table td {
            padding: 15px;
            text-align: left;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .standings-table th {
            color: #8892b0;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.85rem;
            letter-spacing: 1px;
        }
        
        .standings-table tr:hover { background: rgba(255,255,255,0.05); }
        
        .rank { font-size: 1.2rem; font-weight: bold; }
        .rank-1 { color: #ffd700; }
        .rank-2 { color: #c0c0c0; }
        .rank-3 { color: #cd7f32; }
        
        .points { font-size: 1.3rem; font-weight: bold; color: #f7931a; }
        .wins { color: #4ade80; }
        
        .correct-badge {
            background: rgba(74, 222, 128, 0.2);
            color: #4ade80;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
        }
        
        .monthly-result {
            display: flex;
            align-items: center;
            gap: 15px;
            padding: 15px;
            background: rgba(255,255,255,0.03);
            border-radius: 12px;
            margin-bottom: 10px;
        }
        
        .monthly-result .correct { border-left: 4px solid #4ade80; }
        .monthly-result .incorrect { border-left: 4px solid #ff6b6b; }
        
        .guess-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 10px;
        }
        
        .guess-tag {
            background: rgba(247, 147, 26, 0.2);
            color: #f7931a;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 0.9rem;
        }
        
        .yearly-card {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .participant-card {
            background: rgba(255,255,255,0.05);
            border-radius: 16px;
            padding: 20px;
            text-align: center;
            border: 1px solid rgba(255,255,255,0.1);
            transition: transform 0.3s ease, box-shadow 0.3s ease;
        }
        
        .participant-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 40px rgba(247, 147, 26, 0.2);
        }
        
        .participant-name {
            font-size: 1.2rem;
            font-weight: bold;
            margin-bottom: 10px;
        }
        
        .participant-guess {
            font-size: 1.5rem;
            color: #f7931a;
            font-weight: bold;
        }
        
        .footer {
            text-align: center;
            margin-top: 50px;
            color: #8892b0;
            padding: 20px;
        }
        
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: #8892b0;
        }
        
        .empty-state .emoji { font-size: 4rem; margin-bottom: 20px; }
        
        @media (max-width: 768px) {
            h1 { font-size: 2rem; }
            .card { padding: 20px; }
            .standings-table { font-size: 0.9rem; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🦞 WA Bitcoiners Vote</h1>
            <p class="subtitle">Monthly & Yearly Bitcoin Price Predictions</p>
        </header>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('standings')">🏆 Standings</button>
            <button class="tab" onclick="showTab('monthly')">📅 Monthly</button>
            <button class="tab" onclick="showTab('yearly')">🎯 Yearly 2026</button>
        </div>
        
        <div id="standings" class="section active">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">Overall Monthly Standings</h2>
                </div>
                TABLE_STANDINGS
            </div>
        </div>
        
        <div id="monthly" class="section">
            SECTIONS_MONTHLY
        </div>
        
        <div id="yearly" class="section">
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">🎯 2026 Yearly Predictions</h2>
                </div>
                <p style="color: #8892b0; margin-bottom: 20px;">
                    All registered guesses for 2026. Winner revealed December 31, 2026!
                </p>
                <div class="yearly-card">
                    CARDS_YEARLY
                </div>
            </div>
        </div>
        
        <footer class="footer">
            <p>🦞 Built with ⚡ by ClawdPerth</p>
            <p style="font-size: 0.9rem; margin-top: 10px;">
                All predictions in AUD (Australian Dollars)
            </p>
        </footer>
    </div>
    
    <script>
        function showTab(tabId) {
            document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }
    </script>
</body>
</html>
"""

def generate_standings_table(standings):
    rows = ""
    for i, s in enumerate(standings, 1):
        rank_class = f"rank-{i}" if i <= 3 else ""
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        rows += f"""
        <tr>
            <td><span class="rank {rank_class}">{medal}</span></td>
            <td><strong>{s['name']}</strong></td>
            <td class="points">{s['points']} pts</td>
            <td><span class="wins">{s['wins']} correct</span></td>
        </tr>"""
    return f"""
    <table class="standings-table">
        <thead>
            <tr>
                <th>Rank</th>
                <th>Name</th>
                <th>Points</th>
                <th>Correct Guesses</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>""" if rows else "<p class='empty-state'>No results yet</p>"

def generate_monthly_sections(data):
    sections = ""
    for month_key, month_data in data.get('monthly', {}).items():
        price = month_data.get('bitcoin_aud_price')
        if price:
            results = calculate_monthly(data, month_key, price)
            correct = [r for r in results if r['correct']]
            incorrect = [r for r in results if not r['correct']]
            
            html = f"""
            <div class="card">
                <div class="card-header">
                    <h2 class="card-title">📅 {month_data.get('month', month_key)}</h2>
                    <span class="price-badge">${price:,.0f} AUD</span>
                </div>
                <div class="monthly-result correct">
                    <span>🎯</span>
                    <div>
                        <strong>Correct Range</strong>
                        <div class="guess-list">
                            {''.join(f'<span class="guess-tag">{r["name"]}: {r["guess"]}</span>' for r in correct)}
                        </div>
                    </div>
                </div>
                <div class="monthly-result incorrect">
                    <span>❌</span>
                    <div>
                        <strong>Other Guesses</strong>
                        <div class="guess-list">
                            {''.join(f'<span class="guess-tag">{r["name"]}: {r["guess"]}</span>' for r in incorrect)}
                        </div>
                    </div>
                </div>
            </div>"""
            sections += html
    return sections

def generate_yearly_cards(data):
    yearly = data.get('yearly', {}).get('2026', {})
    cards = ""
    for p in yearly.get('participants', []):
        cards += f"""
        <div class="participant-card">
            <div class="participant-name">{p['name']}</div>
            <div class="participant-guess">{p['guess']}</div>
        </div>"""
    return cards

def generate_html(data):
    html = HTML_TEMPLATE
    html = html.replace("TABLE_STANDINGS", generate_standings_table(get_standings(data)))
    html = html.replace("SECTIONS_MONTHLY", generate_monthly_sections(data))
    html = html.replace("CARDS_YEARLY", generate_yearly_cards(data))
    return html

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            data = load_data()
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(generate_html(data).encode())
        else:
            super().do_GET()

if __name__ == "__main__":
    print("🦞 WA Bitcoiners Vote Website")
    print("="*40)
    print("Server running at http://localhost:8000")
    server = HTTPServer(('localhost', 8000), Handler)
    server.serve_forever()
