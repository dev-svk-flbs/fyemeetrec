#!/usr/bin/env python3
"""Ultra minimal test upload"""
import boto3

# Your IDrive E2 credentials
ACCESS_KEY = "BtvRQTb87eNP5lLw3WDO"
SECRET_KEY = "Esp3hhG5TuwhcOT76dr6m5ZUU5Strv1oLqwpRRgr"

s3 = boto3.client(
    's3',
    endpoint_url="https://s3.us-west-1.idrivee2.com",
    aws_access_key_id=ACCESS_KEY,
    aws_secret_access_key=SECRET_KEY
)

# Upload a test file
s3.upload_file('README.md', 'fyemeet', 'test/readme.txt')
print("✅ Test upload complete!")