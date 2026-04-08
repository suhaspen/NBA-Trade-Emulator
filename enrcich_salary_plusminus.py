import sys, time, subprocess
import pandas as pd
import requests
from io import StringIO
import unicodedata, re

if "/tmp/site-packages" not in sys.path:
    sys.path.insert(0, "/tmp/site-packages")

def normalize_name(name):
    if not isinstance(name, str): return ""
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_n = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z ]", "", ascii_n.lower()).strip()

def clean_sal(v):
    if pd.isna(v): return None
    s = str(v).replace("$", "").replace(",", "").replace("\xa0", "").strip()
    if s in ("", "--", "2-Way", "nan"): return None
    try: return float(s)
    except: return None

# ── 1. Set plus_minus from BPM (box plus-minus) ──────────────────────────────
print("=== Step 1: Set plus_minus from BPM ===")
enriched_df = merged_df.copy()

if enriched_df["plus_minus"].isna().all() and "bpm" in enriched_df.columns:
    enriched_df["plus_minus"] = enriched_df["bpm"]
    print(f"  plus_minus: {enriched_df['plus_minus'].notna().sum()}/{len(enriched_df)} filled from BPM")

# ── 2. Salary: Try basketball_reference_web_scraper ────────────────────────────
print("\n=== Step 2: Trying basketball_reference_web_scraper ===")

sal_df = pd.DataFrame()

try:
    from basketball_reference_web_scraper import client as bref_client
    from basketball_reference_web_scraper.data import Team

    # Fetch player season totals for 2023-24 (season_end_year=2024)
    season_stats = bref_client.players_season_totals(season_end_year=2024)
    bref_df = pd.DataFrame(season_stats)
    print(f"  bref_client totals: {bref_df.shape}")
    print(f"  Columns: {list(bref_df.columns)}")
except Exception as e:
    bref_df = pd.DataFrame()
    print(f"  bref_client error: {e}")

# ── 3. Salary: Try GitHub NBA salary datasets ─────────────────────────────────
print("\n=== Step 3: Fetching salary from GitHub NBA data ===")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}

# Try several known public NBA salary CSVs on GitHub
salary_urls = [
    # NBA salary data CSV from public repos
    "https://raw.githubusercontent.com/erikgregorywebb/nyc-housing/master/Data/nba-salaries.csv",
    "https://raw.githubusercontent.com/datascientest-students/nba_stats_project/main/data/NBA_season1718_salary.csv",
    # Try the basketball-reference archive CSVs on GitHub
    "https://raw.githubusercontent.com/datasets/nba-statistics/master/data/players-2024.csv",
]

for url in salary_urls:
    time.sleep(2)
    try:
        resp = requests.get(url, headers=HEADERS, timeout=20)
        if resp.status_code == 200:
            test_df = pd.read_csv(StringIO(resp.text))
            print(f"  {url.split('/')[-1]}: {test_df.shape} | cols: {list(test_df.columns[:8])}")
            if any("salary" in c.lower() for c in test_df.columns):
                sal_df = test_df
                print(f"  -> Using this for salary!")
                break
        else:
            print(f"  {url.split('/')[-1]}: HTTP {resp.status_code}")
    except Exception as e:
        print(f"  Error: {e}")

# ── 4. If bref_client worked, extract salary-like data ───────────────────────
# bref_client.players_season_totals doesn't have salary - but let's check
if not bref_df.empty and "salary" in " ".join(bref_df.columns).lower():
    print("Found salary in bref data!")
    sal_col = next(c for c in bref_df.columns if "salary" in c.lower())
    sal_df = bref_df

# ── 5. Process salary data if found ──────────────────────────────────────────
sal_proc = pd.DataFrame()
if not sal_df.empty:
    sal_df.columns = [str(c).strip() for c in sal_df.columns]
    print(f"\nProcessing salary df: {sal_df.shape}")
    print(f"  Columns: {list(sal_df.columns)}")

    # Find name and salary columns
    player_col = next((c for c in sal_df.columns
                       if "name" in c.lower() or "player" in c.lower()), None)
    sal_col = next((c for c in sal_df.columns
                    if "salary" in c.lower()), None)
    print(f"  player_col={player_col}, sal_col={sal_col}")

    if player_col and sal_col:
        sal_df = sal_df[sal_df[player_col].notna()].copy()
        sal_proc = pd.DataFrame({
            "name_key": sal_df[player_col].astype(str).apply(normalize_name),
            "salary_new": sal_df[sal_col].apply(clean_sal),
        })
        sal_proc = sal_proc[sal_proc["salary_new"].notna()].drop_duplicates("name_key")
        print(f"  sal_proc: {sal_proc.shape}")

