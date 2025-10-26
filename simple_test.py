#!/usr/bin/env python3
"""
Ultra simple calendar check - just raw API call
"""

import requests
from datetime import datetime, timedelta

# Setup
calendar_id = "AQMkADBjYWZhZWI5LTE2ZmItNDUyNy1iNDA4LTY0M2NmOTE0YmU3NwAARgAAA0x0AMwFqHZHtaHN6whvT4UHAGZu2hZpbwRNmdBVsXEd-pIAAAIBBgAAAGZu2hZpbwRNmdBVsXEd-pIAAAJdWQAAAA=="
url = "https://default27828ac15d864f46abfd89560403e7.89.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/eaf1261797f54ecd875b16b92047518f/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=u4zF0dj8ImUdRzDQayjczqITduEt2lDrCx1KzEJInFg"

# Date range (today)
start = datetime.now().isoformat() + 'Z'
end = (datetime.now() + timedelta(days=7)).isoformat() + 'Z'

# Request
data = {
    'cal_id': calendar_id,
    'start_date': start,
    'end_date': end,
    'email': 'souvik@fyelabs.com'
}

# Call API
response = requests.post(url, json=data, headers={'Content-Type': 'application/json'})
print(f"Status: {response.status_code}")
print(f"Response: {response.text}")