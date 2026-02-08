# Netra - Advanced Visual Navigation Assistant

## Overview
Netra is an AI-powered assistive vision system designed to provide "socially aware" navigation for the visually impaired. Developed for the **Gemini 3 Hackathon**, it leverages **Google's Gemini 3 Flash** model to interpret environmental dynamics, recognize interpersonal intent, and maintain long-term spatial memory.

## Key Features
- **Social Intelligence:** Recognizes social cues like smiling or waving to distinguish between a passive bystander and someone seeking interaction.
- **Long-Term Spatial Memory:** Builds a "Memory Palace" of known locations, allowing the user to tag and relocate objects/places.
- **Micro-Navigation:** High-precision hand-to-object guidance for tasks like finding a keyhole or pressing an elevator button.
- **Interactive Task Guidance:** Step-by-step physical task assistance (e.g., "Help me make coffee") with real-time visual verification.
- **Multimodal Interaction:** Supports simultaneous video frame processing and voice command recognition via WebSockets.

## Technical Stack
- **AI Core:** Google Gemini 3 Flash (Multimodal)
- **Backend:** FastAPI, Uvicorn, Python 3.13+
- **Frontend:** HTML5, CSS3, Vanilla JavaScript (WebComponents-style architecture)
- **Real-time Communication:** WebSockets for low-latency video and audio streaming.

## Project Structure
- `main.py`: Entry point for the application.
- `app/`:
    - `config.py`: Centralized configuration and environment loading.
    - `prompts.py`: Highly engineered system prompts for different AI modes.
    - `services/`: Core logic for AI processing (`processor.py`), memory management (`memory.py`), and tracking.
    - `routes/`: WebSocket and page routing.
- `static/`: Frontend assets (JS, CSS, Images).
- `templates/`: UI templates.

## Walkthrough & Setup
### 1. Prerequisites
- Python 3.13 or higher.
- A valid Google Gemini API Key.

### 2. Installation
```bash
# Clone the repository
git clone <your-repo-url>
cd netra

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration
Create a `.env` file in the root directory:
```env
GEMINI_KEY=your_gemini_api_key_here
LOG_LEVEL=INFO
```

### 4. Running the App
```bash
python main.py
```
Access the dashboard at `http://localhost:5000`.

---
*Developed for the Gemini 3 Hackathon.*