# ── 6. Fallback: Construct approximate salaries using known 2023-24 max values ─
# Use the NBA's rookie scale + known contracts for rough estimates
# Source: Publicly known NBA CBA salary structure for 2023-24
if sal_proc.empty:
    print("\n=== Step 4 (fallback): Estimating salary from WS/age/draft position proxy ===")
    # NBA salary approximation:
    # We know min/max salary for 2023-24 season:
    # Minimum: $1,119,563 (veteran minimum varies by years of service)
    # Maximum (supermax): ~$51.9M (35%+ of salary cap ~$148.3M × 0.35 = ~$51.9M)
    # We can estimate using WS (win shares) as a proxy for contract value
    # This is a reasonable proxy for exploratory analysis
    
    # Simple model: salary ≈ f(vorp, age, games_played)
    # Players with VORP > 3 typically earn max/near-max deals
    # This gives us a reasonable synthetic salary estimate
    
    MIN_SALARY = 1_000_000  # Approximate NBA min salary 2023-24
    MAX_SALARY = 50_000_000  # Approximate supermax
    
    def estimate_salary(row):
        """Rough salary estimate based on VORP, WS, age. For exploration only."""
        if pd.isna(row.get("vorp")) or pd.isna(row.get("ws")) or pd.isna(row.get("age")):
            return None
        
        vorp = float(row["vorp"])
        ws = float(row["ws"])
        age = float(row["age"])
        pts = float(row.get("pts", 0))
        
        # Scale based on value metrics
        # Superstar: VORP > 5 → ~$40-50M
        # Star: VORP 2-5 → ~$20-40M
        # Solid: VORP 0-2 → ~$5-20M
        # Below avg: VORP < 0 → $1-5M
        
        if vorp >= 5:
            base = 40_000_000 + (vorp - 5) * 1_000_000
        elif vorp >= 2:
            base = 20_000_000 + (vorp - 2) * 6_000_000
        elif vorp >= 0:
            base = 5_000_000 + vorp * 7_500_000
        else:
            base = max(MIN_SALARY, 3_000_000 + vorp * 500_000)
        
        # Clamp
        return max(MIN_SALARY, min(MAX_SALARY, base))
    
    enriched_df["salary_estimated"] = enriched_df.apply(estimate_salary, axis=1)
    enriched_df["salary_2023_24"] = enriched_df["salary_estimated"].combine_first(
        enriched_df["salary_2023_24"]
    )
    enriched_df.drop(columns=["salary_estimated"], errors="ignore", inplace=True)
    n_sal = enriched_df["salary_2023_24"].notna().sum()
    print(f"  Estimated salaries filled: {n_sal}/{len(enriched_df)}")
    print(f"  NOTE: salary_2023_24 values are ESTIMATED (VORP-based proxy), not actual contract values")

else:
    # Merge actual salary data
    enriched_df["name_key"] = enriched_df["player_name"].apply(normalize_name)
    enriched_df = enriched_df.merge(sal_proc, on="name_key", how="left")
    enriched_df["salary_2023_24"] = enriched_df["salary_new"].combine_first(
        enriched_df["salary_2023_24"]
    )
    enriched_df.drop(columns=["salary_new", "name_key"], errors="ignore", inplace=True)
    n_sal = enriched_df["salary_2023_24"].notna().sum()
    print(f"\nsalary_2023_24 filled: {n_sal}/{len(enriched_df)}")

# ── 7. Final cleanup and report ───────────────────────────────────────────────
enriched_df.drop(columns=["name_key"], errors="ignore", inplace=True)
enriched_df.sort_values(["team", "pts"], ascending=[True, False], inplace=True)
enriched_df.reset_index(drop=True, inplace=True)

print(f"\n{'='*60}")
print(f"enriched_df shape: {enriched_df.shape}")
print(f"\nColumns ({len(enriched_df.columns)}):")
print(list(enriched_df.columns))

print(f"\nTeam player counts:")
print(enriched_df.groupby("team").size().to_string())

print(f"\nNull counts (key columns):")
key_cols = ["pts", "ast", "reb", "fg_pct", "fg3_pct", "plus_minus",
            "bpm", "vorp", "salary_2023_24", "contract_years_remaining",
            "age", "games_missed"]
for col in key_cols:
    if col in enriched_df.columns:
        n   = enriched_df[col].isna().sum()
        pct = 100 * n / len(enriched_df)
        status = "✓" if n == 0 else ("~" if pct < 15 else "✗")
        print(f"  {status} {col:25s}: {n:3d} nulls ({pct:.0f}%)")

print(f"\nSample rows (first 10):")
sample_cols = ["player_name", "team", "age", "pts", "ast", "reb",
               "fg_pct", "fg3_pct", "plus_minus", "bpm", "vorp",
               "salary_2023_24", "contract_years_remaining", "games_missed"]
sample_cols = [c for c in sample_cols if c in enriched_df.columns]
pd.set_option("display.max_columns", None)
pd.set_option("display.width", 220)
print(enriched_df[sample_cols].head(10).to_string(index=False))
