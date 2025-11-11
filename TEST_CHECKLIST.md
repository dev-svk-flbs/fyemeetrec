# Audio Recording System - Critical Test Checklist

## 20 Most Important Tests to Run

### 1. CORE RECORDING FUNCTIONALITY

#### Test 1: Basic Manual Recording
**Priority: CRITICAL**
- [ ] Open Flask app at http://localhost:5000
- [ ] Login with your credentials
- [ ] Go to Record page
- [ ] Select a monitor from dropdown
- [ ] Click "Start Recording"
- [ ] Record for 30 seconds
- [ ] Click "Stop Recording"
- [ ] Verify video file created in `/recordings/` folder
- [ ] Verify recording appears in Recordings page
- [ ] Check video duration matches recording time
- [ ] Verify audio is captured from VoiceMeeter B1

**Expected Result:**
- Recording completes successfully
- Video file exists with correct audio/video
- Database entry created with correct metadata
- Duration calculated correctly

---

#### Test 2: Hotkey Recording (Ctrl+Shift+F9/F10)
**Priority: CRITICAL**
- [ ] Ensure `launcher.py` is running (starts hotkey_listener.py)
- [ ] Press Ctrl+Shift+F9 to start recording
- [ ] Verify toast notification appears "Recording Started"
- [ ] Record for 30 seconds
- [ ] Press Ctrl+Shift+F10 to stop recording
- [ ] Verify toast notification appears "Recording Stopped"
- [ ] Check recording appears in Flask app
- [ ] Verify title format: "Hotkey Recording YYYY-MM-DD HH:MM"

**Expected Result:**
- Hotkeys trigger recording correctly
- Notifications show status
- Recording saved properly

---

#### Test 3: Multi-Monitor Selection
**Priority: HIGH**
- [ ] Go to Settings page
- [ ] Click "Detect Monitors" button
- [ ] Verify all monitors detected and displayed
- [ ] Note monitor positions and resolutions
- [ ] Start recording on Monitor 1
- [ ] Verify correct monitor captured
- [ ] Stop recording
- [ ] Change default monitor in Settings
- [ ] Start new recording
- [ ] Verify new monitor is captured

**Expected Result:**
- All monitors detected correctly
- Monitor switching works
- Correct screen captured each time

---

### 2. AUDIO SYSTEM TESTS

#### Test 4: VoiceMeeter B1 Audio Capture
**Priority: CRITICAL**
- [ ] Open VoiceMeeter (ensure installed)
- [ ] Route system audio to VoiceMeeter B1 output
- [ ] Play audio/video on computer
- [ ] Start recording
- [ ] Verify audio is being captured (speak/play audio)
- [ ] Stop recording
- [ ] Play back video file
- [ ] Confirm audio is present and clear

**Expected Result:**
- Audio from VoiceMeeter B1 captured successfully
- Audio quality is good
- No audio dropouts or sync issues

---

#### Test 5: Bluetooth Headset Integration
**Priority: MEDIUM**
- [ ] Run `bluetooth_endpoint_monitor.py`
- [ ] Connect Bluetooth headset
- [ ] Verify detection logged: "BLUETOOTH HEADSET CONNECTED!"
- [ ] Verify VoiceMeeter restart triggered
- [ ] Disconnect Bluetooth headset
- [ ] Verify detection logged: "BLUETOOTH HEADSET DISCONNECTED!"
- [ ] Start recording with Bluetooth connected
- [ ] Verify audio still captures from VoiceMeeter B1

**Expected Result:**
- Bluetooth connection/disconnection detected
- VoiceMeeter restarts automatically
- Recording continues working after Bluetooth events

---

### 3. MEETING INTEGRATION TESTS

#### Test 6: Calendar Meeting Sync
**Priority: HIGH**
- [ ] Go to Advanced page
- [ ] Click "Sync Calendar Now"
- [ ] Verify meetings synced from Microsoft Graph API
- [ ] Check meetings appear in Meetings page
- [ ] Verify meeting details: subject, organizer, time, attendees
- [ ] Check auto-record flag status
- [ ] Verify Teams meetings identified correctly

**Expected Result:**
- Calendar sync completes successfully
- Meetings saved to database
- All metadata accurate

---

#### Test 7: Link Recording to Meeting
**Priority: HIGH**
- [ ] Create a manual recording
- [ ] Go to Meetings page
- [ ] Find a past meeting with no recording
- [ ] Click "Link Recording" button
- [ ] Select the manual recording
- [ ] Verify recording linked successfully
- [ ] Check meeting status updates to "recorded"
- [ ] Verify recording shows meeting details

