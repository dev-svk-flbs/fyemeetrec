# Complete Webhook Payload Documentation

## Updated ops.fyelabs.com Webhook Integration

The recording system sends comprehensive metadata to `https://ops.fyelabs.com/recordings/webhook/` after successful upload to IDrive E2.

### Endpoint Details
- **URL**: `https://ops.fyelabs.com/recordings/webhook/`
- **Method**: POST
- **Headers**:
  ```json
  {
    "Content-Type": "application/json",
    "X-Webhook-Token": "fye_webhook_secure_token_2025_recordings"
  }
  ```

## Complete Payload Structure

### Case 1: Recording Linked to Meeting
```json
{
  "recording_id": 123,
  "title": "FYELABS & Mucex - Update Meeting",
  "created_at": "2025-10-27 10:30:00.123456",
  "duration_seconds": 3600,
  "duration_database": 3590,
  "user_info": {
    "username": "souvik",
    "email": "souvik@fyelabs.com"
  },
  "file_info": {
    "total_size_mb": 250.75,
    "individual_sizes_mb": {
      "video.mkv": 245.20,
      "transcript.txt": 0.05,
      "thumbnail.jpg": 5.50
    }
  },
  "uploaded_files": {
    "video": "https://s3.us-west-1.idrivee2.com/fyemeet/123/video.mkv",
    "transcript": "https://s3.us-west-1.idrivee2.com/fyemeet/123/transcript.txt",
    "thumbnail": "https://s3.us-west-1.idrivee2.com/fyemeet/123/thumbnail.jpg",
    "metadata": "https://s3.us-west-1.idrivee2.com/fyemeet/123/metadata.json"
  },
  "upload_timestamp": "2025-10-27T10:35:00.123456",
  "upload_source": "background_thread",
  "bucket_name": "fyemeet",
  "region": "us-west-1",
  "meeting_info": {
    "meeting_id": 456,
    "subject": "FYELABS & Mucex - Update Meeting",
    "start_time": "2025-10-27 10:00:00",
    "end_time": "2025-10-27 11:00:00",
    "duration_minutes": 60,
    "organizer": "souvik@fyelabs.com",
    "location": "Microsoft Teams Meeting",
    "web_link": "https://teams.microsoft.com/l/meetup-join/19%3ameeting_...",
    "meeting_type": "teams",
    "is_teams_meeting": true,
    "is_recurring": false,
    "attendee_count": 5,
    "required_attendees": [
      "souvik@fyelabs.com",
      "team@mucex.com",
      "john@fyelabs.com"
    ],
    "optional_attendees": [
      "observer@fyelabs.com"
    ],
    "calendar_event_id": "AQMkADBjYWZhZWI5LTE2ZmItNDUyNy1iNDA4LTY0M2NmOTE0YmU3NwBGAAADTHQAzAWodke1oc3rCG9PhQcAZm7aFmlvBE2Z0FWxcR36kgAAAgEGAAAAZm7aFmlvBE2Z0FWxcR36kgAAJ6XYgAAAAA==",
    "discovered_at": "2025-10-26 15:20:00",
    "is_linked_to_meeting": true
  }
}
```

### Case 2: Standalone Recording (Not Linked to Meeting)
```json
{
  "recording_id": 124,
  "title": "Manual Recording - Screen Capture",
  "created_at": "2025-10-27 14:15:00.789012",
  "duration_seconds": 1800,
  "duration_database": 1795,
  "user_info": {
    "username": "souvik",
    "email": "souvik@fyelabs.com"
  },
  "file_info": {
    "total_size_mb": 180.25,
    "individual_sizes_mb": {
      "video.mkv": 175.80,
      "transcript.txt": 0.03,
      "thumbnail.jpg": 4.42
    }
  },
  "uploaded_files": {
    "video": "https://s3.us-west-1.idrivee2.com/fyemeet/124/video.mkv",
    "transcript": "https://s3.us-west-1.idrivee2.com/fyemeet/124/transcript.txt",
    "thumbnail": "https://s3.us-west-1.idrivee2.com/fyemeet/124/thumbnail.jpg",
    "metadata": "https://s3.us-west-1.idrivee2.com/fyemeet/124/metadata.json"
  },
  "upload_timestamp": "2025-10-27T14:20:00.789012",
  "upload_source": "background_thread",
  "bucket_name": "fyemeet",
  "region": "us-west-1",
  "meeting_info": {
    "is_linked_to_meeting": false
  }
}
```

## Field Descriptions

### Core Recording Data
- **recording_id**: Unique local database ID for the recording
- **title**: Recording title (same as meeting subject if linked)
- **created_at**: When recording was created (local timezone)
- **duration_seconds**: Actual video duration from ffprobe analysis
- **duration_database**: Duration stored in database (may differ slightly)

### User Information
- **user_info.username**: Local username of recorder
- **user_info.email**: Email address of recorder

### File Information
- **file_info.total_size_mb**: Combined size of all uploaded files
- **file_info.individual_sizes_mb**: Size breakdown by file type

### Uploaded Files
- **uploaded_files.video**: S3 URL for the video file (.mkv format)
- **uploaded_files.transcript**: S3 URL for the transcript (.txt format)
- **uploaded_files.thumbnail**: S3 URL for the thumbnail image (.jpg format)
- **uploaded_files.metadata**: S3 URL for complete metadata JSON

### Upload Metadata
- **upload_timestamp**: ISO timestamp when upload completed
- **upload_source**: Always "background_thread"
- **bucket_name**: S3 bucket name ("fyemeet")
- **region**: S3 region ("us-west-1")

### Meeting Information (when linked)
- **meeting_info.meeting_id**: Local database meeting ID
- **meeting_info.subject**: Meeting title/subject
- **meeting_info.start_time**: Meeting scheduled start (Eastern timezone)
- **meeting_info.end_time**: Meeting scheduled end (Eastern timezone)
- **meeting_info.duration_minutes**: Planned meeting duration
- **meeting_info.organizer**: Meeting organizer email
- **meeting_info.location**: Meeting location description
- **meeting_info.web_link**: Teams meeting join URL
- **meeting_info.meeting_type**: "teams", "phone", "in-person", or "other"
- **meeting_info.is_teams_meeting**: Boolean flag for Teams meetings
- **meeting_info.is_recurring**: Boolean flag for recurring meetings
- **meeting_info.attendee_count**: Total number of attendees
- **meeting_info.required_attendees**: Array of required attendee emails
- **meeting_info.optional_attendees**: Array of optional attendee emails
- **meeting_info.calendar_event_id**: Unique calendar/Exchange meeting ID
- **meeting_info.discovered_at**: When meeting was first discovered
- **meeting_info.is_linked_to_meeting**: Always true when meeting data present

### Meeting Information (when not linked)
- **meeting_info.is_linked_to_meeting**: Always false for standalone recordings

## Usage Notes

1. **Meeting Detection**: The system automatically links recordings to meetings when:
   - Recording is started from the meetings interface
   - Manual association is made in the admin panel

2. **File Availability**: All S3 URLs are publicly accessible and permanent

3. **Timezone Handling**: 
   - `created_at` uses local timezone
   - Meeting times (`start_time`, `end_time`) are in Eastern timezone
   - `upload_timestamp` is in ISO format with timezone info

4. **Error Handling**: Webhook is sent even if some files fail to upload, with only successful URLs included

5. **Authentication**: All requests include `X-Webhook-Token` header for verification