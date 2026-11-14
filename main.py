import os
import streamlit as st
from dotenv import load_dotenv

from scrape import (
    clean_body_content,
    extract_body_content,
    scrape_website,
    split_dom_content,
)
from parse import parse_with_gemini

# Load environment variables
load_dotenv()

# App configuration
st.set_page_config(
    page_title="AI Web Scraper",
    page_icon="🕷️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .stButton>button {
        border-radius: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# Initialize Session State
if "raw_html" not in st.session_state:
    st.session_state["raw_html"] = ""
if "dom_content" not in st.session_state:
    st.session_state["dom_content"] = ""
if "chunks" not in st.session_state:
    st.session_state["chunks"] = []
if "scraped_url" not in st.session_state:
    st.session_state["scraped_url"] = ""
if "parsed_result" not in st.session_state:
    st.session_state["parsed_result"] = ""
if "extraction_prompt" not in st.session_state:
    st.session_state["extraction_prompt"] = ""


def set_prompt_preset(text: str):
    """Callback to safely set prompt text without resetting on rerun."""
    st.session_state["extraction_prompt"] = text


# --- SIDEBAR CONFIGURATION ---
with st.sidebar:
    st.title("⚙️ Configuration")

    st.markdown("### 🔑 API Keys")
    env_gemini_key = os.getenv("GEMINI_API_KEY", "")
    gemini_key_input = st.text_input(
        "Gemini API Key",
        value=env_gemini_key if env_gemini_key != "your_gemini_api_key_here" else "",
        type="password",
        placeholder="AIzaSy...",
        help="Required for AI parsing. Get a free key at https://aistudio.google.com/",
    )

    env_scrape_key = os.getenv("SCRAPE_DO_API_KEY", "")
    scrape_key_input = st.text_input(
        "Scrape.do Token (Optional)",
        value=env_scrape_key if env_scrape_key != "your_scrape_do_token_here" else "",
        type="password",
        placeholder="Enter Scrape.do token...",
        help="Proxy & anti-bot service. If left blank, falls back to direct HTTP requests.",
    )

    st.markdown("---")
    st.markdown("### 🤖 Extraction Model")
    model_choice = st.selectbox(
        "Gemini Model",
        options=[
            "gemini-2.5-flash",
            "gemini-3.8-flash",
            "gemini-3.5-flash-lite",
        ],
        index=0,
        help="Select the Gemini model for content analysis.",
    )

    chunk_size = st.slider(
        "Chunk Size (characters)",
        min_value=2000,
        max_value=12000,
        value=6000,
        step=1000,
        help="Maximum characters per chunk passed to Gemini.",
    )

    preserve_links = st.checkbox(
        "Preserve Hyperlinks & Images",
        value=True,
        help="Keep URLs and image references inline within the cleaned content.",
    )

    render_js = st.checkbox(
        "Render JavaScript (Scrape.do only)",
        value=False,
        help="Executes client-side JS using Scrape.do headless browser for SPAs.",
    )

    st.markdown("---")
    st.markdown(
        """
        **Get API Keys:**
        - [Google AI Studio (Gemini)](https://aistudio.google.com/)
        - [Scrape.do Portal](https://scrape.do/)
        """
    )

# --- MAIN APP LAYOUT ---
st.markdown('<div class="main-header">🕷️ AI Web Scraper</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-header">Scrape web content and extract structured data using Google Gemini.</div>',
    unsafe_allow_html=True,
)

# Step 1: Web Scraping
st.subheader("Step 1: Scrape Website Content")
col_url, col_btn = st.columns([4, 1])

with col_url:
    target_url = st.text_input(
        "Target URL",
        placeholder="https://example.com or https://news.ycombinator.com",
        label_visibility="collapsed",
    )

with col_btn:
    scrape_clicked = st.button("🚀 Scrape Website", use_container_width=True, type="primary")

if scrape_clicked:
    if not target_url.strip():
        st.warning("⚠️ Please enter a valid URL.")
    else:
        with st.spinner("Fetching and processing website content..."):
            try:
                raw_html = scrape_website(
                    url=target_url,
                    api_key=scrape_key_input,
                    render_js=render_js,
                )
                body_content = extract_body_content(raw_html)
                cleaned_content = clean_body_content(body_content, preserve_links=preserve_links)
                chunks = split_dom_content(cleaned_content, max_length=chunk_size, overlap=300)

                # Store in session state
                st.session_state["raw_html"] = raw_html
                st.session_state["dom_content"] = cleaned_content
                st.session_state["chunks"] = chunks
                st.session_state["scraped_url"] = target_url
                st.session_state["parsed_result"] = ""  # reset previous extraction

                st.success(f"✅ Successfully scraped: **{target_url}**")
            except Exception as e:
                st.error(f"❌ Scraping failed: {e}")

# Display Scraped Content Details
if st.session_state["dom_content"]:
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Cleaned Characters", f"{len(st.session_state['dom_content']):,}")
    with col2:
        st.metric("Total Word Count", f"{len(st.session_state['dom_content'].split()):,}")
    with col3:
        st.metric("Generated Chunks", len(st.session_state["chunks"]))

    with st.expander("👀 View Cleaned DOM Content", expanded=False):
        st.text_area(
            "Cleaned Content",
            st.session_state["dom_content"],
            height=260,
            disabled=True,
        )

    with st.expander("📄 View Raw HTML Source", expanded=False):
        st.text_area(
            "Raw HTML",
            st.session_state["raw_html"],
            height=260,
            disabled=True,
        )

    st.markdown("---")

    # Step 2: Gemini AI Parsing
    st.subheader("Step 2: Parse Content with Gemini")
    st.write("Specify what information you want to extract from the scraped webpage:")

    # Quick prompt presets with on_click callbacks
    preset_cols = st.columns(4)
    with preset_cols[0]:
        st.button(
            "📊 Extract Data Table",
            use_container_width=True,
            on_click=set_prompt_preset,
            args=("Extract all key tabular data, items, names, and metrics formatted as a clean Markdown table.",),
        )
    with preset_cols[1]:
        st.button(
            "🏷️ Products & Prices",
            use_container_width=True,
            on_click=set_prompt_preset,
            args=("Extract all product titles, prices, ratings, and URLs into a Markdown table.",),
        )
    with preset_cols[2]:
        st.button(
            "📰 Summarize Key Points",
            use_container_width=True,
            on_click=set_prompt_preset,
            args=("Summarize the main topic, key takeaways, and important data points from this page in bullet points.",),
        )
    with preset_cols[3]:
        st.button(
            "🔗 Links & Contacts",
            use_container_width=True,
            on_click=set_prompt_preset,
            args=("Extract all email addresses, phone numbers, contact info, and external URLs found on the page.",),
        )

    parse_description = st.text_area(
        "Extraction Prompt",
        key="extraction_prompt",
        placeholder="e.g. Extract all product names, prices, and links as a Markdown table.",
        height=100,
    )

    parse_btn = st.button("🧠 Parse with Gemini", type="primary")

    if parse_btn:
        active_gemini_key = gemini_key_input.strip() or os.getenv("GEMINI_API_KEY", "").strip()
        if not active_gemini_key or active_gemini_key == "your_gemini_api_key_here":
            st.error("⚠️ Gemini API Key is required. Please enter it in the sidebar or set it in `.env`.")
        elif not parse_description.strip():
            st.warning("⚠️ Please provide instructions for what to extract.")
        else:
            progress_bar = st.progress(0, text="Initializing Gemini extraction...")
            status_text = st.empty()

            def update_progress(current: int, total: int):
                pct = int((current / total) * 100)
                progress_bar.progress(pct, text=f"Processing chunk {current} of {total} with {model_choice}...")

            try:
                parsed_output = parse_with_gemini(
                    dom_chunks=st.session_state["chunks"],
                    parse_description=parse_description,
                    api_key=active_gemini_key,
                    model_name=model_choice,
                    progress_callback=update_progress,
                    pacing_delay=1.0,
                )
                st.session_state["parsed_result"] = parsed_output
                progress_bar.progress(100, text="Extraction complete!")
                status_text.success("🎉 Parsing completed successfully!")
            except Exception as e:
                progress_bar.empty()
                st.error(f"❌ Error during Gemini parsing: {e}")

# Display Extraction Results
if st.session_state.get("parsed_result"):
    st.markdown("### 📋 Extraction Results")
    st.markdown(st.session_state["parsed_result"])

    st.download_button(
        label="📥 Download Result (.md)",
        data=st.session_state["parsed_result"],
        file_name="extracted_data.md",
        mime="text/markdown",
    )
