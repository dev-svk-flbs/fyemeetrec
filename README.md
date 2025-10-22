# 🎯 Professional Recording & Upload System

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  Local Web UI   │    │  Local Recorder  │    │  Upload Server  │
│  (port 5000)    │───▶│  dual_stream.py  │───▶│  (port 8000)    │
│                 │    │                  │    │                 │
│ • Start/Stop    │    │ • Screen capture │    │ • File storage  │
│ • Live text     │    │ • Transcription  │    │ • Text logging  │
│ • Upload status │    │ • Auto upload    │    │ • Status API    │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Components

### 1. Local Web Interface (`app.py`)
- Clean start/stop recording UI
- Live transcription feed  
- Upload progress tracking
- Non-blocking operation

### 2. Recording Engine (`dual_stream.py`) 
- Screen + audio capture (VoiceMeeter B1)
- Real-time Faster-Whisper transcription
- Professional video encoding
- Background upload (non-blocking)

### 3. Upload Server (`upload_server.py`)
- Professional file receiver
- Transcription logging
- Status monitoring
- Large file handling (up to 500MB)

## Quick Start

### 1. Start Upload Server (on your server)
```bash
python upload_server.py
```
- Runs on port 8000
- Creates `uploads/` folder
- Receives files and transcriptions

### 2. Start Local Web UI
```bash
python app.py  
```
- Runs on http://localhost:5000
- Simple start/stop interface
- Live transcription display

### 3. Use the Interface
1. Open http://localhost:5000
2. Click "Start Recording"
3. See live transcriptions appear
4. Click "Stop Recording" when done
5. File automatically uploads in background

## Features

✅ **True start/stop recording** (no duration limits)  
✅ **Live transcription** with Faster-Whisper  
✅ **Professional video quality** with audio filters  
✅ **Background upload** (UI never freezes)  
✅ **Upload progress tracking**  
✅ **Large file support** (up to 500MB)  
✅ **Automatic transcription logging**  

## File Output

- **Videos**: `uploads/videos/meeting_YYYYMMDD_HHMMSS.mkv`
- **Transcriptions**: `uploads/videos/meeting_YYYYMMDD_HHMMSS.json`

## Performance

- **Recording**: Real-time, no performance impact
- **Transcription**: ~1 second latency, <30% CPU  
- **Upload**: Background thread, non-blocking
- **Large files**: Chunked upload with timeout handling

## Dependencies

```bash
pip install flask faster-whisper requests numpy
```

## Configuration

Edit server IP in `dual_stream.py`:
```python
def __init__(self, server_ip="YOUR_SERVER_IP", server_port=8000):
```