import os
# pyrefly: ignore [missing-import]
import pyttsx3
# pyrefly: ignore [missing-import]
import speech_recognition as sr
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

API_KEY = os.getenv("GEMINI_API_KEY")

if not API_KEY or API_KEY == "your_gemini_api_key_here":
    raise SystemExit(
        "GEMINI_API_KEY is missing. Put your API key in the .env file. "
        "You can get a free one at https://aistudio.google.com/app/apikey"
    )

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

SYSTEM_PROMPT = """
You are JARVIS, a helpful personal AI voice assistant.
The user is speaking to you through a microphone.

Rules:
- Keep normal answers concise and natural for spoken conversation.
- Do not use markdown tables unless the user explicitly asks.
- Do not use emojis.
- Address the user as "sir" when appropriate.
- If a request requires a computer action that is not implemented yet,
  clearly say that the capability has not been connected yet.
"""

# Initialize TTS
engine = pyttsx3.init()
voices = engine.getProperty('voices')
# Optional: customize voice by un-commenting and changing index
# engine.setProperty('voice', voices[0].id) 

conversation_history = [
    {"role": "user", "parts": [SYSTEM_PROMPT]},
    {"role": "model", "parts": ["Understood, sir."]}
]

def speak(text):
    engine.say(text)
    engine.runAndWait()

import numpy as np
import sounddevice as sd
import soundfile as sf
import tempfile
from pathlib import Path

def transcribe():
    print("\nListening... speak now.")
    sample_rate = 16000
    block_seconds = 0.25
    silence_seconds = 1.2
    threshold = 0.015
    max_seconds = 20

    blocksize = int(sample_rate * block_seconds)
    chunks = []
    silent_for = 0.0
    started = False
    elapsed = 0.0

    with sd.InputStream(
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        blocksize=blocksize,
    ) as stream:
        while elapsed < max_seconds:
            data, _ = stream.read(blocksize)
            audio_data = np.asarray(data).copy()
            chunks.append(audio_data)

            volume = float(np.sqrt(np.mean(audio_data * audio_data)))

            if volume > threshold:
                started = True
                silent_for = 0.0
            elif started:
                silent_for += block_seconds
                if silent_for >= silence_seconds:
                    break

            elapsed += block_seconds

    if not chunks:
        return None

    audio = np.concatenate(chunks, axis=0)
    path = Path(tempfile.gettempdir()) / "jarvis_recording.wav"
    sf.write(path, audio, sample_rate)

    print("Transcribing...")
    r = sr.Recognizer()
    with sr.AudioFile(str(path)) as source:
        audio_clip = r.record(source)
    try:
        text = r.recognize_google(audio_clip)
        return text
    except sr.UnknownValueError:
        return None
    except sr.RequestError as e:
        print(f"Could not request results from Google Speech Recognition service; {e}")
        return None

def ask_jarvis(user_text):
    conversation_history.append({"role": "user", "parts": [user_text]})
    
    try:
        response = model.generate_content(conversation_history)
        answer = response.text.strip()
        conversation_history.append({"role": "model", "parts": [answer]})
        
        # Keep conversation history bounded
        if len(conversation_history) > 20:
            del conversation_history[2:4] # keep system prompt, delete oldest exchange
            
        return answer
    except Exception as e:
        print(f"Error calling Gemini: {e}")
        return "I'm sorry sir, I encountered an error communicating with my language model."

def main():
    print("=" * 58)
    print("                 JARVIS VOICE AGENT (FREE VERSION)")
    print("=" * 58)
    print("Speak after 'Listening...' appears.")
    print("Say 'exit', 'quit', or 'goodbye' to stop.")
    print("Press Ctrl+C at any time to stop.\n")

    speak("Online, sir. How can I help you?")

    while True:
        try:
            user_text = transcribe()

            if not user_text:
                continue

            print(f"You: {user_text}")

            if user_text.lower().strip() in {
                "exit", "quit", "goodbye", "shutdown jarvis", "stop jarvis"
            }:
                speak("Goodbye, sir.")
                break

            print("JARVIS is thinking...")
            answer = ask_jarvis(user_text)

            print(f"JARVIS: {answer}")
            speak(answer)

        except KeyboardInterrupt:
            print("\nStopping JARVIS...")
            break
        except Exception as exc:
            print(f"\nError: {exc}")
            try:
                speak("I encountered an error, sir.")
            except Exception:
                pass

if __name__ == "__main__":
    main()
