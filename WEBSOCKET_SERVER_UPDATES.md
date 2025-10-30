# WebSocket Server Updates for Premature Recording Stop Handling

## Overview
The client now detects and notifies the server when recordings stop prematurely (before the expected duration). The server should be updated to handle these notifications properly.

## New Message Types from Client

### 1. `recording_stopped_premature`
Sent when the client detects that a recording has stopped before its expected duration.

**Payload Structure:**
```json
{
  "type": "recording_stopped_premature",
  "timestamp": "2025-10-30T15:30:45.123456",
  "data": {
    "subject": "Team Standup Meeting",
    "organizer": "john@company.com",
    "start_time": "2025-10-30T15:00:00Z",
    "duration_actual": 450,
    "duration_expected": 3600,
    "reason": "User stopped recording manually or error occurred"
  }
}
```

**Fields:**
- `subject`: Meeting subject
- `organizer`: Meeting organizer email
- `start_time`: Meeting start time (ISO format)
- `duration_actual`: How many seconds the recording actually ran
- `duration_expected`: How many seconds the recording was supposed to run
- `reason`: Why it stopped (manual stop, error, etc.)

### 2. `stop_confirmed` (Enhanced)
Sent when recording stops successfully (scheduled or manual).

**Updated Payload:**
```json
{
  "type": "stop_confirmed",
  "timestamp": "2025-10-30T16:00:12.456789",
  "data": {
    "subject": "Team Standup Meeting",
    "organizer": "john@company.com",
    "start_time": "2025-10-30T15:00:00Z",
    "duration_actual": 3605,
    "duration_expected": 3600,
    "reason": "completed",
    "status": "success"
  }
}
```

**New Fields:**
- `duration_expected`: Expected duration in seconds
- `reason`: One of: `"completed"`, `"manual"`, `"premature"`, `"error"`
- `status`: `"success"` or `"failed"`

### 3. `recording_status` (Existing - Enhanced Frequency)
Now sent every 5 seconds (previously 30 seconds) for faster detection of issues.

**Payload:**
```json
{
  "type": "recording_status",
  "timestamp": "2025-10-30T15:05:10.123456",
  "data": {
    "subject": "Team Standup Meeting",
    "organizer": "john@company.com",
    "start_time": "2025-10-30T15:00:00Z",
    "status": "recording",
    "elapsed": 310,
    "remaining": 3290
  }
}
```

## Server-Side Implementation Recommendations

### 1. Message Handler Updates

```python
async def handle_client_message(websocket, message):
    """Handle incoming messages from recording client"""
    try:
        data = json.loads(message)
        msg_type = data.get('type')
        msg_data = data.get('data', {})
        timestamp = data.get('timestamp')
        
        if msg_type == 'recording_stopped_premature':
            await handle_premature_stop(websocket, msg_data, timestamp)
        
        elif msg_type == 'stop_confirmed':
            await handle_stop_confirmed(websocket, msg_data, timestamp)
        
        elif msg_type == 'recording_status':
            await handle_recording_status(websocket, msg_data, timestamp)
        
        # ... other message types ...
        
    except Exception as e:
        logger.error(f"Error handling message: {e}")
```

### 2. Premature Stop Handler

```python
async def handle_premature_stop(websocket, data, timestamp):
    """Handle notification that recording stopped before expected duration"""
    subject = data.get('subject')
    organizer = data.get('organizer')
    start_time = data.get('start_time')
    duration_actual = data.get('duration_actual')
    duration_expected = data.get('duration_expected')
    reason = data.get('reason')
    
    logger.warning(
        f"⚠️ Recording stopped prematurely: {subject}\n"
        f"   Expected: {duration_expected}s, Actual: {duration_actual}s\n"
        f"   Reason: {reason}"
    )
    
    # Update database record
    try:
        # Find the meeting/recording record
        recording = await find_recording_by_details(subject, organizer, start_time)
        
        if recording:
            # Update status to indicate premature stop
            recording.status = 'stopped_premature'
            recording.expected_duration = duration_expected
            recording.actual_duration = duration_actual
            recording.stop_reason = reason
            recording.stopped_at = datetime.fromisoformat(timestamp)
            
            await db.save(recording)
            
            logger.info(f"✅ Updated recording {recording.id} with premature stop info")
            
            # Optional: Send notification/alert
            await send_alert_notification(
                type="recording_premature_stop",
                recording_id=recording.id,
                subject=subject,
                organizer=organizer,
                duration_actual=duration_actual,
                duration_expected=duration_expected
            )
        else:
            logger.warning(f"Recording not found for premature stop: {subject}")
    
    except Exception as e:
        logger.error(f"Error handling premature stop: {e}")
```

