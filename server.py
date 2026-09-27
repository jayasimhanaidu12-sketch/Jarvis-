"""
JARVIS Voice Agent — Senior-Grade Flask Backend
================================================
Performance Architecture:
  1. LOCAL FAST-PATH  — regex dispatcher handles open/time/calculate/news
     instantly (<5ms), no AI call needed.
  2. GEMINI SMART PATH — for everything else; single-model-call tool loop.
  3. UNICODE-SAFE      — all console output ASCII-safe for Windows cp1252.
"""

import os, sys, re, time, json, math, webbrowser, threading, datetime, subprocess, unicodedata, pyautogui
from urllib.parse import quote_plus

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai
from google.genai import types
from ddgs import DDGS
import wikipedia
import requests
from news_agent import get_top_ai_news, format_news_for_speech, format_news_for_display

# ── Unbuffered output (ASCII-safe for Windows) ───────────────────────────────
sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
sys.stderr.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")

# ── Config ───────────────────────────────────────────────────────────────────
load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY", "").strip().strip('"').strip("'")
if not API_KEY or API_KEY in ("your_gemini_api_key_here", "PUT_YOUR_API_KEY_HERE"):
    raise SystemExit("GEMINI_API_KEY missing — check your .env file.")

client = genai.Client(api_key=API_KEY)
MODELS = ["gemini-3.8-flash", "gemini-flash-latest", "gemini-flash-lite-latest"]

# ── System prompt ────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are JARVIS, a powerful personal AI voice assistant modeled on the Iron Man movie AI.
You answer spoken voice commands. Your responses will be read aloud.

=== TOOL PROTOCOL ===
When a task needs a tool, reply with ONLY a JSON object on a SINGLE line (no markdown):
{"tool": "<tool_name>", "args": {"key": "value"}}

Available tools:
  web_search    - {"tool": "web_search", "args": {"query": "..."}}
  wikipedia     - {"tool": "wikipedia", "args": {"query": "..."}}
  open_url      - {"tool": "open_url", "args": {"url": "https://..."}}
  open_google   - {"tool": "open_google", "args": {"query": "..."}}
  open_youtube  - {"tool": "open_youtube", "args": {"query": "..."}}
  weather       - {"tool": "weather", "args": {"location": "..."}}
  calculate     - {"tool": "calculate", "args": {"expr": "2 + 2"}}
  datetime      - {"tool": "datetime", "args": {}}
  open_app      - {"tool": "open_app", "args": {"app": "notepad"}}
  ai_news       - {"tool": "ai_news", "args": {"count": 5}}
  run_command   - {"tool": "run_command", "args": {"command": "dir"}}
  press_keys    - {"tool": "press_keys", "args": {"keys": "ctrl,t"}}
  type_text     - {"tool": "type_text", "args": {"text": "hello world"}}

=== RULES ===
- You have FULL KEYBOARD & SYSTEM ACCESS. 
- If the user asks you to do something to their computer (e.g., create a file/folder, change volume), use `run_command`.
- If the user asks you to press a keyboard shortcut (e.g., "control T", "enter", "alt tab") or type something out, use `press_keys` or `type_text`. For `press_keys`, use comma-separated key names (e.g. "win,d", "ctrl,t").
- Respond conversationally in plain spoken English (no markdown, no bullet points).
- Keep responses concise — they will be spoken aloud.
- Address the user as "sir".
- Use tools whenever the user asks to search, look up, open, browse, calculate, get the time/date/weather, control the computer, or simulate typing.
- After receiving tool results, give a concise spoken summary of the key findings or confirm the action was done.
- Never make up facts — search if you don't know.
"""

# ═══════════════════════════════════════════════════════════════════════════
#  TOOL FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════

def _safe(text: str) -> str:
    """Strip non-ASCII chars that Windows cp1252 can't handle."""
    return unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode("ascii")

def tool_web_search(query: str) -> str:
    try:
        results = list(DDGS().text(query, max_results=5))
        if not results:
            return "No results found."
        lines = []
        for r in results[:4]:
            title = _safe(r.get("title", ""))
            body  = _safe(r.get("body", ""))[:200]
            lines.append(f"* {title}: {body}")
        return "\n".join(lines)
    except Exception as e:
        return f"Search error: {e}"

