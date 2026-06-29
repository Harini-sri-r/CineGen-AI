# 🎬 CineGen AI

> **AI-Powered Story-to-Video Generation Platform**

CineGen AI is a full-stack AI application that transforms text stories into cinematic videos by combining Large Language Models (LLMs), AI image generation, text-to-speech, and automated video composition. The platform provides a complete workflow—from story input to downloadable MP4 videos—with user authentication, history management, and PostgreSQL integration.

---

## ✨ Features

* 🔐 Secure User Authentication (JWT)
* 📖 AI Story Generation
* 🧠 Scene Extraction using **Llama 3 (Ollama)**
* 🎨 AI Image Generation using **Pollinations AI**
* 🎙️ AI Narration using **Edge-TTS**
* 🎬 Automatic MP4 Video Generation using **MoviePy**
* 📂 User-specific Generation History
* 📊 Interactive Dashboard & Statistics
* 💾 PostgreSQL Database Integration
* 📥 Download Generated Images & Videos
* ⚡ Responsive and Modern User Interface

---

## 📸 Screenshots

### 🏠 Dashboard

![Dashboard](screenshots/dashboard.png)

---

### ✨ Story Generation

![Story Generation](screenshots/generation.png)

---

### 📂 Generation History

![History](screenshots/history.png)

---

### ⚙️ Settings

![Settings](screenshots/settings.png)

---

## 🏗️ System Workflow

```text
User Story
     │
     ▼
Scene Extraction (Llama 3)
     │
     ▼
Prompt Generation
     │
     ▼
AI Image Generation
     │
     ▼
Text-to-Speech Narration
     │
     ▼
Video Composition
     │
     ▼
Download MP4 Video
```

---

## 🛠️ Tech Stack

| Category             | Technologies            |
| -------------------- | ----------------------- |
| **Frontend**         | HTML5, CSS3, JavaScript |
| **Backend**          | FastAPI, Python         |
| **Database**         | PostgreSQL, SQLAlchemy  |
| **Authentication**   | JWT                     |
| **LLM**              | Ollama (Llama 3)        |
| **Image Generation** | Pollinations AI         |
| **Text-to-Speech**   | Edge-TTS                |
| **Video Processing** | MoviePy, FFmpeg         |
| **Testing**          | Pytest                  |

---

## 📂 Project Structure

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
├── requirements.txt
├── README.md
└── .env
```

---

## 🚀 Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/Harini-sri-r/CineGen-AI.git
cd CineGen-AI
```

### 2. Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

**Windows**

```bash
venv\Scripts\activate
```

**Linux / macOS**

```bash
source venv/bin/activate
```

---

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Configure Environment Variables

Create a `.env` file in the project root.

```env
DATABASE_URL=postgresql+psycopg://postgres:your_password@localhost:5432/cinegen_ai

JWT_SECRET_KEY=your_secret_key

POLLINATIONS_API_KEY=your_api_key

OLLAMA_BASE_URL=http://127.0.0.1:11434

OLLAMA_MODEL=llama3
```

---

### 5. Start Ollama

```bash
ollama serve
```

Pull the model (only once):

```bash
ollama pull llama3
```

---

### 6. Run the Backend

```bash
python -m uvicorn app:app --reload --port 8001
```

Backend URL:

```
http://127.0.0.1:8001
```

---

### 7. Run the Frontend

Open `index.html` using VS Code Live Server or any local web server.

```
http://127.0.0.1:5500/index.html
```

---

## 🎥 How It Works

1. Enter a story.
2. Llama 3 extracts meaningful scenes.
3. AI generates cinematic prompts.
4. Pollinations AI creates scene images.
5. Edge-TTS narrates each scene.
6. MoviePy combines images, narration, and transitions.
7. Download the generated MP4 video.

---

## 📊 Current Features

* ✅ Story Generation
* ✅ Scene Extraction
* ✅ Prompt Generation
* ✅ AI Image Generation
* ✅ AI Narration
* ✅ MP4 Video Rendering
* ✅ User Authentication
* ✅ PostgreSQL Integration
* ✅ History Management
* ✅ Dashboard
* ✅ Download Images & Videos
* ✅ Responsive UI

---

## 🧪 Running Tests

```bash
pytest
```

---

## 👩‍💻 Author

**Harini Sri R**

B.Tech – Artificial Intelligence & Data Science

📌 Dr. N.G.P Institute of Technology

🔗 GitHub: https://github.com/Harini-sri-r

---

## ⭐ Support

If you found this project useful, consider giving it a **⭐ Star** on GitHub!
