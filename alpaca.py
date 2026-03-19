#!/usr/bin/env python3
"""
Alpaca Trading API Integration
"""

import os
import requests
import json
from datetime import datetime

# Alpaca API credentials (paper trading)
API_KEY = os.environ.get('ALPACA_API_KEY', 'PK2MU4L5PNPMC4ODN5E2BTST3E')
SECRET_KEY = os.environ.get('ALPACA_SECRET_KEY', '5ieGgTUvf8jLhQzFTZ9u51jR4zybZPNqfw5GFZZwcNCn')
PAPER_BASE_URL = 'https://paper-api.alpaca.markets'
LIVE_BASE_URL = 'https://api.alpaca.markets'

class AlpacaClient:
    def __init__(self, paper=True):
        self.base_url = PAPER_BASE_URL if paper else LIVE_BASE_URL
        self.headers = {
            'APCA-API-KEY-ID': API_KEY,
            'APCA-API-SECRET-KEY': SECRET_KEY,
            'Content-Type': 'application/json'
        }
        
    def get_account(self):
        """Get account info"""
        url = f"{self.base_url}/v2/account"
        try:
            resp = requests.get(url, headers=self.headers)
            return resp.json() if resp.status_code == 200 else None
        except Exception as e:
            print(f"Error: {e}")
            return None
    
    def get_positions(self):
        """Get current positions"""
        url = f"{self.base_url}/v2/positions"
        try:
            resp = requests.get(url, headers=self.headers)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            print(f"Error: {e}")
            return []
    
    def get_quote(self, symbol):
        """Get current quote for a symbol"""
        url = f"{self.base_url}/v2/stocks/{symbol}/quotes/latest"
        try:
            resp = requests.get(url, headers=self.headers)
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'bid': float(data.get('quote', {}).get('bp', 0)),
                    'ask': float(data.get('quote', {}).get('ap', 0)),
                    'last': float(data.get('quote', {}).get('lp', 0))
                }
        except Exception as e:
            print(f"Error fetching quote for {symbol}: {e}")
        return None
    
    def get_bars(self, symbol, timeframe='1Day', limit=50):
        """Get historical bars"""
        url = f"{self.base_url}/v2/stocks/{symbol}/bars"
        params = {
            'timeframe': timeframe,
            'limit': limit
        }
        try:
            resp = requests.get(url, headers=self.headers, params=params)
            return resp.json().get('bars', []) if resp.status_code == 200 else []
        except Exception as e:
            print(f"Error fetching bars for {symbol}: {e}")
            return []
    
    def submit_short(self, symbol, qty, limit_price=None):
        """Submit a short order"""
        url = f"{self.base_url}/v2/orders"
        
        order_data = {
            'symbol': symbol,
            'qty': qty,
            'side': 'sell',  # Selling short = sell
            'type': 'market',
            'time_in_force': 'day'
        }
        
        if limit_price:
            order_data['type'] = 'limit'
            order_data['limit_price'] = str(limit_price)
        
        try:
            resp = requests.post(url, headers=self.headers, json=order_data)
            if resp.status_code in [200, 201]:
                return resp.json()
            else:
                print(f"Order error: {resp.text}")
                return None
        except Exception as e:
            print(f"Error submitting order: {e}")
            return None
    
    def cover_short(self, symbol, qty, limit_price=None):
        """Cover a short position (buy to close)"""
        url = f"{self.base_url}/v2/orders"
        
        order_data = {
            'symbol': symbol,
            'qty': qty,
            'side': 'buy',  # Buying to cover = buy
            'type': 'market',
            'time_in_force': 'day'
        }
        
        if limit_price:
            order_data['type'] = 'limit'
            order_data['limit_price'] = str(limit_price)
        
        try:
            resp = requests.post(url, headers=self.headers, json=order_data)
            if resp.status_code in [200, 201]:
                return resp.json()
            else:
                print(f"Order error: {resp.text}")
                return None
        except Exception as e:
            print(f"Error covering order: {e}")
            return None
    
    def cancel_order(self, order_id):
        """Cancel an order"""
        url = f"{self.base_url}/v2/orders/{order_id}"
        try:
            resp = requests.delete(url, headers=self.headers)
            return resp.status_code == 204
        except Exception as e:
            print(f"Error cancelling order: {e}")
            return False
    
    def get_orders(self, status='all'):
        """Get orders"""
        url = f"{self.base_url}/v2/orders"
        params = {'status': status}
        try:
            resp = requests.get(url, headers=self.headers, params=params)
            return resp.json() if resp.status_code == 200 else []
        except Exception as e:
            print(f"Error: {e}")
            return []


def main():
    """Test Alpaca connection"""
    client = AlpacaClient(paper=True)
    
    print("📡 Alpaca Paper Trading Client initialized")
    print("   Configure ALPACA_API_KEY and ALPACA_SECRET_KEY to trade")
    
    # Try to get account info
    account = client.get_account()
    if account:
        print(f"   Account: {account.get('account_number', 'N/A')}")
        print(f"   Cash: ${float(account.get('cash', 0)):,.2f}")
    else:
        print("   ⚠️  API not connected - check credentials")


if __name__ == '__main__':
    main()