**Expected Result:**
- Recording successfully linked to meeting
- Status updates correctly
- Relationship persists in database

---

#### Test 8: Meeting Auto-Record Toggle
**Priority: MEDIUM**
- [ ] Go to Meetings page
- [ ] Find an upcoming meeting
- [ ] Click "Enable Auto-Record" toggle
- [ ] Verify status changes
- [ ] Disable auto-record
- [ ] Verify status changes back
- [ ] Check database `auto_record` field updates

**Expected Result:**
- Auto-record toggle works
- Database updates correctly
- UI reflects changes immediately

---

### 4. WEBSOCKET CLIENT TESTS

#### Test 9: WebSocket Connection to Server
**Priority: HIGH**
- [ ] Ensure `launcher.py` is running (includes websocket_client.py)
- [ ] Check logs: "Connected to remote control server"
- [ ] Verify user login detected: user email logged
- [ ] Check weekly meetings received (23 meetings message)
- [ ] Verify heartbeat messages sent every 30 seconds
- [ ] Check `weekly_meetings.json` file created
- [ ] Verify meetings synced to database

**Expected Result:**
- WebSocket connects successfully
- Meetings downloaded from server
- Local database synced with server meetings

---

#### Test 10: Remote Recording Start/Stop
**Priority: MEDIUM**
- [ ] WebSocket client connected
- [ ] From ops.fyelabs.com, send START command for a meeting
- [ ] Verify client receives command
- [ ] Verify recording starts automatically
- [ ] Check logs: "Remote START command received"
- [ ] From ops.fyelabs.com, send STOP command
- [ ] Verify recording stops
- [ ] Check logs: "Remote STOP command received"

**Expected Result:**
- Remote commands received
- Recording starts/stops remotely
- Status confirmed back to server

---

### 5. DATABASE & DATA INTEGRITY

#### Test 11: Database Recording Lifecycle
**Priority: CRITICAL**
- [ ] Start a recording
- [ ] While recording, check database for entry with status="recording"
- [ ] Stop recording
- [ ] Verify status updates to "completed"
- [ ] Check `duration` field calculated
- [ ] Verify `file_path` points to video file
- [ ] Check `file_size` is populated
- [ ] Verify `created_at` and `updated_at` timestamps

**Expected Result:**
- Database entry created on start
- All fields populated correctly
- Status updates through lifecycle

---

#### Test 12: Upload Retry System
**Priority: HIGH**
- [ ] Create a recording
- [ ] Simulate upload failure (disconnect internet)
- [ ] Click "Sync to Cloud"
- [ ] Verify retry queued
- [ ] Check retry_manager logs
- [ ] Reconnect internet
- [ ] Wait for automatic retry (background task)
- [ ] Verify upload succeeds
- [ ] Check `sync_status` updates to "synced"

**Expected Result:**
- Failed uploads queued for retry
- Automatic retry works
- Sync status tracked correctly

---

### 6. FILE MANAGEMENT TESTS

#### Test 13: Recording File Organization
**Priority: MEDIUM**
- [ ] Create multiple recordings
- [ ] Check `/recordings/` folder structure
- [ ] Verify naming: `{title}_{timestamp}.mp4`
- [ ] Check for transcript files: `{title}_{timestamp}_transcript.txt`
- [ ] Check for thumbnail files: `{title}_{timestamp}_thumbnail.jpg`
- [ ] Verify no duplicate files
- [ ] Check file permissions

**Expected Result:**
- Files organized correctly
- Naming convention consistent
- All related files grouped together

---

#### Test 14: Auto-Delete Old Recordings
**Priority: MEDIUM**
- [ ] Go to Settings
- [ ] Set "Auto-delete after" to 1 day
- [ ] Save settings
- [ ] Create test recording with old timestamp (manually adjust DB)
- [ ] Wait for cleanup job (runs every 6 hours) OR trigger manually
- [ ] Verify old recording deleted
- [ ] Check database entry status="deleted" or removed
- [ ] Verify cloud backup preserved (if synced)

**Expected Result:**
- Old recordings cleaned up automatically
- Cloud backups preserved
- Disk space freed

---

### 7. USER INTERFACE TESTS

#### Test 15: Dashboard Metrics
**Priority: LOW**
- [ ] Go to Dashboard
- [ ] Verify "Total Recordings" count is accurate
- [ ] Check "Storage Used" shows correct size
- [ ] Verify "Recent Recordings" list displays correctly
- [ ] Check "Upcoming Meetings" shows next meetings
- [ ] Verify all links work
- [ ] Test responsive layout on different screen sizes

