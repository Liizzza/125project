# Sleep Optimizer

A personalized sleep coaching app that analyzes your Apple Health sleep data to recommend optimal bedtimes, track sleep debt, and suggest calming content to help you wind down.

## Overview

Sleep Optimizer consists of an iOS SwiftUI frontend and a Python FastAPI backend. Users upload their Apple Health export, set their sleep preferences, and receive nightly recommendations tailored to their sleep patterns.

## Features

- **Sleep Analysis** — Parses Apple Health data to extract 30 nights of sleep history
- **Sleep Debt Tracking** — Calculates accumulated sleep debt with recency-weighted decay
- **Nightly Sleep Plan** — Recommends a personalized bedtime and wake time based on your debt, circadian rhythm, and constraints
- **Quality Labels** — Rates your sleep status (Well Rested, On Track, Recovering, High Debt, etc.)
- **Content Recommendations** — Suggests YouTube videos organized into two wind-down stages:
  - **Stage A (Wind Down)** — Longer ambient content for the hours before bed
  - **Stage B (Lights Out)** — Short, low-intensity content for the final 45 minutes
- **Nap Logging** — Log naps throughout the day; sleep debt and tonight's plan adjust automatically
- **Multi-User Support** — Isolated per-user data directories on the backend

## Tech Stack

| Layer | Technology |
|---|---|
| iOS Frontend | SwiftUI, URLSession, `@Observable` |
| Backend | Python, FastAPI, Pandas |
| Data | Apple Health XML export, JSON, CSV |

## Project Structure

```
├── main.py                        # FastAPI server and REST endpoints
├── scripts/
│   ├── extract_sleep.py           # Parses Apple Health export.xml → CSV
│   ├── build_sleep_nightly.py     # Aggregates per-night sleep metrics
│   ├── build_sleep_profile.py     # Compiles user sleep statistics
│   ├── make_sleep_plan.py         # Core algorithm: generates tonight's plan
│   ├── recommend_content.py       # Selects personalized content recommendations
│   └── run_tonight.py             # Orchestrates full pipeline, produces bundle
├── data/users/{user_id}/          # Per-user data (created at runtime)
│   ├── export.xml
│   ├── sleep_records.csv
│   ├── sleep_index_nightly.csv
│   ├── sleep_profile.json
│   ├── tomorrow_constraints.json
│   ├── tonight_plan.json
│   ├── tonight_content.json
│   ├── tonight_bundle.json
│   └── nap_log.json
├── requirements.txt
└── frontend/
    ├── SleepOptimizedApp.swift    # App entry point and navigation
    ├── Views/
    │   ├── WelcomeView.swift
    │   ├── LoginView.swift
    │   ├── UploadView.swift       # Health data upload (Step 1)
    │   ├── PreferencesView.swift  # Sleep goals and content prefs (Step 2)
    │   ├── DashboardView.swift    # Main dashboard
    │   └── NapView.swift          # Nap logging
    └── Utilities/
        ├── SleepAPIManager.swift  # API client and data models
        └── DocumentPicker.swift   # File picker for health export
```

## Getting Started

### Prerequisites

- Python 3.9+
- Xcode 15+ (for the iOS app)
- An iPhone with Apple Health data (or a simulator for testing)

### Backend

1. Clone the repo and navigate to the project root:
   ```bash
   git clone <repo-url>
   cd 125project
   ```

2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Start the server:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

   The API will be available at `http://localhost:8000`. You can view the auto-generated docs at `http://localhost:8000/docs`.

### iOS App

1. Open the Xcode project in `frontend/`.
2. In `SleepAPIManager.swift`, update `baseURL` to your machine's local IP address so the device can reach the backend on the same network:
   ```swift
   let baseURL = "http://<your-local-ip>:8000"
   ```
   You can find your local IP in System Settings → Network.
3. Select your target device or simulator and press **Run** (⌘R).

## How to Run It

### 1. Start the backend
```bash
source .venv/bin/activate
uvicorn main:app --host 0.0.0.0 --port 8000
```

### 2. Launch the iOS app
Open `frontend/` in Xcode and run on your device or simulator.

### 3. Export your Apple Health data
On your iPhone: **Health app → your profile picture → Export All Health Data**. This produces a `export.zip` — unzip it to get `export.xml`.

### 4. Upload and configure
- In the app, tap **Get Started** and upload your `export.xml`.
- On the next screen, set your sleep goal, wake time, and content preferences, then tap **Save**.

### 5. View your dashboard
The dashboard shows:
- Tonight's recommended **bedtime** and **wake time**
- Your current **sleep debt** and **quality label**
- A **content queue** for Stage A (wind-down) and Stage B (lights out)

### 6. Log a nap (optional)
Tap the nap button to log a nap. Choose a duration and the plan will recalculate automatically.

### 7. Refresh
Pull to refresh or tap the refresh button on the dashboard to regenerate tonight's plan with the latest data.

## Usage

1. **Export Apple Health data** from the Health app on your iPhone (Profile → Export All Health Data).
2. **Upload** the `export.xml` file in the app's Upload screen.
3. **Set your preferences** — target sleep hours, wake time, content category weights, and constraints.
4. **View your dashboard** — see tonight's recommended bedtime, sleep debt, and content queue.
5. **Log naps** as needed; the plan updates automatically.

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/upload/health-data` | Upload Apple Health XML |
| `POST` | `/users/{user_id}/preferences` | Save sleep preferences |
| `POST` | `/users/{user_id}/run/pipeline` | Run the full sleep analysis pipeline |
| `GET/POST` | `/users/{user_id}/tonight/bundle` | Get tonight's plan + content bundle |
| `POST` | `/users/{user_id}/nap` | Log a nap |
| `GET` | `/users/{user_id}/nap` | Get today's nap status |
| `GET` | `/users/{user_id}/sleep/plan` | Get tonight's sleep plan |
| `GET` | `/users/{user_id}/sleep/profile` | Get user sleep profile |
| `GET` | `/users/{user_id}/sleep/history` | Get sleep history |

## Sleep Plan Algorithm

The core algorithm in `make_sleep_plan.py`:

1. Calculates available sleep opportunity (now → wake constraint)
2. Computes sleep debt from 30-night history with recency weighting (5% daily decay)
3. Applies circadian rhythm scoring (9 PM–2 AM is the ideal window)
4. Factors in hard constraints (latest bedtime, minimum opportunity)
5. Outputs recommended bedtime, expected wake time, opportunity window, and quality label

## Content Recommendation Categories

| Category | Examples |
|---|---|
| Noise | Brown noise, white noise |
| Nature | Ambient nature sounds |
| Meditation | Mindfulness, breathwork |
| ASMR | Relaxation ASMR |
| Stories | Audiobooks, bedtime stories |
| Music | Calm instrumental music |
| Movement | Gentle stretching |
