# 🎬 CineGen AI

<div align="center">

### AI-Powered Story-to-Video Generation Platform

Transform your ideas into cinematic videos using AI-powered story understanding, scene generation, image synthesis, narration, and video rendering.

</div>

---

## 📖 Overview

CineGen AI is a full-stack AI application that converts text stories into complete cinematic videos. It intelligently extracts scenes, generates AI images, creates natural narration, and combines everything into an MP4 video. The platform also provides secure authentication, personal history, and PostgreSQL-backed user management.

---

## ✨ Features

* 🔐 JWT Authentication
* 📖 AI Story Generation
* 🧠 Scene Extraction using Llama 3 (Ollama)
* 🎨 AI Image Generation using Pollinations AI
* 🎙️ AI Narration using Edge-TTS
* 🎬 Automatic MP4 Video Generation using MoviePy
* 📂 Personal Story, Image & Video History
* 📊 User Dashboard & Statistics
* 💾 PostgreSQL Database Integration
* 📥 Download Images & Videos
* 📱 Responsive User Interface

---

# 📸 Application Preview

## 🏠 Dashboard

![Dashboard](screenshots/dashboard.png?v=2)

---

## ✨ Story Generation

![Story Generation](screenshots/generation.png?v=2)

---

## 📂 Generation History

![History](screenshots/history.png?v=2)

---

## ⚙️ Settings

![Settings](screenshots/settings.png?v=2)

---

## ⚙️ Tech Stack

| Category            | Technologies                      |
| ------------------- | --------------------------------- |
| **Frontend**        | HTML5, CSS3, JavaScript           |
| **Backend**         | FastAPI, Python                   |
| **Database**        | PostgreSQL, SQLAlchemy            |
| **Authentication**  | JWT                               |
| **AI Models**       | Ollama (Llama 3), Pollinations AI |
| **Text-to-Speech**  | Edge-TTS                          |
| **Video Rendering** | MoviePy, FFmpeg                   |
| **Testing**         | Pytest                            |

---

## 🏗️ System Workflow

```text
User Story
     │
     ▼
Scene Extraction
     │
     ▼
Prompt Generation
     │
     ▼
AI Image Generation
     │
     ▼
Narration Generation
     │
     ▼
Video Composition
     │
     ▼
Download MP4
```

---

## 📁 Project Structure

```text
CineGen-AI/
│
├── app.py
├── models/
├── routes/
├── services/
├── utils/
├── tests/
├── screenshots/
├── outputs/
├── static/
├── requirements.txt
├── README.md
└── .env
```

---

# 🚀 Getting Started

### Clone the Repository

```bash
git clone https://github.com/Harini-sri-r/CineGen-AI.git
cd CineGen-AI
```

---

### Create Virtual Environment

```bash
python -m venv venv
```

Activate it

**Windows**

```bash
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

---

### Install Dependencies

```bash
pip install -r requirements.txt
```

---

### Configure Environment Variables

Create a `.env` file in the project root.

```env
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/cinegen_ai

JWT_SECRET_KEY=your_secret_key

POLLINATIONS_API_KEY=your_pollinations_api_key

OLLAMA_BASE_URL=http://127.0.0.1:11434

OLLAMA_MODEL=llama3
```

---

### Start Ollama

```bash
ollama serve
```

Download the model (only once):

```bash
ollama pull llama3
```

---

### Run the Backend

```bash
python -m uvicorn app:app --reload --port 8001
```

Backend:

```
http://127.0.0.1:8001
```

---

### Run the Frontend

Open **index.html** using Live Server or any local web server.

```
http://127.0.0.1:5500/index.html
```

---

## 🎥 How It Works

1. Enter a story.
2. AI extracts meaningful scenes.
3. Cinematic prompts are generated.
4. AI creates scene images.
5. Narration is generated.
6. Images and narration are combined into an MP4 video.
7. Download and manage your generated content.

---

## 📊 Current Features

* ✅ Secure User Authentication
* ✅ Dashboard
* ✅ Story Generation
* ✅ Scene Extraction
* ✅ Prompt Generation
* ✅ AI Image Generation
* ✅ Narration Generation
* ✅ Video Rendering
* ✅ History Management
* ✅ PostgreSQL Integration
* ✅ Download Images & Videos

---

## 🧪 Running Tests

Run all tests:

```bash
pytest
```