def tool_wikipedia(query: str) -> str:
    try:
        wikipedia.set_lang("en")
        summary = wikipedia.summary(query, sentences=4, auto_suggest=True)
        return _safe(summary)
    except wikipedia.exceptions.DisambiguationError as e:
        try:
            return _safe(wikipedia.summary(e.options[0], sentences=4))
        except:
            return f"Multiple results: {', '.join(e.options[:5])}"
    except Exception as e:
        return f"Wikipedia error: {e}"

def _win_open(url_or_path: str):
    """Open URL or file reliably on Windows."""
    subprocess.Popen(f'start "" "{url_or_path}"', shell=True)

def tool_open_url(url: str) -> str:
    _win_open(url)
    return f"Opened: {url}"

def tool_open_google(query: str) -> str:
    url = f"https://www.google.com/search?q={quote_plus(query)}"
    _win_open(url)
    return f"Opened Google search for: {query}"

def tool_open_youtube(query: str) -> str:
    url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
    _win_open(url)
    return f"Opened YouTube search for: {query}"

def tool_weather(location: str) -> str:
    try:
        url  = f"https://wttr.in/{quote_plus(location)}?format=3"
        resp = requests.get(url, timeout=5)
        return _safe(resp.text.strip())
    except Exception as e:
        return f"Weather fetch error: {e}"

def tool_calculate(expr: str) -> str:
    try:
        allowed = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
        allowed.update({"abs": abs, "round": round, "int": int, "float": float})
        result = eval(expr, {"__builtins__": {}}, allowed)
        return f"{expr} = {result}"
    except Exception as e:
        return f"Calculation error: {e}"

def tool_datetime(_args) -> str:
    now = datetime.datetime.now()
    return now.strftime("The current date is %A, %B %d, %Y. The time is %I:%M %p.")

def tool_open_app(app: str) -> str:
    key = app.lower().strip()
    # ── Canonical app map ───────────────────────────────────────────────────
    app_map = {
        # System utilities
        "explorer":              "explorer.exe",
        "file explorer":         "explorer.exe",
        "windows explorer":      "explorer.exe",
        "files":                 "explorer.exe",
        "my computer":           "explorer.exe",
        "this pc":               "explorer.exe",
        "notepad":               "notepad",
        "calculator":            "calc",
        "calc":                  "calc",
        "paint":                 "mspaint",
        "cmd":                   "cmd",
        "command prompt":        "cmd",
        "terminal":              "cmd",
        "powershell":            "powershell",
        "task manager":          "taskmgr",
        "control panel":         "control",
        "settings":              "ms-settings:",
        "windows settings":      "ms-settings:",
        "snipping tool":         "SnippingTool",
        "snip":                  "SnippingTool",
        "wordpad":               "write",
        "paint 3d":              "paint3d",
        "sticky notes":          "stikynot",
        # Browsers
        "edge":                  "msedge",
        "microsoft edge":        "msedge",
        "ms edge":               "msedge",
        "chrome":                "chrome",
        "google chrome":         "chrome",
        "firefox":               "firefox",
        "brave":                 "brave",
        "browser":               "browser",
        "new tab":               "browser",
        # Office
        "word":                  "winword",
        "excel":                 "excel",
        "powerpoint":            "powerpnt",
        "outlook":               "outlook",
        "teams":                 "teams",
        "microsoft teams":       "teams",
        "onenote":               "onenote",
        # Dev tools
        "vscode":                "code",
        "vs code":               "code",
        "visual studio code":    "code",
        "visual studio":         "devenv",
        "github desktop":        "githubdesktop",
        # Media
        "spotify":               "spotify",
        "vlc":                   "vlc",
        "media player":          "wmplayer",
        "photos":                "ms-photos:",
        # Communication
        "discord":               "discord",
        "slack":                 "slack",
        "zoom":                  "zoom",
        "skype":                 "skype",
        "whatsapp":              "whatsapp",
        "telegram":              "telegram",
        # Other
        "steam":                 "steam",
        "notion":                "notion",
    }
    cmd = app_map.get(key, key)
    try:
        # Safely open browsers using Python's native webbrowser to avoid profile lock issues
        if cmd in ["browser", "chrome", "msedge", "firefox", "brave"]:
            webbrowser.open_new_tab("https://www.google.com")
        elif cmd == "google":
            webbrowser.open_new_tab("https://www.google.com")
        elif cmd == "youtube":
            webbrowser.open_new_tab("https://www.youtube.com")
        elif cmd.startswith("ms-"):
            subprocess.Popen(f"start {cmd}", shell=True)
        elif cmd == "explorer.exe":
            # Force open File Explorer window
            subprocess.Popen(["explorer.exe"])
        else:
            # For registered apps like 'chrome', 'msedge', 'winword', etc., 'start <name>' works perfectly
            subprocess.Popen(f"start {cmd}", shell=True)
        print(f"  [APP] Opened: {cmd}")
        return f"Opened {app}."
    except Exception as e:
        print(f"  [APP ERROR] {e}")
        return f"Could not open {app}: {e}"

