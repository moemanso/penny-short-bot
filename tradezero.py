#!/usr/bin/env python3
"""
TradeZero API Integration
"""

import requests
import hmac
import hashlib
import time
from datetime import datetime

class TradeZeroClient:
    def __init__(self, api_key, api_secret, account_id=None, paper=True):
        self.api_key = api_key
        self.api_secret = api_secret
        self.account_id = account_id
        self.base_url = "https://api.tradezero.co" if not paper else "https://papi.tradezero.co"
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'ApexShorts/1.0'})
    
    def _sign(self, timestamp, method, path):
        """Generate HMAC signature"""
        message = f"{timestamp}{method}{path}"
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _request(self, method, path, data=None):
        """Make authenticated request"""
        timestamp = str(int(time.time() * 1000))
        signature = self._sign(timestamp, method, path)
        
        headers = {
            'TZ-API-KEY': self.api_key,
            'TZ-TIMESTAMP': timestamp,
            'TZ-SIGNATURE': signature,
            'Content-Type': 'application/json'
        }
        
        url = f"{self.base_url}{path}"
        
        if method == 'GET':
            resp = self.session.get(url, headers=headers, params=data)
        elif method == 'POST':
            resp = self.session.post(url, headers=headers, json=data)
        else:
            return None
        
        return resp.json() if resp.status_code == 200 else None
    
    def get_account(self):
        """Get account info"""
        path = "/v1/api/account"
        return self._request('GET', path)
    
    def get_positions(self):
        """Get current positions"""
        path = "/v1/api/positions"
        return self._request('GET', path)
    
    def place_short(self, symbol, quantity, limit_price=None):
        """Place a short order"""
        path = "/v1/api/orders"
        
        order = {
            "symbol": symbol,
            "side": "sell",  # sell = short
            "quantity": quantity,
            "orderType": "market" if not limit_price else "limit"
        }
        
        if limit_price:
            order["limitPrice"] = limit_price
        
        return self._request('POST', path, order)
    
    def cover_short(self, symbol, quantity, limit_price=None):
        """Cover a short (buy to close)"""
        path = "/v1/api/orders"
        
        order = {
            "symbol": symbol,
            "side": "buy",  # buy = cover
            "quantity": quantity,
            "orderType": "market" if not limit_price else "limit"
        }
        
        if limit_price:
            order["limitPrice"] = limit_price
        
        return self._request('POST', path, order)
    
    def cancel_order(self, order_id):
        """Cancel an order"""
        path = f"/v1/api/orders/{order_id}"
        return self._request('DELETE', path)
    
    def get_locates(self, symbol):
        """Get available locates for a symbol (critical for shorts!)"""
        path = f"/v1/api/locates/{symbol}"
        return self._request('GET', path)


def main():
    """Test connection - needs your credentials"""
    print("📡 TradeZero Client Ready")
    print("   To connect, need:")
    print("   - API Key from TradeZero dashboard")
    print("   - API Secret")
    print("   - Account ID")


if __name__ == '__main__':
    main()
