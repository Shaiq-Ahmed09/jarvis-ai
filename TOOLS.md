# J.A.R.V.I.S. Windows System Control Scripts

## Audio & Volume
- **Mute Audio:**
  ```powershell
  (New-Object -ComObject Wscript.Shell).SendKeys([char]173)
  ```
- **Volume Down:**
  ```powershell
  (New-Object -ComObject Wscript.Shell).SendKeys([char]174)
  ```
- **Volume Up:**
  ```powershell
  (New-Object -ComObject Wscript.Shell).SendKeys([char]175)
  ```

## Workstation Security
- **Lock Windows Screen:**
  ```powershell
  rundll32.exe user32.dll,LockWorkStation
  ```

## Hardware Telemetry
- **Battery Status:**
  ```powershell
  Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining, BatteryStatus
  ```
- **CPU & Memory:**
  ```powershell
  Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory
  ```

## Applications
- **Launch Apps:**
  ```powershell
  Start-Process notepad.exe
  Start-Process chrome.exe
  Start-Process calc.exe
  ```

## Visual Intelligence & Neural Optical Navigation
- **Neural OCR Detection (`core/vision.py`):**
  Uses `rapidocr-onnxruntime` with OpenCV sub-pixel scaling to map interactive UI buttons, links, tabs, and menus in real time.
- **Autonomous Element Clicking (`click_element`):**
  Fuzzy and boundary-aware label matching locates target coordinates and executes native mouse clicks.
- **HUD Optical Sensory Feed (`look`):**
  Overlays Stark cyan targeting boxes and emerald reticles on acquired targets directly in the HUD `#optics-box` viewport.

## Autonomous Proactive Sentinel Daemon (`core/proactive.py`)
- **Morning Executive Briefing (`trigger_morning_briefing`):**
  Synthesizes atmospheric weather conditions, unread priority Gmail messages, and workstation telemetry every weekday at 09:00 AM (or on demand).
- **Hardware Sentinel:**
  Continuously monitors battery levels (discharging <= 20%) and sustained CPU thermal loads (>= 90%) with cooldown-protected alerts.
- **Media Observer:**
  Inspects active desktop windows (Spotify / YouTube) and proactively announces track changes.
- **Sentinel Management (`configure_sentinel`, `get_sentinel_status`):**
  Allows dynamic configuration of briefing schedules, thresholds, and inspection of recent diagnostic events.

## Zero-Downtime Local LLM Failover & Offline Mode (`core/local_llm.py`)
- **Local Ollama Integration (`http://localhost:11434`):**
  Connects to locally running Ollama with tool-calling models (`llama3.2:latest`, `phi3`).
- **Seamless Failover & Offline Guard (`toggle_offline_mode`):**
  Automatically routes to local Ollama on network loss, quota limits (429/503), or manual toggle, with secondary emergency heuristic failsafe ensuring zero downtime.
- **HUD Mode Synchronization:**
  Streams `NEURAL CORE // OFFLINE LOCAL MODE` status and telemetry directly to the Stark HUD header.

## Semantic Vector Memory Cortex (`core/memory_vector.py`)
- **Vector Storage Engine:**
  Powered by ChromaDB (`cortex_db/`) with a deterministic, lightweight 384-dimensional embedding generator matching `all-MiniLM-L6-v2` space without external network downloads.
- **Categorized Memory Architecture:**
  Classifies memory records into `PREFERENCE`, `WORKFLOW`, `PROJECT_NOTE`, and `IDENTITY`.
- **Dynamic Context Injection:**
  Performs real-time cosine semantic similarity retrieval on every turn (`system_prompt(query=user_text)`), injecting contextually relevant past memories with confidence percentage scores.
- **Autonomous Dialogue Extraction (`auto_extract_and_remember`):**
  Monitors natural conversation turns to automatically capture declared user preferences, names, and custom operational workflows.
- **Stark HUD Memory Drawer:**
  Interactive slide-out drawer featuring real-time semantic search filtering, category filter pills, confidence badges, timestamps, manual memory committing, and single-click vector purging.
