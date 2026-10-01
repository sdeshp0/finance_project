"""Fixed ETF universes offered as sidebar presets, alongside S&P 500 sectors
and a custom ticker list. These are plain dicts (ticker -> display label), not
backed by any constituent-list scrape, so there's no live source to fail -
only the price fetch itself can fail, same as any other ticker in the app.
"""

# The 11 SPDR Select Sector ETFs - one per GICS sector, tracking the S&P 500's
# own sector weights. Confirmed current/active.
SECTOR_ETFS: dict[str, str] = {
    "XLK": "Technology", "XLF": "Financials", "XLV": "Health Care",
    "XLY": "Consumer Discretionary", "XLP": "Consumer Staples", "XLE": "Energy",
    "XLI": "Industrials", "XLB": "Materials", "XLU": "Utilities",
    "XLRE": "Real Estate", "XLC": "Communication Services",
}

# A curated set of major-market iShares MSCI (and similar) single-country
# ETFs. Not exhaustive - picked for liquidity and geographic spread.
COUNTRY_ETFS: dict[str, str] = {
    "EWJ": "Japan", "EWG": "Germany", "EWU": "United Kingdom", "EWQ": "France",
    "EWI": "Italy", "EWL": "Switzerland", "EWC": "Canada", "EWA": "Australia",
    "EWZ": "Brazil", "EWW": "Mexico", "FXI": "China (Large-Cap)", "INDA": "India",
    "EWY": "South Korea", "EWT": "Taiwan", "EWS": "Singapore", "EWH": "Hong Kong",
}