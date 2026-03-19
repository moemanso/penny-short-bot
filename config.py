# Penny Short Bot - Configuration

## Risk Parameters
MAX_RISK_PER_TRADE = 0.015  # 1.5% of portfolio
STOP_LOSS_PCT = 0.15        # 15% - cover if stock rises this much
MAX_CONCURRENT_SHORTS = 8
MIN_AVG_VOLUME = 100000     # 100K minimum avg volume
MAX_MARKET_CAP = 50_000_000 # $50M

## Trading
PAPER_TRADING = True  # Set to False for real money
DEFAULT_PORTFOLIO = 100000  # Paper portfolio size

## Screener
LOOKBACK_DAYS = 90  # Look for companies that went public in last 90 days
MIN_PRICE = 0.50    # Minimum stock price
MAX_PRICE = 5.00    # Maximum stock price (penny stock range)

## Filters
MIN_CASH_RUNWAY_MONTHS = 6  # Flag if less than 6 months
MIN_REVENUE = 0  # Allow pre-revenue
EXCLUDE_REVERSE_MERGERS = True