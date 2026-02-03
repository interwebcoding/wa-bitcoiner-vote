# 🦞 WA Bitcoiners Vote

A beautiful, modern results website for monthly and yearly Bitcoin price prediction polls.

## Features

- 📊 **Live Standings** - Track overall points across all monthly polls
- 📅 **Monthly Polls** - View detailed results for each month
- 🎯 **Yearly Predictions** - See all registered yearly guesses
- 🏆 **Point System** - 3 points for correct range, 1 point for closest incorrect

## Quick Start

### Option 1: Simple HTML (Static)

Open `index.html` directly in any browser.

### Option 2: Python Server (with live data)

```bash
python3 app.py
# Then open http://localhost:8000
```

## Admin - Adding New Poll Results

1. Open `admin.html` in your browser
2. Select poll type (Monthly/Yearly)
3. Enter the period (e.g., "2026-02" or "2026")
4. Enter the Bitcoin USD price
5. Add all participants and their guesses
6. Click "Generate JSON" and copy to `data/polls.json`

## Data Structure

Edit `data/polls.json` directly:

```json
{
  "monthly": {
    "2025-12": {
      "month": "December 2025",
      "bitcoin_usd_price": 98000,
      "participants": [
        {"name": "Zee", "guess": "$90k - $100k"},
        {"name": "Bren", "guess": "$100k - $120k"}
      ]
    }
  },
  "yearly": {
    "2026": {
      "year": 2026,
      "bitcoin_usd_price": null,
      "participants": [
        {"name": "Bren", "guess": "$150k"}
      ]
    }
  }
}
```

## Screenshots

Store poll screenshots in:
- `images/monthly/` - Monthly poll screenshots
- `images/yearly/` - Yearly poll screenshots

## Point System

**Monthly Polls:**
- 🎯 **3 points** - Guess the correct price range
- 📍 **1 point** - Closest incorrect range

**Yearly Predictions:**
- Winner announced December 31st
- Closest guess wins!

## Files

```
wa-bitcoiner-vote/
├── index.html          # Main results website
├── admin.html          # Admin interface for adding polls
├── app.py             # Python server (optional)
├── calculate_points.py # Point calculation utility
├── data/
│   └── polls.json     # Poll data (edit this!)
├── images/
│   ├── monthly/       # Monthly poll screenshots
│   └── yearly/        # Yearly poll screenshots
└── README.md
```

## Contributing

1. Upload screenshot to `images/monthly/` or `images/yearly/`
2. Extract participant data from screenshot
3. Update `data/polls.json` with new poll results
4. Commit and deploy!

## Built With

- ❤️ HTML/CSS/JavaScript (static, no build required)
- 🐍 Python (optional server)
- 🍃 JSON for data storage

---

**All predictions in USD (US Dollars)**

🦞⚡ Built by ClawdPerth
