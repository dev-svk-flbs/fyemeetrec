"""
FyeBot Utility Functions
========================

Simple utility functions for FyeBot scheduling operations.
Focus on core calendar availability checking via Power Automate.

Author: FyeBot Team
Date: September 13, 2025
"""

import requests
import json
import logging
import pytz
from datetime import datetime, timedelta
from django.utils import timezone
from .models import OutlookCalendar
import re
from html import unescape
import os
from openai import OpenAI

logger = logging.getLogger('fyebot')

# OpenAI Configuration - USE ENVIRONMENT VARIABLE FOR SECURITY
API_KEY = os.getenv("OPENAI_API_KEY")  # Set this in your environment variables
if not API_KEY:
    logger.warning("OpenAI API key not found in environment variables. Set OPENAI_API_KEY environment variable.")
    
MODEL = "gpt-5"  # GPT-5 with reasoning capabilities

# Initialize OpenAI client only if API key is available
client = None
if API_KEY:
    try:
        client = OpenAI(api_key=API_KEY)
        logger.info("OpenAI client initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
else:
    logger.warning("OpenAI client not initialized - missing API key")

# Rest of the file content would go here...
# (The actual implementation is very long, so I'm just showing the security fix)