#!/usr/bin/env python3
"""
Screener - Tests concept with liquid stocks
"""

import yfinance as yf

class StockScreener:
    def __init__(self):
        # These all work for shorting on Alpaca
        self.watchlist = [
            'TSLA', 'NVDA', 'AMD', 'META', 'NFLX', 'GOOGL', 'AMZN',
            'SMCI', 'SOFI', 'UPST', 'RIVN', 'LCID', 'SNAP', 'PINS',
            'HOOD', 'MRNA', 'NVAX', 'BBAI', 'NIO', 'XPEV'
        ]
        
    def get_opportunities(self):
        """Get short opportunities ranked by volatility/risk"""
        print(f"\n🔍 Scanning {len(self.watchlist)} stocks...")
        
        candidates = []
        
        for ticker in self.watchlist:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info
                
                price = info.get('currentPrice', 0)
                if not price or price <= 0:
                    continue
                
                volume = info.get('averageVolume', 0)
                market_cap = info.get('marketCap', 0)
                beta = info.get('beta', 1.0)
                
                # Score by volatility (higher beta = better short)
                score = 0
                
                # Higher beta = more volatile = better short candidate
                if beta and beta > 2.0:
                    score += 40
                elif beta and beta > 1.5:
                    score += 30
                elif beta and beta > 1.2:
                    score += 20
                
                # Higher volume = more liquid
                if volume > 20_000_000:
                    score += 20
                elif volume > 10_000_000:
                    score += 15
                elif volume > 5_000_000:
                    score += 10
                
                # Mid cap - not too stable, not too risky
                if market_cap and 5_000_000_000 < market_cap < 50_000_000_000:
                    score += 20
                
                candidates.append({
                    'symbol': ticker,
                    'name': info.get('shortName', ticker),
                    'price': price,
                    'volume': volume,
                    'beta': beta,
                    'score': score
                })
                print(f"   {ticker}: \${price:.2f} | Beta: {beta:.2f} | Score: {score}")
                        
            except Exception as e:
                continue
        
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        if candidates:
            print(f"\n🎯 Top opportunities:")
            for c in candidates[:5]:
                print(f"   {c['symbol']}: \${c['price']:.2f} (beta: {c['beta']:.2f})")
        
        return candidates


if __name__ == '__main__':
    screener = StockScreener()
    opps = screener.get_opportunities()
