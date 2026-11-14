# 🕷️ AI Web Scraper

An intelligent web scraping application built with **Streamlit**, **Scrape.do**, and **Google Gemini (`google-genai`)**.

---

## 📁 File Structure

```text
ai-web-scraper/
├── .env                 # API keys (never commit this)
├── .env.example         # Example configuration template
├── .gitignore           # Ignores .env, venv/, __pycache__/
├── requirements.txt     # Python dependencies
├── main.py              # Streamlit UI (entry point)
├── scrape.py            # scrape.do fetching + HTML cleaning + chunking
└── parse.py             # Gemini parsing
```

---

## ⚙️ Prerequisites & Setup

### 1. Clone or Open the Repository
```bash
cd web_scraper
```

### 2. Create and Activate a Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# macOS / Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your keys:
```bash
cp .env.example .env
```

Edit `.env`:
```env
# Get your Gemini API key from https://aistudio.google.com/
GEMINI_API_KEY=your_gemini_api_key_here

# (Optional) Get your Scrape.do API token from https://scrape.do/
# If omitted, the scraper will use direct HTTP requests as a fallback
SCRAPE_DO_API_KEY=your_scrape_do_token_here
```

---

## 🚀 Running the App

Start the Streamlit application:
```bash
streamlit run main.py
```

Open your browser at `http://localhost:8501`.

---

## 🧩 How It Works

1. **Scraping (`scrape.py`)**:
   - Sends requests through **Scrape.do** proxy API (with anti-bot bypassing and optional JavaScript rendering) or falls back to direct browser-simulated requests.
   - Extracts the `<body>` tag via **BeautifulSoup**.
   - Strips non-content elements (`<script>`, `<style>`, navigation, etc.) and cleans up whitespace.
   - Splits the cleaned text into manageable chunks (`split_dom_content`) based on your configured chunk size.

2. **Parsing (`parse.py`)**:
   - Takes each content chunk and prompts **Google Gemini** using the official `google-genai` SDK.
   - Instructs the model to extract only the information requested by your prompt.
   - Filters out non-matching chunks and aggregates results into formatted Markdown.

3. **User Interface (`main.py`)**:
   - Streamlit interface for entering target URLs, adjusting chunk sizes, toggling JavaScript rendering, and selecting Gemini models.
   - Offers real-time progress indicators, DOM previews, and one-click download buttons for the extracted data.

