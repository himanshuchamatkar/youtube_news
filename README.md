# Indian Stock Market Daily News Shorts Factory

A production-grade, zero-cost, fully automated YouTube Shorts generation factory focused **exclusively on the Indian stock market and financial updates**.

---

## 🚀 Features

- **Multi-Source News Ingestion**: Scrapes RSS feeds (Economic Times, Moneycontrol, Livemint) with fallbacks to GNews, NewsAPI, and Finnhub.
- **AI Filtering & Scoring**: Custom Python engine scores articles on Indian market relevance, impact, freshness, and credibility (rejecting international/forex/crypto news).
- **Gemini AI Verification**: Checks news authenticity, classifications, and generates 40-55s engaging scripts with titles, description tags, and disclaimers.
- **Synthesized Voice**: Narration generated dynamically using Google Cloud TTS (`en-IN-Wavenet-C`).
- **Dynamic Chart Generator**: Draws index performance charts, headline banners, and percentage movement badges using Pillow & Matplotlib.
- **FFmpeg Render Engine**: Stitches Pexels stock videos (with gradient fallbacks) and burns sync'd SRT subtitles.
- **Unattended YouTube Upload**: Utilizes OAuth refresh tokens to automatically upload Shorts with exact privacy and SEO keywords.
- **Idempotency Lock**: Hard database unique constraints guarantee that **exactly ONE Short** is successfully published per day.
- **Admin Dashboard**: React + Vite + Tailwind admin console to track live jobs, query news/video logs, edit settings, and trigger runs.

---

## 📂 Project Structure

```
D:\youtube_news
├── backend/
│   ├── app/
│   │   ├── core/           # Security, config, and Supabase client
│   │   ├── models/         # Pydantic schemas
│   │   ├── services/       # Gemini, TTS, Pexels, YouTube, Media orchestrator
│   │   ├── providers/      # NewsAPI, GNews, Finnhub, RSS scraper
│   │   ├── video/          # Chart/subtitle generators, FFmpeg wrapper
│   │   └── main.py         # FastAPI routes entrypoint
│   ├── tests/              # Automated unit tests
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx         # Dashboard layout, logs viewer, settings forms
│   │   ├── index.css       # Tailwind configuration and custom theme classes
│   │   └── main.tsx
│   ├── index.html
│   ├── tailwind.config.js
│   └── vercel.json         # Vercel SPA routing
├── database/
│   └── migrations/
│       └── 01_init.sql     # Database schema migrations script
├── media/                  # Folder structure for temporary files
│   ├── temp/
│   ├── audio/
│   ├── charts/
│   └── rendered/
├── scripts/
│   └── parse_credentials.py
├── .gitignore
├── credentials.txt         # Credentials file (ignored by Git)
├── .env                    # System variables (ignored by Git)
└── docker-compose.yml
```

---

## 🛠️ Installation & Setup

### 1. Parse Credentials & Initialize Git
Run the credentials script to parse `credentials.txt` and generate your local secret keys, `.env` file, and `.gitignore`:
```bash
python scripts/parse_credentials.py
```
*Note: Make sure to copy the printed admin password for logging into the dashboard!*

### 2. Database Migration (Supabase)
Copy the contents of [`database/migrations/01_init.sql`](file:///D:/youtube_news/database/migrations/01_init.sql) and execute it inside the **SQL Editor** of your Supabase project dashboard.

### 3. Run Backend (FastAPI)
Install the dependencies and start the local webserver:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --reload --port 8000
```

### 4. Run Frontend (React + Vite)
Build or launch the React client application:
```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` to access the dashboard.

---

## 🧪 Testing

Execute the automated test suite using `unittest` to verify news scoring, blacklist filters, deduplication, and quality control validation bounds:
```bash
python -m unittest backend/tests/test_pipeline.py
```
