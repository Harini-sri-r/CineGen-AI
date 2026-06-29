# 🎬 CineGen AI

An AI-powered web application that transforms text stories into cinematic videos using Large Language Models, AI image generation, text-to-speech, and automated video composition.

## ✨ Features

* 🔐 User Authentication (JWT)
* 📖 AI Story Generation
* 🧠 Scene Extraction using Llama 3 (Ollama)
* 🎨 AI Image Generation using Pollinations AI
* 🎙️ AI Narration using Edge-TTS
* 🎬 Automatic MP4 Video Generation using MoviePy
* 📂 Personal Generation History
* 📊 User Dashboard & Statistics
* 💾 PostgreSQL Database Integration
* 📥 Download Images and Videos

---

## 📸 Screenshots

### Dashboard
![Dashboard](screenshots/dashboard.png)

### Story Generation
![Story Generation](screenshots/generation.png)

### History
![History](screenshots/history.png)

### Settings
![Settings](screenshots/settings.png)

---

## 🛠️ Tech Stack

| Category       | Technologies                      |
| -------------- | --------------------------------- |
| Backend        | FastAPI, Python                   |
| Frontend       | HTML, CSS, JavaScript             |
| Database       | PostgreSQL                        |
| AI             | Ollama (Llama 3), Pollinations AI |
| Text-to-Speech | Edge-TTS                          |
| Video          | MoviePy, FFmpeg                   |
| Testing        | Pytest                            |

---

## 🚀 Getting Started

### Clone the repository

```bash
git clone https://github.com/Harini-sri-r/CineGen-AI.git
cd CineGen-AI
```

### Install dependencies

```bash
pip install -r requirements.txt
```

### Configure environment variables

Create a `.env` file:

```env
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/cinegen_ai

JWT_SECRET_KEY=your_secret_key

POLLINATIONS_API_KEY=your_api_key

OLLAMA_MODEL=llama3
```

### Run the application

```bash
python -m uvicorn app:app --reload --port 8001
```

Open the frontend:

```text
http://127.0.0.1:5500/index.html
```

