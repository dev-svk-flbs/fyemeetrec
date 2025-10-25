# Django Webhook Integration

## Overview

The recording system now automatically sends metadata to your Django server at `ops.fyelabs.com` after successfully uploading recordings to IDrive E2 S3.

## How It Works

1. **Recording Completes** → Local recording finishes and files are saved
2. **Upload to IDrive E2** → Video, transcript, and thumbnail are uploaded to S3
3. **Metadata Creation** → Comprehensive metadata is compiled including:
   - Recording details (ID, title, duration)
   - User information (username, email)
   - File sizes and S3 URLs
   - Upload timestamps
4. **Webhook Sent** → Metadata is POST'ed to Django webhook endpoint
5. **Django Processing** → Django creates/updates recording in database

## Webhook Endpoint

```
POST https://ops.fyelabs.com/recordings/webhook/
```

## Payload Structure

The webhook sends a JSON payload with the following structure:

```json
{
  "recording_id": 3,
  "title": "Meeting 2025-10-24 21:55",
  "created_at": "2025-10-25 01:55:59.374860",
  "duration_seconds": 77,
  "duration_database": 77,
  "user_info": {
    "username": "souvik",
    "email": "souvik@fyelabs.com"
  },
  "file_info": {
    "total_size_mb": 0.51,
    "individual_sizes_mb": {
      "video.mkv": 0.5,
      "thumbnail.jpg": 0.01,
      "transcript.txt": 0.0
    }
  },
  "uploaded_files": {
    "video": "https://s3.us-west-1.idrivee2.com/fyemeet/3/video.mkv",
    "thumbnail": "https://s3.us-west-1.idrivee2.com/fyemeet/3/thumbnail.jpg",
    "transcript": "https://s3.us-west-1.idrivee2.com/fyemeet/3/transcript.txt",
    "metadata": "https://s3.us-west-1.idrivee2.com/fyemeet/3/metadata.json"
  },
  "upload_timestamp": "2025-10-24T21:57:22.775114",
  "upload_source": "background_thread",
  "bucket_name": "fyemeet",
  "region": "us-west-1"
}
```

## Key Features

### Non-Blocking
- Webhook sending is non-blocking
- Upload won't fail if webhook fails
- Errors are logged but don't affect local recording

### Automatic Retry
- Built into the retry_manager system
- Failed webhooks can be retried manually
- Webhook is attempted after successful S3 upload

### User Matching
- Django matches by `user_info.email`
- Email must exist in Django CustomUser model
- Returns 404 if user not found

### Upsert Behavior
- Uses `recording_id` as unique identifier
- Creates new recording if ID doesn't exist
- Updates existing recording if ID found
- Returns `action: "created"` or `action: "updated"`

## Expected Responses

### Success (201 Created)
```json
{
  "status": "success",
  "message": "Recording created successfully",
  "recording_id": 3,
  "pk": 1,
  "action": "created"
}
```

### Success (200 OK - Update)
```json
{
  "status": "success",
  "message": "Recording updated successfully",
  "recording_id": 3,
  "pk": 1,
  "action": "updated"
}
```

### Error (404 Not Found)
```json
{
  "status": "error",
  "message": "No user found with email: example@example.com"
}
```

### Error (400 Bad Request)
```json
{
  "status": "error",
  "message": "Missing required fields: recording_id or user_info.email"
}
```

## Testing

### Test Script
Run the test script to verify webhook integration:

```bash
python test_webhook.py
```

This will:
- Send a test payload to the Django webhook
- Display the request and response
- Confirm successful integration

### Manual Testing with curl
```bash
curl -X POST https://ops.fyelabs.com/recordings/webhook/ \
  -H "Content-Type: application/json" \
  -d '{
    "recording_id": 999,
    "title": "Test Recording",
    "user_info": {
      "email": "souvik@fyelabs.com",
      "username": "souvik"
    },
    "uploaded_files": {
      "video": "https://s3.us-west-1.idrivee2.com/fyemeet/999/video.mkv"
    },
    "duration_seconds": 120,
    "bucket_name": "fyemeet",
    "region": "us-west-1"
  }'
```

## Logging

Webhook activity is logged with these indicators:
- `📤 Sending webhook to...` - Webhook request starting
- `✅ Webhook sent successfully` - Django accepted the webhook
- `❌ Webhook failed with status XXX` - HTTP error from Django
- `❌ Webhook timeout` - Request took > 30 seconds
- `❌ Webhook connection failed` - Network error
- `⚠️ Webhook failed but upload succeeded` - Non-critical error

Check logs at: `logs/app.log`

## Configuration

The webhook URL is configured in `background_uploader.py`:

```python
class BackgroundUploader:
    def __init__(self, db_path=None):
        # Django Webhook Configuration
        self.webhook_url = 'https://ops.fyelabs.com/recordings/webhook/'
```

To change the webhook URL, edit this line in the `__init__` method.

## Error Handling

- **Webhook failures do NOT fail the upload**
- S3 upload completes independently
- Webhook errors are logged for debugging
- Failed webhooks can be retried manually through the UI
- Timeout set to 30 seconds to prevent hanging

## Integration Flow

```
┌─────────────────┐
│ Recording Ends  │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Upload to S3    │
│ (video, thumb,  │
│  transcript)    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Create Metadata │
│ (sizes, URLs,   │
│  user info)     │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Send Webhook    │
│ to Django       │
└────────┬────────┘
         │
         ├─── Success ───► Recording appears in Django
         │
         └─── Failure ───► Logged, can retry later
```

## Troubleshooting

### Webhook Not Sending
1. Check logs: `logs/app.log`
2. Verify network connectivity to ops.fyelabs.com
3. Ensure user email exists in Django
4. Check S3 upload completed successfully

### User Not Found
- Ensure user email in local DB matches Django
- User must exist in Django CustomUser model
- Email is case-sensitive

### Timeout Errors
- Check network latency to ops.fyelabs.com
- Verify Django server is responding
- Check Django logs for processing issues

### Partial Uploads
- Webhook only sent if at least one file uploads successfully
- Check which files failed in logs
- Retry mechanism will attempt failed files

## Security

- HTTPS connection to ops.fyelabs.com
- No authentication token required (Django endpoint is CSRF-exempt)
- User email is validated server-side
- S3 URLs are public but use long random paths

## Future Enhancements

- [ ] Add webhook authentication token
- [ ] Implement webhook retry queue
- [ ] Add webhook status dashboard
- [ ] Support multiple webhook endpoints
- [ ] Add webhook payload signing