# ── News cache ───────────────────────────────────────────────────────────────
_news_cache      = []
_news_cache_time = 0.0
NEWS_CACHE_TTL   = 30 * 60  # 30 minutes

def tool_ai_news(count: int = 5) -> str:
    global _news_cache, _news_cache_time
    now = time.time()
    if not _news_cache or (now - _news_cache_time) > NEWS_CACHE_TTL:
        print("  [NEWS] Fetching fresh AI news from RSS feeds...")
        _news_cache      = get_top_ai_news(count=10)
        _news_cache_time = now
    else:
        print("  [NEWS] Using cached news.")
    return format_news_for_speech(_news_cache[:count], max_items=count)

def tool_run_command(command: str) -> str:
    print(f"  [CMD] Executing: {command}")
    try:
        # Run the command with a timeout to prevent hanging
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=15
        )
        output = (result.stdout.strip() + "\n" + result.stderr.strip()).strip()
        return output if output else "Command executed successfully with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as e:
        return f"Command execution error: {e}"

def tool_press_keys(keys: str) -> str:
    print(f"  [KEYBOARD] Pressing: {keys}")
    try:
        key_list = [k.strip().lower() for k in keys.split(',')]
        pyautogui.hotkey(*key_list)
        return f"Pressed keys: {keys}"
    except Exception as e:
        return f"Error pressing keys: {e}"

def tool_type_text(text: str) -> str:
    print(f"  [KEYBOARD] Typing: {text}")
    try:
        pyautogui.write(text, interval=0.02)
        return f"Typed text: {text}"
    except Exception as e:
        return f"Error typing text: {e}"

TOOLS = {
    "web_search":   lambda a: tool_web_search(a["query"]),
    "wikipedia":    lambda a: tool_wikipedia(a["query"]),
    "open_url":     lambda a: tool_open_url(a["url"]),
    "open_google":  lambda a: tool_open_google(a["query"]),
    "open_youtube": lambda a: tool_open_youtube(a["query"]),
    "weather":      lambda a: tool_weather(a["location"]),
    "calculate":    lambda a: tool_calculate(a["expr"]),
    "datetime":     lambda a: tool_datetime(a),
    "open_app":     lambda a: tool_open_app(a["app"]),
    "ai_news":      lambda a: tool_ai_news(int(a.get("count", 5))),
    "run_command":  lambda a: tool_run_command(a["command"]),
    "press_keys":   lambda a: tool_press_keys(a["keys"]),
    "type_text":    lambda a: tool_type_text(a["text"]),
}

# ═══════════════════════════════════════════════════════════════════════════
#  LOCAL FAST-PATH DISPATCHER  (zero AI round-trip for common commands)
# ═══════════════════════════════════════════════════════════════════════════

# App name patterns extracted from voice input
_APP_KEYWORDS = {
    r"\b(file explorer|windows explorer|explorer|my computer|this pc|files)\b": "file explorer",
    r"\b(notepad)\b":                  "notepad",
    r"\b(calculator|calc)\b":          "calculator",
    r"\b(paint 3d)\b":                 "paint 3d",
    r"\b(paint)\b":                    "paint",
    r"\b(cmd|command prompt|terminal)\b": "cmd",
    r"\b(powershell)\b":               "powershell",
    r"\b(task manager)\b":             "task manager",
    r"\b(control panel)\b":            "control panel",
    r"\b(settings|windows settings)\b": "settings",
    r"\b(snipping tool|snip)\b":       "snipping tool",
    r"\b(spotify)\b":                  "spotify",
    r"\b(discord)\b":                  "discord",
    r"\b(vs ?code|visual studio code)\b": "vs code",
    r"\b(visual studio)\b":            "visual studio",
    r"\b(edge|microsoft edge|ms edge)\b": "microsoft edge",
    r"\b(chrome|google chrome)\b":     "chrome",
    r"\b(firefox)\b":                  "firefox",
    r"\b(browser|new tab)\b":          "browser",
    r"\b(google)\b":                   "google",
    r"\b(youtube)\b":                  "youtube",
    r"\b(word)\b":                     "word",
    r"\b(excel)\b":                    "excel",
    r"\b(powerpoint)\b":               "powerpoint",
    r"\b(outlook)\b":                  "outlook",
    r"\b(teams|microsoft teams)\b":    "teams",
    r"\b(vlc)\b":                      "vlc",
    r"\b(zoom)\b":                     "zoom",
    r"\b(steam)\b":                    "steam",
    r"\b(telegram)\b":                 "telegram",
    r"\b(whatsapp)\b":                 "whatsapp",
    r"\b(slack)\b":                    "slack",
    r"\b(notion)\b":                   "notion",
}