### 3. Stop Confirmed Handler (Updated)

```python
async def handle_stop_confirmed(websocket, data, timestamp):
    """Handle recording stop confirmation"""
    subject = data.get('subject')
    organizer = data.get('organizer')
    start_time = data.get('start_time')
    duration_actual = data.get('duration_actual')
    duration_expected = data.get('duration_expected')
    reason = data.get('reason')
    status = data.get('status')
    
    logger.info(
        f"✅ Recording stopped: {subject}\n"
        f"   Duration: {duration_actual}s (expected: {duration_expected}s)\n"
        f"   Reason: {reason}, Status: {status}"
    )
    
    # Update database
    try:
        recording = await find_recording_by_details(subject, organizer, start_time)
        
        if recording:
            recording.status = 'completed' if status == 'success' else 'failed'
            recording.actual_duration = duration_actual
            recording.expected_duration = duration_expected
            recording.stop_reason = reason
            recording.stopped_at = datetime.fromisoformat(timestamp)
            
            # Check if it was premature (stopped more than 60 seconds early)
            if duration_expected - duration_actual > 60 and reason == 'manual':
                recording.status = 'stopped_early'
            
            await db.save(recording)
            
            logger.info(f"✅ Updated recording {recording.id} status: {recording.status}")
    
    except Exception as e:
        logger.error(f"Error updating recording: {e}")
```

### 4. Recording Status Tracker

```python
# Track active recordings on server side
active_recordings = {}

async def handle_recording_status(websocket, data, timestamp):
    """Handle periodic recording status updates"""
    subject = data.get('subject')
    organizer = data.get('organizer')
    start_time = data.get('start_time')
    status = data.get('status')
    elapsed = data.get('elapsed')
    remaining = data.get('remaining')
    
    # Create unique key for this recording
    recording_key = f"{organizer}:{subject}:{start_time}"
    
    # Update tracking
    active_recordings[recording_key] = {
        'subject': subject,
        'organizer': organizer,
        'start_time': start_time,
        'status': status,
        'elapsed': elapsed,
        'remaining': remaining,
        'last_update': timestamp,
        'websocket': websocket
    }
    
    logger.debug(f"Recording status: {subject} - {elapsed}s elapsed, {remaining}s remaining")
    
    # Optional: Check for stale recordings (no update in 60 seconds)
    await check_stale_recordings()

async def check_stale_recordings():
    """Check for recordings that haven't sent updates recently"""
    now = datetime.now()
    stale_threshold = 60  # seconds
    
    stale_keys = []
    for key, info in active_recordings.items():
        last_update = datetime.fromisoformat(info['last_update'])
        if (now - last_update).total_seconds() > stale_threshold:
            logger.warning(f"⚠️ Stale recording detected: {info['subject']}")
            stale_keys.append(key)
            
            # Send alert
            await send_alert_notification(
                type="recording_stale",
                subject=info['subject'],
                organizer=info['organizer'],
                last_update=info['last_update']
            )
    
    # Remove stale recordings
    for key in stale_keys:
        del active_recordings[key]
```

## Database Schema Updates

### Recommended Fields for Recording Table

```python
class Recording(Base):
    __tablename__ = 'recordings'
    
    id = Column(Integer, primary_key=True)
    subject = Column(String(500))
    organizer = Column(String(255))
    start_time = Column(DateTime)
    
    # Status tracking
    status = Column(String(50))  # 'recording', 'completed', 'failed', 'stopped_premature', 'stopped_early'
    
    # Duration tracking
    expected_duration = Column(Integer)  # In seconds
    actual_duration = Column(Integer)    # In seconds
    
    # Stop reason
    stop_reason = Column(String(100))  # 'completed', 'manual', 'premature', 'error'
    
    # Timestamps
    started_at = Column(DateTime)
    stopped_at = Column(DateTime)
    
    # Video file (will be uploaded separately)
    video_url = Column(String(500))
    file_size = Column(BigInteger)
```

## Event Flow Diagram

```
Client Side                          Server Side
-----------                          -----------

Recording Started
     |
     ├─> "start_confirmed" ────────> Store in active_recordings{}
     |                                Update DB: status='recording'
     |
Every 5s during recording
     |
     ├─> "recording_status" ────────> Update active_recordings{}
     |                                Track elapsed/remaining time
     |
If user stops manually OR error
     |
     ├─> "recording_stopped_premature" ──> Update DB: status='stopped_premature'
     |                                      Send alert notification
     |                                      Remove from active_recordings{}
     |
If recording completes normally
     |
     └─> "stop_confirmed" ──────────> Update DB: status='completed'
                                       Remove from active_recordings{}
                                       Wait for video upload webhook
```

