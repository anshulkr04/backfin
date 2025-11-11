#!/usr/bin/env python3
"""
Entry point for queue manager service
"""

import sys
import os
import asyncio

# Ensure we're in the right directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Add the current directory to Python path
sys.path.insert(0, os.getcwd())

# Import and run the queue manager
from core.queue_manager import main

if __name__ == "__main__":
    asyncio.run(main())