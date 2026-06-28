# 🎬 CineGen AI: Multimodal Story-to-Video Generation Using LLMs and AI

<div align="center">

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green?logo=fastapi)
![JavaScript](https://img.shields.io/badge/JavaScript-ES6-yellow?logo=javascript)
![License](https://img.shields.io/badge/License-MIT-orange)
![Status](https://img.shields.io/badge/Status-Completed-success)

**Transform plain text stories into cinematic AI-generated videos with narration, scene images, and intelligent storytelling.**

</div>

---

# 📖 Overview

CineGen AI is an AI-powered multimedia generation platform that converts a simple story into a narrated cinematic video.

The application uses a Large Language Model (Llama 3) to understand the story, divide it into meaningful scenes, generate detailed prompts, create AI images, synthesize narration, and finally compose everything into a professional MP4 video.

Unlike traditional text-to-image generators, CineGen AI produces a complete storytelling experience including:

* 🧠 AI Scene Understanding
* 🎨 AI Image Generation
* 🎙️ AI Voice Narration
* 🎬 Automatic Video Generation
* 📂 Generation History
* 📥 Downloadable Videos

---

# 🚀 Features

## ✨ AI Story Processing

* Story Validation
* Scene Extraction using Llama 3
* Intelligent Prompt Generation
* Multi-scene Story Understanding

---

## 🖼️ AI Image Generation

* Pollinations AI Integration
* High-quality Scene Images
* Automatic Placeholder Recovery
* Image Download Support

---

## 🎙️ AI Voice Narration

* Edge-TTS
* Natural Human-like Voice
* Scene-wise Audio Generation

---

## 🎬 Video Generation

* MoviePy
* MP4 Rendering
* Automatic Scene Timing
* Fade Transitions
* Ken Burns Zoom Effect
* Intro Title
* End Credits
* Optional Background Music

---

## 🌐 Modern Web Interface

* Responsive UI
* Progress Tracking
* Story Dashboard
* Scene Cards
* Prompt Viewer
* Image Gallery
* Embedded Video Player
* Download Video
* Open Video in New Tab

---

## 📚 History System

* Previous Stories
* Previous Images
* Previous Videos
* Statistics Dashboard
* Replay Generated Videos

---

# 🏗️ System Architecture

```text
                 User Story
                      │
                      ▼
              FastAPI Backend
                      │
      ┌───────────────┼───────────────┐
      │               │               │
      ▼               ▼               ▼
 Scene Extraction  Prompt Generator  Story Validation
      │
      ▼
  Ollama Llama 3
      │
      ▼
 Pollinations AI
      │
      ▼
 Scene Images
      │
      ▼
 Edge-TTS Narration
      │
      ▼
 MoviePy Video Composer
      │
      ▼
 MP4 Video Generation
      │
      ▼
 Frontend Video Player
```

---

# 🛠️ Technology Stack

### Backend

* Python 3.11
* FastAPI
* Uvicorn
* Pydantic

### AI & ML

* Ollama Llama 3
* Pollinations AI
* Edge-TTS

### Video Processing

* MoviePy
* FFmpeg

### Frontend

* HTML5
* CSS3
* JavaScript
