"""
Insider Trading Data Management Package

Collects, deduplicates, and uploads insider trading data from NSE and BSE.
"""

from .insider_trading_detector import InsiderTradingManager, NSEInsiderScraper, BSEInsiderScraper

__all__ = ['InsiderTradingManager', 'NSEInsiderScraper', 'BSEInsiderScraper']