def _fast_dispatch(text: str):
    """
    Try to handle text locally without calling Gemini.
    Returns (reply, tool_log) or None if not handled.
    """
    t = text.lower().strip()

    # ── Time / Date ──────────────────────────────────────────────────────
    if re.search(r"\b(time|date|day|today|what day)\b", t):
        result = tool_datetime({})
        return result, [{"tool": "datetime", "args": {}, "result": result}]

    # ── Calculation ──────────────────────────────────────────────────────
    calc_match = re.search(
        r"(?:calculate|compute|what(?:'s| is)\s+)?(\d[\d\s\+\-\*\/\^\(\)\.]+)", t
    )
    if calc_match and any(op in calc_match.group(1) for op in ["+", "-", "*", "/", "^"]):
        expr = calc_match.group(1).strip()
        result = tool_calculate(expr)
        return f"The answer is {result}, sir.", [{"tool": "calculate", "args": {"expr": expr}, "result": result}]

    # ── Open App ─────────────────────────────────────────────────────────
    if re.search(r"\b(open|launch|start|run|show me)\b", t):
        for pattern, app_name in _APP_KEYWORDS.items():
            if re.search(pattern, t, re.IGNORECASE):
                result = tool_open_app(app_name)
                reply  = f"Opening {app_name} for you now, sir."
                return reply, [{"tool": "open_app", "args": {"app": app_name}, "result": result}]

        # YouTube open
        yt = re.search(r"\b(open|play|search)\b.+?\b(?:on\s+)?youtube\b(?:\s+for\s+(.+))?", t)
        if yt:
            query = yt.group(2) or re.sub(r"open|play|search|on|youtube|for", "", t).strip()
            result = tool_open_youtube(query)
            return f"Opening YouTube for {query}, sir.", [{"tool": "open_youtube", "args": {"query": query}, "result": result}]

        # Google open
        goog = re.search(r"\b(google|search)\b.+?(?:for\s+)?(.+)", t)
        if goog:
            query  = goog.group(2).strip()
            result = tool_open_google(query)
            return f"Searching Google for {query}, sir.", [{"tool": "open_google", "args": {"query": query}, "result": result}]

    # ── AI News ──────────────────────────────────────────────────────────
    if re.search(r"\b(news|headlines|ai news|latest)\b", t):
        result = tool_ai_news(5)
        return result, [{"tool": "ai_news", "args": {"count": 5}, "result": "news fetched"}]

    return None  # Not handled locally — fall through to Gemini

# ═══════════════════════════════════════════════════════════════════════════
#  GEMINI CALL WITH RETRY + MODEL FALLBACK
# ═══════════════════════════════════════════════════════════════════════════

def parse_tool_call(text: str):
    text = text.strip()
    
    # Try direct parse
    try:
        if text.startswith("{") and text.endswith("}"):
            obj = json.loads(text)
            return obj.get("tool"), obj.get("args", {})
    except:
        pass

    # Fallback to finding outermost braces
    try:
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            obj = json.loads(text[start:end+1])
            return obj.get("tool"), obj.get("args", {})
    except:
        pass

    return None, None

def call_gemini(history):
    for model_id in MODELS:
        for attempt in range(2):
            try:
                print(f"  [AI] {model_id} attempt {attempt+1}...")
                resp = client.models.generate_content(
                    model=model_id,
                    contents=history,
                    config=types.GenerateContentConfig(
                        system_instruction=SYSTEM_PROMPT,
                        temperature=0.7,
                        max_output_tokens=512,
                    ),
                )
                return resp.text.strip(), model_id
            except Exception as e:
                err = str(e)
                print(f"  [WARN] {model_id} failed: {err[:80]}")
                if "503" in err or "UNAVAILABLE" in err:
                    time.sleep(1)
                    continue
                break
    return None, None