**Expected Result:**
- All metrics accurate
- UI responsive and functional
- No broken links

---

#### Test 16: Settings Page Functionality
**Priority: HIGH**
- [ ] Go to Settings page
- [ ] Change default monitor
- [ ] Change auto-delete days
- [ ] Click "Save Settings"
- [ ] Verify success message appears
- [ ] Reload page
- [ ] Verify settings persisted
- [ ] Check `settings.config` file updated

**Expected Result:**
- Settings save successfully
- Changes persist after reload
- Config file updated correctly

---

### 8. ERROR HANDLING & EDGE CASES

#### Test 17: Recording Without Monitor Detection
**Priority: MEDIUM**
- [ ] Fresh install (no monitors detected)
- [ ] Try to start recording
- [ ] Verify error message shown
- [ ] Go to Settings → Detect Monitors
- [ ] Retry recording
- [ ] Verify works after detection

**Expected Result:**
- Graceful error handling
- Clear instructions to user
- Recovery path works

---

#### Test 18: Concurrent Recording Prevention
**Priority: HIGH**
- [ ] Start a recording via Flask UI
- [ ] While recording, try to start another via hotkey
- [ ] Verify error/warning shown
- [ ] Check only one FFmpeg process running
- [ ] Stop first recording
- [ ] Verify can start new recording

**Expected Result:**
- Only one recording at a time
- Clear error message
- State managed correctly

---

#### Test 19: FFmpeg Process Management
**Priority: CRITICAL**
- [ ] Start recording
- [ ] Check Task Manager for FFmpeg processes
- [ ] Count processes (should be 2: video + audio)
- [ ] Stop recording gracefully
- [ ] Verify FFmpeg processes terminated
- [ ] Force-stop app mid-recording (Ctrl+C)
- [ ] Check no orphaned FFmpeg processes
- [ ] Verify recording marked as "failed" in DB

**Expected Result:**
- FFmpeg processes managed correctly
- Clean shutdown
- No process leaks

---

#### Test 20: 3-Hour Auto-Stop Safety
**Priority: MEDIUM**
- [ ] Start a recording
- [ ] Let it run (or simulate 3+ hours elapsed)
- [ ] Verify auto-stop triggers at 3 hours
- [ ] Check logs: "Recording exceeded 3-hour limit"
- [ ] Verify recording saved up to 3 hours
- [ ] Check database status="completed"
- [ ] Verify file not corrupted

**Expected Result:**
- Auto-stop prevents infinite recordings
- Recording saved successfully
- Database updated correctly

---

## Additional Quick Checks

### System Health Checks
- [ ] Check all logs in `/logs/` folder for errors
- [ ] Verify `recordings.db` database file exists
- [ ] Check `settings.config` file is valid JSON
- [ ] Verify FFmpeg exists at `ffmpeg/bin/ffmpeg.exe`
- [ ] Test Flask app starts without errors
- [ ] Verify all dependencies installed (run `pip install -r requirements.txt`)

### Performance Checks
- [ ] Monitor CPU usage during recording (should be <50%)
- [ ] Check memory usage (should be <2GB)
- [ ] Verify video file size reasonable (~100MB per 10 min at 1080p)
- [ ] Test video playback is smooth
- [ ] Check disk I/O not bottlenecking

---

## Test Environment Setup

### Prerequisites
1. VoiceMeeter installed and configured
2. Multiple monitors connected (or virtual monitors for testing)
3. Internet connection for calendar sync
4. Microsoft account with calendar access
5. Sufficient disk space (>10GB free)

### Recommended Test Sequence
1. Run Tests 1-5 (Core functionality)
2. Run Tests 6-8 (Meeting integration)
3. Run Tests 9-10 (WebSocket/remote)
4. Run Tests 11-14 (Database & files)
5. Run Tests 15-16 (UI)
6. Run Tests 17-20 (Error handling)

---

## Bug Reporting Template

When you find an issue:

```
**Test Number:** #
**Test Name:** 
**Expected Result:** 
**Actual Result:** 
**Steps to Reproduce:**
1. 
2. 
3. 

**Logs/Screenshots:**
- Attach relevant log files from /logs/
- Include screenshots if UI issue

**System Info:**
- OS: Windows 10/11
- Python Version: 
- Number of Monitors: 
- VoiceMeeter Version: 
```

---

## Success Criteria

All 20 tests should pass with:
- No critical errors
- All core features working
- Acceptable performance
- Clean logs (no exceptions)
- Data integrity maintained

**Last Updated:** 2025-11-11
**Version:** 1.0
