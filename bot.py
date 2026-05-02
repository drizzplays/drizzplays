import os
import json
import gspread
import requests
import time

def calculate_units(odds, tab_name, history_score=None):
    """
    Calculates wager size. 
    -200 is the 'Nuke' ceiling (2u).
    Homeruns are scaled down as lotteries unless stats are extreme.
    """
    # Convert American to Decimal for math if needed, but we'll use American logic
    abs_odds = abs(odds)
    
    # Base sizing: Standard "To Win 1 Unit" logic
    if odds > 0:
        base_wager = 100 / odds
    else:
        base_wager = abs_odds / 100

    # Apply Tab-specific dampeners
    if tab_name == "Batter_Homeruns":
        # HRs are lotteries. We wager to win 0.25u - 0.5u usually.
        # If history_score is extreme (e.g., 2 HR in last few games), we bump to 0.75u
        multiplier = 0.5 if (history_score and history_score >= 80) else 0.2
        wager = base_wager * multiplier
    else:
        # Standard Props
        wager = base_wager

    # Hard Cap: No bet > 2 units. 
    # If odds are -200, wager is 2.0. This is our 'Nuke' limit.
    if wager > 2.0:
        wager = 2.0
        
    return round(wager, 2)

def send_discord(content):
    url = os.environ['DISCORD_WEBHOOK_URL']
    requests.post(url, json={"content": content})
    time.sleep(1) # Prevent rate limiting

def process_bot():
    creds = json.loads(os.environ['GOOGLE_SHEETS_CREDS'])
    gc = gspread.service_account_from_dict(creds)
    sh = gc.open_by_key(os.environ['SHEET_ID'])

    tabs = [
        "Batter_Homeruns", "Batter_Hits", "Batter_HitsRunsRbis",
        "Strikeouts", "Pitcher Walks", "Pitcher Earned Runs", 
        "Pitcher Outs Recorded", "NRFI Props"
    ]

    for tab in tabs:
        try:
            ws = sh.worksheet(tab)
            records = ws.get_all_records()
            
            for row in records:
                tier = str(row.get('Tier', '')).lower()
                try:
                    odds = int(row.get('Odds', 0))
                except: continue

                # REQUIREMENT: Green Tier and Odds >= -200 (meaning -150, +110, etc are OK)
                if "green" in tier and odds >= -200:
                    player = row.get('Player', row.get('Matchup', 'Unknown'))
                    prop = row.get('Prop', 'Line')
                    history_val = row.get('History_Score', 0) # Assuming a 0-100 score column
                    
                    wager = calculate_units(odds, tab, history_val)
                    
                    # Formatting the Nuke alert
                    header = "☢️ **NUKE ALERT** ☢️" if wager >= 1.9 else "✅ **NEW GREEN PLAY**"
                    
                    msg = (
                        f"{header}\n"
                        f"**Market:** {tab.replace('_', ' ')}\n"
                        f"**Selection:** {player} - {prop}\n"
                        f"**Odds:** {odds}\n"
                        f"**Suggested Wager:** {wager}u"
                    )
                    send_discord(msg)
                    
        except gspread.exceptions.WorksheetNotFound:
            continue 

if __name__ == "__main__":
    process_bot()
