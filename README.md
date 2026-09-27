# J.A.R.V.I.S. – Iron Man Voice Agent & OS Controller

![JARVIS Core Interface](https://via.placeholder.com/800x400/000408/00e5ff?text=J.A.R.V.I.S.+CORE+SYSTEM)

J.A.R.V.I.S. is an ultra-advanced, fully voice-activated AI assistant designed to replicate the Iron Man movie experience. Built with Python and Flask, powered by Google's Gemini models, and featuring a stunning holographic browser-based UI.

Unlike standard chatbots, JARVIS possesses **Full System Access** to your Windows operating system. It can execute terminal commands, press keyboard shortcuts, open applications, control browser tabs, and fetch real-time AI news.

## 🔥 Key Features

- **Holographic Core UI**: A full-screen, minimalist glowing core interface featuring matrix-style ambient particles, dynamic audio visualizers, and a permanent communication log.
- **Full OS Control (PowerShell/CMD)**: JARVIS is wired into the system substrate. Tell him to "Create a new folder on the desktop" or "Check my IP address", and he will execute the raw terminal commands in the background.
- **Keyboard & Typing Automation**: Integrated with `pyautogui`, you can say "Jarvis, press control T" or "Jarvis, type 'Hello World'" and he will emulate the keyboard perfectly.
- **Local Fast-Path Dispatcher**: Common commands like checking the time, opening apps, or launching Google/YouTube are executed instantly via a local regex engine—achieving 0ms latency by bypassing the LLM.
- **Smart Model Fallback**: Handles complex requests by falling back through Gemini 3.8 Flash, to Flash Latest, to Flash-Lite-Latest, ensuring maximum uptime and avoiding rate limits.
- **AI News Integration**: Pulls and caches the latest artificial intelligence news via RSS feeds, dynamically summarized upon request.
- **Continuous Wake Word**: Advanced continuous Speech Recognition in the browser. Say "Jarvis" in the middle of a sentence, and he instantly captures the command and executes it.

## ⚙️ Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/jarvis-voice-agent.git
   cd jarvis-voice-agent
   ```

2. **Install dependencies:**
   Ensure you have Python 3.10+ installed.
   ```bash
   pip install -r requirements.txt
   ```
   *(Make sure to manually install PyAutoGUI if you intend to use keyboard simulation: `pip install pyautogui`)*

3. **Configure Environment Variables:**
   Rename `.env.example` to `.env` and insert your Gemini API Key:
   ```env
   GEMINI_API_KEY=your_api_key_here
   ```

4. **Launch the Core:**
   ```bash
   python server.py
   ```
   Open your browser and navigate to `http://localhost:5000`.

## 🛡️ Security Warning
**This project gives the AI autonomous execution rights on your local terminal.** Do not expose the Flask server to the public internet without proper authentication, and be extremely careful what you instruct JARVIS to do (e.g., do not tell it to delete critical system files).

## 🛠️ Architecture
- **Frontend**: HTML5, Vanilla JavaScript, Web Speech API (Synthesis & Recognition), CSS3 Animations.
- **Backend**: Python, Flask, Subprocess, PyAutoGUI, Webbrowser.
- **Brain**: Google `gemini-1.5-flash-lite` API.

---
*Engineered to perfection.*
