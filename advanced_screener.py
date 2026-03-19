#!/usr/bin/env python3
"""
Advanced Penny Stock Scanner with Scoring System
"""

import yfinance as yf
import requests
from datetime import datetime, timedelta
import json

class AdvancedScanner:
    def __init__(self):
        # Watchlist of potential penny stocks
        self.watchlist = [
            # Sub-$5 stocks to monitor
            'BBAI', 'NVAX', 'MRNA', 'SOFI', 'UPST', 'RIVN', 'LCID', 'NIO',
            'SNAP', 'PINS', 'HOOD', 'SMCI', 'AMD', 'INDI', 'PL', 'DNA',
            'RKLB', 'SDA', 'BARK', 'LAES', 'MNDR', 'ANY', 'ATER', 'BBIG',
            'LCID', 'XPEV', 'LI', 'WISH', 'NKLA', 'FSR', 'CCIV', 'CHPT',
            'VOLT', 'AUVI', 'SNCE', 'BCT', 'WTRH', 'OP', 'BTBT', 'MARA', 'RIOT',
        ]
    
    def get_data(self, ticker):
        """Get comprehensive data for a ticker"""
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            
            # Get historical data for volume/price analysis
            hist = stock.history(period="5d")
            
            data = {
                'symbol': ticker,
                'name': info.get('shortName', info.get('longName', ticker)),
                'price': info.get('currentPrice', 0),
                'prev_close': info.get('regularMarketPreviousClose', 0),
                'open': info.get('regularMarketOpen', 0),
                'day_high': info.get('regularMarketDayHigh', 0),
                'day_low': info.get('regularMarketDayLow', 0),
                'volume': info.get('regularMarketVolume', 0),
                'avg_volume': info.get('averageVolume', 0),
                'market_cap': info.get('marketCap', 0),
                'float': info.get('floatShares', 0),
                'beta': info.get('beta', 1.0),
                'volatility': info.get('volatility', 0),
                'sector': info.get('sector', 'Unknown'),
                'industry': info.get('industry', 'Unknown'),
            }
            
            # Calculate additional metrics
            if len(hist) >= 2:
                data['volume_5d'] = hist['Volume'].sum()
                data['avg_vol_5d'] = hist['Volume'].mean()
                data['price_change_5d'] = ((hist['Close'].iloc[-1] - hist['Close'].iloc[0]) / hist['Close'].iloc[0]) * 100
            
            if len(hist) >= 1:
                data['gap_up'] = ((data['open'] - data['prev_close']) / data['prev_close']) * 100 if data['prev_close'] else 0
            
            return data
            
        except Exception as e:
            return None
    
    def calculate_score(self, data):
        """Calculate risk score (0-100) - HIGHER = BETTER SHORT CANDIDATE"""
        if not data:
            return 0, []
        
        score = 0
        reasons = []
        
        price = data.get('price', 0)
        volume = data.get('volume', 0)
        avg_volume = data.get('avg_volume', 1)
        market_cap = data.get('market_cap', 0)
        beta = data.get('beta', 1.0)
        float_shares = data.get('float', 0)
        
        # === PRICE FACTORS (max 25 pts) ===
        if price < 1:
            score += 25
            reasons.append(f"Deep penny: ${price:.2f}")
        elif price < 2:
            score += 20
            reasons.append(f"Penny stock: ${price:.2f}")
        elif price < 3:
            score += 15
            reasons.append(f"Low price: ${price:.2f}")
        elif price < 5:
            score += 10
            reasons.append(f"Sub-$5: ${price:.2f}")
        
        # === VOLATILITY FACTORS (max 30 pts) ===
        if beta and beta > 2.5:
            score += 20
            reasons.append(f"High beta: {beta:.2f}")
        elif beta and beta > 1.8:
            score += 15
            reasons.append(f"Volatile: {beta:.2f}")
        elif beta and beta > 1.3:
            score += 10
            reasons.append(f"Moderate beta: {beta:.2f}")
        
        # Volume spike detection
        vol_ratio = volume / avg_volume if avg_volume else 1
        if vol_ratio > 3:
            score += 10
            reasons.append(f"Volume spike: {vol_ratio:.1f}x")
        
        # Gap up detection
        gap = data.get('gap_up', 0)
        if gap > 20:
            score += 10
            reasons.append(f"Gap up: {gap:.1f}%")
        elif gap > 10:
            score += 5
            reasons.append(f"Opened up: {gap:.1f}%")
        
        # === SIZE FACTORS (max 20 pts) ===
        if market_cap and market_cap < 50_000_000:
            score += 15
            reasons.append(f"Small cap: ${market_cap/1e6:.1f}M")
        elif market_cap and market_cap < 200_000_000:
            score += 10
            reasons.append(f"Mid-small cap: ${market_cap/1e6:.1f}M")
        
        if float_shares and float_shares < 5_000_000:
            score += 10
            reasons.append(f"Low float: {float_shares/1e6:.1f}M")
        
        # === TECHNICAL FACTORS (max 15 pts) ===
        price_change = data.get('price_change_5d', 0)
        if price_change > 30:
            score += 15
            reasons.append(f"Parabolic 5d: +{price_change:.1f}%")
        elif price_change > 20:
            score += 10
            reasons.append(f"Strong run: +{price_change:.1f}%")
        elif price_change > 10:
            score += 5
            reasons.append(f"Running: +{price_change:.1f}%")
        
        # === DILUTION WARNING (add negative if recently ran up) ===
        if price_change < -30:
            reasons.append(f"Already crashed: {price_change:.1f}%")
        
        return score, reasons
    
    def check_trade_conditions(self, data, score):
        """Check if trade conditions are met"""
        conditions = {
            'price_acceptable': False,
            'liquidity_sufficient': False,
            'borrow_available': None,  # Would check via broker
            'not_halted': True,  # Would check via broker
            'score_threshold': score >= 40,
        }
        
        price = data.get('price', 0)
        volume = data.get('volume', 0)
        
        # Price check
        if 0.10 <= price <= 10:
            conditions['price_acceptable'] = True
        
        # Liquidity check - need at least 500K volume
        if volume >= 500_000:
            conditions['liquidity_sufficient'] = True
        
        # All conditions must pass
        conditions['all_passed'] = (
            conditions['price_acceptable'] and
            conditions['liquidity_sufficient'] and
            conditions['score_threshold'] and
            conditions['not_halted']
        )
        
        return conditions
    
    def scan(self):
        """Run full scan"""
        print(f"\n{'='*70}")
        print(f"🔍 ADVANCED SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}")
        
        candidates = []
        
        for ticker in self.watchlist:
            data = self.get_data(ticker)
            if not data:
                continue
            
            # Skip if no price
            if not data.get('price') or data['price'] <= 0:
                continue
            
            score, reasons = self.calculate_score(data)
            conditions = self.check_trade_conditions(data, score)
            
            candidate = {
                'data': data,
                'score': score,
                'reasons': reasons,
                'conditions': conditions
            }
            
            # Only show if score is meaningful
            if score >= 20:
                candidates.append(candidate)
                status = "✅ READY" if conditions['all_passed'] else "⏸️ WAITING"
                print(f"\n{ticker} ({data['name'][:25]}) - Score: {score} {status}")
                print(f"   Price: ${data['price']:.2f} | Vol: {data['volume']/1e6:.1f}M | Beta: {data.get('beta', 0):.2f}")
                for r in reasons[:5]:
                    print(f"   • {r}")
                
                if not conditions['all_passed']:
                    failed = [k for k, v in conditions.items() if not v and k != 'borrow_available']
                    if failed:
                        print(f"   ⚠️  Blocks: {', '.join(failed)}")
        
        # Sort by score
        candidates.sort(key=lambda x: x['score'], reverse=True)
        
        # Return top candidates that are ready
        ready = [c for c in candidates if c['conditions']['all_passed']]
        
        print(f"\n{'='*70}")
        print(f"📊 SCAN COMPLETE: {len(candidates)} scanned | {len(ready)} READY TO TRADE")
        print(f"{'='*70}")
        
        if ready:
            print("\n🎯 TOP SETUPS:")
            for c in ready[:5]:
                print(f"   {c['data']['symbol']}: {c['score']} pts")
        
        return candidates, ready


def main():
    scanner = AdvancedScanner()
    candidates, ready = scanner.scan()


if __name__ == '__main__':
    main()