# ── Conversation history (persistent per-session) ────────────────────────────
conversation_history = []

# ═══════════════════════════════════════════════════════════════════════════
#  FLASK APP
# ═══════════════════════════════════════════════════════════════════════════
app = Flask(__name__)
CORS(app)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/status")
def status():
    return jsonify({"status": "online", "agent": "JARVIS", "model": MODELS[0]})

@app.route("/api/chat", methods=["POST"])
def chat():
    data      = request.get_json(force=True)
    user_text = data.get("text", "").strip()
    print(f"\n[USER] {user_text}")

    if not user_text:
        return jsonify({"error": "Empty"}), 400

    # ── FAST PATH — handle locally with zero AI latency ──────────────────
    fast_result = _fast_dispatch(user_text)
    if fast_result is not None:
        reply, tool_log = fast_result
        print(f"  [FAST] {reply[:120]}")
        # Still add to conversation history for context continuity
        conversation_history.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
        )
        conversation_history.append(
            types.Content(role="model", parts=[types.Part.from_text(text=reply)])
        )
        if len(conversation_history) > 30:
            del conversation_history[0:2]
        return jsonify({"reply": reply, "tools": tool_log}), 200

    # ── SMART PATH — Gemini handles complex queries ───────────────────────
    conversation_history.append(
        types.Content(role="user", parts=[types.Part.from_text(text=user_text)])
    )

    tool_log = []
    for _ in range(3):  # max 3 tool rounds
        raw, used_model = call_gemini(conversation_history)

        if raw is None:
            if conversation_history and conversation_history[-1].role == "user":
                conversation_history.pop()
            return jsonify({
                "reply": "All AI models are under heavy load right now, sir. Please try again in a moment.",
                "tools": tool_log
            }), 200

        tool_name, tool_args = parse_tool_call(raw)

        if tool_name and tool_name in TOOLS:
            print(f"  [TOOL] {tool_name}({tool_args})")
            try:
                tool_result = TOOLS[tool_name](tool_args)
            except Exception as e:
                tool_result = f"Tool error: {e}"
            print(f"  [RESULT] {str(tool_result)[:200]}")
            tool_log.append({"tool": tool_name, "args": tool_args, "result": str(tool_result)[:300]})

            conversation_history.append(
                types.Content(role="model", parts=[types.Part.from_text(text=raw)])
            )
            conversation_history.append(
                types.Content(role="user", parts=[types.Part.from_text(
                    text=f"[Tool result for {tool_name}]: {tool_result}\n\nNow give the user a concise spoken summary."
                )])
            )
            continue

        else:
            # Final answer
            conversation_history.append(
                types.Content(role="model", parts=[types.Part.from_text(text=raw)])
            )
            if len(conversation_history) > 30:
                del conversation_history[0:2]
            print(f"  [JARVIS] ({used_model}): {raw[:120]}")
            return jsonify({"reply": raw, "tools": tool_log}), 200

    if conversation_history and conversation_history[-1].role == "user":
        conversation_history.pop()
    return jsonify({"reply": "I ran into a processing loop, sir. Could you rephrase that?", "tools": tool_log}), 200


@app.route("/api/news")
def get_news():
    """Returns top AI news as JSON for the frontend news panel."""
    global _news_cache, _news_cache_time
    now = time.time()
    if not _news_cache or (now - _news_cache_time) > NEWS_CACHE_TTL:
        print("  [NEWS] /api/news: Fetching fresh news...")
        _news_cache      = get_top_ai_news(count=10)
        _news_cache_time = now
    return jsonify({
        "articles": format_news_for_display(_news_cache),
        "fetched_at": datetime.datetime.now().strftime("%I:%M %p"),
        "count": len(_news_cache)
    })


# ── Launch ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = 5000
    print(f"\n{'='*62}")
    print(f"   J.A.R.V.I.S. -- POWERED VOICE AGENT + AI NEWS")
    print(f"{'='*62}")
    print(f"  Model  : {MODELS[0]} (with fallbacks)")
    print(f"  URL    : http://localhost:{port}")
    print(f"  Dispatch: Fast-path (local) + Gemini (smart)")
    print(f"  Tools  : web_search, wikipedia, open_url, open_google,")
    print(f"           open_youtube, weather, calculate, datetime,")
    print(f"           open_app (file explorer + 30+ apps), ai_news")
    print(f"{'='*62}\n")
    threading.Timer(1.5, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=False)