## Testing Scenarios

### Test 1: Normal Completion
1. Start recording with 60 minute duration
2. Wait full 60 minutes
3. Verify `stop_confirmed` received with `reason: "completed"`
4. Verify `duration_actual` ≈ `duration_expected`

### Test 2: Manual Stop
1. Start recording with 60 minute duration
2. User clicks "Stop Recording" after 10 minutes
3. Verify `recording_stopped_premature` received
4. Verify `duration_actual` = ~600s, `duration_expected` = 3600s

### Test 3: Client Crash
1. Start recording
2. Kill client process after 5 minutes
3. Verify server detects stale recording after 60s
4. Verify alert notification sent

### Test 4: Network Disconnect
1. Start recording
2. Disconnect network after 10 minutes
3. Recording continues locally
4. Reconnect network
5. Verify premature stop notification sent when client reconnects

### Test 5: 3-Hour Hard Limit (Remote Triggered)
1. Start recording via websocket command with 4-hour duration
2. Wait 3 hours (or simulate by adjusting system time)
3. Verify recording auto-stops at exactly 3 hours
4. Verify `recording_stopped_premature` sent with reason="automatic_limit"
5. Verify `duration_actual` ≈ 10800s (3 hours)

### Test 6: 3-Hour Hard Limit (Manual)
1. User clicks "Record" button manually
2. User forgets to stop recording
3. After 3 hours, recording auto-stops
4. Verify no websocket notification (was manual recording)
5. Verify video file and metadata are properly saved

## 3-Hour Hard Limit Feature

### Overview
A fail-safe has been implemented to automatically stop any recording that exceeds 3 hours (10,800 seconds). This prevents:
- Users forgetting to stop manual/ad-hoc recordings
- Disk space exhaustion from runaway recordings
- Accidental overnight recordings

### Implementation Details

**Client Side (Flask App):**
- Background monitor thread checks recording duration every 30 seconds
- If recording exceeds 3 hours, automatically stops it
- Tracks whether recording was remote-triggered or manual
- Remote-triggered recordings will notify the websocket server via the premature stop mechanism

**Server Side Behavior:**
- Remote-triggered recordings: Server receives `recording_stopped_premature` with reason indicating auto-stop
- Manual recordings: No websocket notification (user wasn't expecting specific duration anyway)

**Example Log Output:**
```
⚠️ Recording exceeded 3-hour limit (10805s) - auto-stopping!
✅ Recording auto-stopped (3-hour limit)
📡 Recording was remote-triggered - websocket client will notify server
```

### Configuration

Client side constant (in `app.py`):
```python
# Maximum recording duration (3 hours in seconds)
MAX_RECORDING_DURATION = 3 * 60 * 60  # 10800 seconds
```

Server config (add to your server configuration):
```python
RECORDING_MONITOR_CONFIG = {
    'status_update_interval': 5,      # How often clients send status (seconds)
    'stale_threshold': 60,             # When to consider recording stale (seconds)
    'premature_stop_threshold': 60,    # Minimum seconds early to flag as premature
    'max_recording_duration': 10800,   # 3 hours hard limit (matches client)
    'enable_alerts': True,             # Send notifications for premature stops
    'alert_channels': ['email', 'slack']  # Where to send alerts
}
```

## Summary of Changes

### Client Changes (Already Implemented)
✅ Monitor recording status every 5 seconds
✅ Detect premature stops by checking Flask health API
✅ Send `recording_stopped_premature` message with duration info
✅ Enhanced `stop_confirmed` with reason and expected duration
✅ Added reason parameter to all stop operations
✅ **3-hour hard limit** - automatically stops any recording after 3 hours
✅ Track remote vs manual recordings to determine websocket notification
✅ Background duration monitor thread running continuously

### Server Changes (Recommended)
- [ ] Add handler for `recording_stopped_premature` messages
- [ ] Update `stop_confirmed` handler to process new fields
- [ ] Track active recordings in memory for monitoring
- [ ] Detect stale recordings (no update in 60 seconds)
- [ ] Add database fields for duration tracking and stop reason
- [ ] Implement alert system for premature stops
- [ ] Add dashboard view to show active recordings
- [ ] Log all premature stops for analysis

## Benefits

1. **Clean Process Flow**: Server always knows when recordings stop, regardless of reason
2. **Better Monitoring**: Track expected vs actual duration for all recordings
3. **Proactive Alerts**: Get notified immediately when recordings stop unexpectedly
4. **Data Integrity**: Even if client crashes, server will eventually detect stale recording
5. **Analytics**: Collect data on why recordings stop prematurely (user action, errors, etc.)
6. **Debugging**: Easier to troubleshoot issues with detailed stop reasons and duration tracking
