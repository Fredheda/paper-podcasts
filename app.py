"""Streamlit UI for Paper-to-Podcast Pipeline."""

import streamlit as st
import os
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
from typing import List

from src.services.arxiv_service import ArxivService
from src.services.pdf_service import PdfService
from src.services.llm_service import LLMService
from src.services.llm_providers import AnthropicProvider
from src.services.audio_service import AudioService
from src.services.tts_providers import OpenAITTSProvider
from src.pipeline.paper_pipeline import PaperPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Page configuration - MUST be first Streamlit command
st.set_page_config(
    page_title="Paper Podcasts",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================================
# Constants
# ============================================================================

LIBRARY_CACHE_TTL = 60  # seconds
DEFAULT_MAX_RESULTS = 5
DEFAULT_EXACT_MATCH = True
EXTRACT_TEXT_PREVIEW_LIMIT = 5000  # characters
TITLE_TRUNCATE_SHORT = 50  # characters
TITLE_TRUNCATE_LONG = 60  # characters
MAX_AUTHORS_DISPLAY = 3


# ============================================================================
# Helper Functions
# ============================================================================

def format_authors(authors, max_display: int = MAX_AUTHORS_DISPLAY) -> str:
    """Format author list for display.

    Args:
        authors: List of author objects or dicts with 'name' key
        max_display: Maximum number of authors to display before truncating

    Returns:
        Formatted author string
    """
    if not authors:
        return ""

    # Handle both author objects and dicts
    author_names = []
    for author in authors[:max_display]:
        if hasattr(author, 'name'):
            author_names.append(author.name)
        elif isinstance(author, dict):
            author_names.append(author.get("name", "Unknown"))
        else:
            author_names.append(str(author))

    authors_str = ", ".join(author_names)
    if len(authors) > max_display:
        authors_str += f" + {len(authors) - max_display} more"

    return authors_str


# ============================================================================
# Session State Initialization
# ============================================================================

def init_session_state():
    """Initialize session state variables."""
    if "search_results" not in st.session_state:
        st.session_state.search_results = []

    if "selected_papers" not in st.session_state:
        st.session_state.selected_papers = set()

    if "library" not in st.session_state:
        st.session_state.library = []

    if "current_view" not in st.session_state:
        st.session_state.current_view = "search"

    if "processing_complete" not in st.session_state:
        st.session_state.processing_complete = False

    if "exact_match" not in st.session_state:
        st.session_state.exact_match = DEFAULT_EXACT_MATCH

    if "max_results" not in st.session_state:
        st.session_state.max_results = DEFAULT_MAX_RESULTS


# ============================================================================
# Service Initialization (Cached)
# ============================================================================

@st.cache_resource
def init_services():
    """Initialize all services (cached across reruns)."""
    load_dotenv()

    anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not anthropic_api_key or not openai_api_key:
        st.error("Missing API keys. Please set ANTHROPIC_API_KEY and OPENAI_API_KEY in your environment.")
        st.stop()

    arxiv_service = ArxivService()
    pdf_service = PdfService()
    llm_provider = AnthropicProvider(api_key=anthropic_api_key)
    llm_service = LLMService(provider=llm_provider, prompts_dir="prompts")
    tts_provider = OpenAITTSProvider(api_key=openai_api_key)
    audio_service = AudioService(provider=tts_provider)

    pipeline = PaperPipeline(
        arxiv_service=arxiv_service,
        pdf_service=pdf_service,
        llm_service=llm_service,
        audio_service=audio_service,
        storage_dir=Path("data"),
    )

    return {
        "arxiv": arxiv_service,
        "pipeline": pipeline,
    }


# ============================================================================
# Library Loading
# ============================================================================

@st.cache_data(ttl=LIBRARY_CACHE_TTL)
def load_library_from_disk() -> List[dict]:
    """Load processed papers from the data directory."""
    data_dir = Path("data/papers")

    if not data_dir.exists():
        return []

    library = []

    for paper_dir in data_dir.iterdir():
        if not paper_dir.is_dir():
            continue

        # Look for paper_state.json
        state_file = paper_dir / "paper_state.json"
        if not state_file.exists():
            continue

        try:
            # Load paper from disk
            with open(state_file, 'r') as f:
                paper_data = json.load(f)

            # Check if audio exists
            audio_dir = paper_dir / "audio"
            audio_files = list(audio_dir.glob("*.mp3")) if audio_dir.exists() else []

            # Check if summary exists
            summary_dir = paper_dir / "summaries"
            summary_files = list(summary_dir.glob("summary_*.txt")) if summary_dir.exists() else []

            # Check if extracted content exists
            extract_dir = paper_dir / "extracted"
            extract_files = list(extract_dir.glob("*.md")) if extract_dir.exists() else []

            library.append({
                "title": paper_data.get("title", "Unknown"),
                "arxiv_id": paper_data.get("arxiv_id", ""),
                "authors": paper_data.get("authors", []),
                "status": paper_data.get("status", "unknown"),
                "abstract": paper_data.get("abstract", ""),
                "audio_path": audio_files[0] if audio_files else None,
                "summary_path": summary_files[0] if summary_files else None,
                "extract_path": extract_files[0] if extract_files else None,
                "paper_dir": paper_dir,
            })
        except Exception as e:
            logger.error(f"Error loading paper from {paper_dir}: {e}")
            continue

    return library


# ============================================================================
# UI Components
# ============================================================================

def render_header():
    """Render the app header."""
    st.title("📚 Paper Podcasts")
    st.markdown("Transform research papers into podcasts")
    st.divider()


def render_search_interface(services):
    """Render the search interface."""
    st.subheader("🔍 Search arXiv")

    # Check if an example search was clicked
    default_query = ""
    auto_search = False
    if "example_search" in st.session_state:
        default_query = st.session_state.example_search
        auto_search = True
        del st.session_state.example_search  # Clear it after using

    # Use form to enable Enter key submission
    with st.form(key="search_form", clear_on_submit=False):
        col1, col2, col3 = st.columns([4, 1, 1])

        with col1:
            search_query = st.text_input(
                "Enter topic or paper name",
                value=default_query,
                placeholder="e.g., attention is all you need",
                label_visibility="collapsed"
            )

        with col2:
            search_button = st.form_submit_button("Search", type="primary", use_container_width=True)

        with col3:
            clear_button = st.form_submit_button("Clear", use_container_width=True)

    # Handle clear button
    if clear_button:
        st.session_state.search_results = []
        st.session_state.selected_papers = set()
        st.rerun()

    # Search options (outside form so they don't reset)
    with st.expander("Search Options"):
        col1, col2 = st.columns(2)
        with col1:
            exact_match = st.checkbox("Exact phrase match", value=st.session_state.exact_match, key="exact_match")
        with col2:
            max_results = st.slider("Max results", min_value=1, max_value=20, value=st.session_state.max_results, key="max_results")

    # Trigger search if button clicked OR auto_search is True
    if (search_button or auto_search) and search_query:
        with st.spinner("Searching arXiv..."):
            try:
                results = services["arxiv"].search_by_topic(
                    topic=search_query,
                    exact=exact_match,
                    max_results=max_results
                )
                st.session_state.search_results = results
                st.session_state.selected_papers = set()
                st.toast(f"✅ Found {len(results)} paper{'s' if len(results) != 1 else ''}", icon="🔍")
            except Exception as e:
                st.error(f"Search failed: {e}")
                logger.error(f"Search error: {e}", exc_info=True)


def render_search_results(services):
    """Render search results with selection checkboxes."""
    if not st.session_state.search_results:
        # Better empty state with centered content
        st.write("")  # Spacing
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # Large icon
            st.markdown("### 🔍")
            st.markdown("#### No Results Yet")
            st.caption("Start by searching for research papers on arXiv")

            st.divider()

            # Example searches - ML and GenAI focused
            st.markdown("**Popular ML & GenAI searches:**")
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🧠 Attention mechanism", use_container_width=True, key="ex1"):
                    st.session_state.example_search = "attention mechanism"
                    st.rerun()
                if st.button("🤖 Large language models", use_container_width=True, key="ex2"):
                    st.session_state.example_search = "large language models"
                    st.rerun()
            with col_b:
                if st.button("🎨 Diffusion models", use_container_width=True, key="ex3"):
                    st.session_state.example_search = "diffusion models"
                    st.rerun()
                if st.button("🔄 Reinforcement learning", use_container_width=True, key="ex4"):
                    st.session_state.example_search = "reinforcement learning"
                    st.rerun()

        return

    st.subheader(f"Search Results ({len(st.session_state.search_results)} papers)")

    for i, paper in enumerate(st.session_state.search_results):
        with st.container(border=True):
            col1, col2 = st.columns([0.1, 0.9])

            with col1:
                selected = st.checkbox(
                    "Select",
                    key=f"paper_{i}",
                    value=paper.arxiv_id in st.session_state.selected_papers,
                    label_visibility="collapsed"
                )

                if selected:
                    st.session_state.selected_papers.add(paper.arxiv_id)
                elif paper.arxiv_id in st.session_state.selected_papers:
                    st.session_state.selected_papers.remove(paper.arxiv_id)

            with col2:
                st.markdown(f"**{paper.title}**")

                # Authors
                authors_str = format_authors(paper.authors)

                st.caption(f"👤 {authors_str} • 📅 {paper.published.strftime('%Y-%m-%d')}")

                # Abstract preview
                with st.expander("View Abstract"):
                    st.write(paper.abstract)
                    st.caption(f"arXiv ID: {paper.arxiv_id}")

    # Process button
    st.divider()
    selected_count = len(st.session_state.selected_papers)

    if selected_count > 0:
        if st.button(f"🎙️ Process {selected_count} Selected Paper{'s' if selected_count > 1 else ''}", type="primary"):
            st.session_state.processing_complete = False
            process_selected_papers(services["pipeline"])
    else:
        st.button(f"🎙️ Process 0 Selected Papers", type="primary", disabled=True)


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def process_selected_papers(pipeline: PaperPipeline):
    """Process selected papers through the pipeline with real-time progress tracking."""
    selected_papers = [
        paper for paper in st.session_state.search_results
        if paper.arxiv_id in st.session_state.selected_papers
    ]

    if not selected_papers:
        st.warning("No papers selected")
        return

    for i, paper in enumerate(selected_papers):
        st.subheader(f"Processing {i+1}/{len(selected_papers)}: {paper.title}")

        with st.status(f"Processing {paper.title[:TITLE_TRUNCATE_SHORT]}...", expanded=True) as status:
            try:
                # Stage 1: Download
                st.write("📥 Downloading PDF...")
                download_result = pipeline.process_paper(paper, stages=["download"])

                if download_result.download:
                    pdf_size = download_result.download.pdf_path.stat().st_size
                    st.write(f"✅ Downloaded PDF ({format_file_size(pdf_size)})")
                else:
                    st.write("⚠️ Download failed or already exists")
                    if download_result.errors:
                        st.error(f"Download error: {download_result.errors[0]}")
                        status.update(label=f"❌ Failed at download: {paper.title[:TITLE_TRUNCATE_SHORT]}", state="error")
                        continue

                # Stage 2: Extract
                st.write("📄 Extracting text from PDF...")
                extract_result = pipeline.process_paper(paper, stages=["extract"])

                if extract_result.extraction:
                    char_count = extract_result.extraction.character_count
                    st.write(f"✅ Extracted {char_count:,} characters")
                else:
                    st.write("⚠️ Extraction failed")
                    if extract_result.errors:
                        st.error(f"Extraction error: {extract_result.errors[0]}")
                        status.update(label=f"❌ Failed at extraction: {paper.title[:TITLE_TRUNCATE_SHORT]}", state="error")
                        continue

                # Stage 3: Summarize
                st.write("🤖 Generating summary with AI...")
                summary_result = pipeline.process_paper(paper, stages=["summarize"])

                if summary_result.summary:
                    summary_length = len(summary_result.summary.summary_text)
                    word_count = len(summary_result.summary.summary_text.split())
                    st.write(f"✅ Generated summary ({word_count:,} words, {summary_length:,} characters)")
                else:
                    st.write("⚠️ Summarization failed")
                    if summary_result.errors:
                        st.error(f"Summary error: {summary_result.errors[0]}")
                        status.update(label=f"❌ Failed at summarization: {paper.title[:TITLE_TRUNCATE_SHORT]}", state="error")
                        continue

                # Stage 4: Audio Generation
                st.write("🎙️ Generating podcast audio...")
                audio_result = pipeline.process_paper(paper, stages=["audio"])

                if audio_result.audio:
                    audio_size = audio_result.audio.audio_path.stat().st_size
                    duration_info = ""
                    if audio_result.audio.audio_duration_seconds:
                        mins = int(audio_result.audio.audio_duration_seconds // 60)
                        secs = int(audio_result.audio.audio_duration_seconds % 60)
                        duration_info = f", {mins}:{secs:02d}"
                    st.write(f"✅ Generated audio ({format_file_size(audio_size)}{duration_info})")
                else:
                    st.write("⚠️ Audio generation failed")
                    if audio_result.errors:
                        st.error(f"Audio error: {audio_result.errors[0]}")
                        status.update(label=f"❌ Failed at audio generation: {paper.title[:TITLE_TRUNCATE_SHORT]}", state="error")
                        continue

                # All stages complete!
                if audio_result.is_successful:
                    status.update(label=f"✅ Complete: {paper.title[:TITLE_TRUNCATE_SHORT]}", state="complete")
                    st.toast(f"🎉 Successfully processed: {paper.title[:TITLE_TRUNCATE_LONG]}", icon="✅")
                else:
                    status.update(label=f"⚠️ Partially complete: {paper.title[:TITLE_TRUNCATE_SHORT]}", state="running")
                    st.toast(f"⚠️ Partially completed: {paper.title[:TITLE_TRUNCATE_LONG]}", icon="⚠️")

            except Exception as e:
                status.update(label=f"❌ Error: {paper.title[:TITLE_TRUNCATE_SHORT]}", state="error")
                st.error(f"Error processing {paper.title}: {e}")
                logger.error(f"Processing error: {e}", exc_info=True)

    # Mark processing complete and refresh library
    st.session_state.processing_complete = True
    st.session_state.selected_papers = set()
    load_library_from_disk.clear()  # Clear cache to reload library
    st.rerun()


def render_library():
    """Render the podcast library."""
    st.subheader("📚 Your Podcast Library")

    all_library = load_library_from_disk()

    if not all_library:
        # Better empty state for library
        st.write("")  # Spacing
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            # Large icon
            st.markdown("### 🎙️")
            st.markdown("#### Your Library is Empty")
            st.caption("Process some papers to start building your podcast library")

            st.write("")  # Spacing

            st.markdown("""
            **To get started:**
            1. Go to the Search tab
            2. Find a paper you're interested in
            3. Select and process it
            4. Come back here to listen!
            """)

        return

    # Filter by status
    col1, col2 = st.columns([3, 1])
    with col2:
        filter_status = st.selectbox(
            "Filter by status",
            options=["all", "completed", "in progress"],
            label_visibility="collapsed"
        )

    # Apply filter using list comprehension
    if filter_status == "completed":
        library = [p for p in all_library if p["status"] == "completed"]
    elif filter_status == "in progress":
        library = [p for p in all_library if p["status"] != "completed"]
    else:
        library = all_library

    with col1:
        st.write(f"**{len(library)} paper{'s' if len(library) != 1 else ''} in library**")

    for paper_info in library:

        # Status emoji for expander label
        status_emoji = "✅" if paper_info["status"] == "completed" else "⏳"

        # Create expander with title and status
        with st.expander(f"{status_emoji} {paper_info['title']}", expanded=False):
            # Authors
            if paper_info["authors"]:
                authors_str = format_authors(paper_info["authors"])
                st.caption(f"👤 {authors_str}")

            st.caption(f"📋 Status: {paper_info['status']}")

            # Link to arXiv paper
            if paper_info["arxiv_id"]:
                arxiv_url = f"https://arxiv.org/abs/{paper_info['arxiv_id']}"
                st.link_button("📄 View Paper on arXiv", arxiv_url, use_container_width=False)

            st.divider()

            # Audio player
            if paper_info["audio_path"]:
                st.audio(str(paper_info["audio_path"]), format="audio/mpeg")

                # Download buttons row
                col1, col2 = st.columns(2)
                with col1:
                    # Download MP3 button
                    with open(paper_info["audio_path"], "rb") as audio_file:
                        st.download_button(
                            label="⬇️ Download MP3",
                            data=audio_file,
                            file_name=f"{paper_info['title'][:TITLE_TRUNCATE_SHORT]}.mp3",
                            mime="audio/mpeg",
                            key=f"download_{paper_info['arxiv_id']}",
                            use_container_width=True
                        )
                with col2:
                    # Download PDF button if it exists
                    pdf_files = list(paper_info["paper_dir"].glob("*.pdf"))
                    if pdf_files:
                        with open(pdf_files[0], "rb") as pdf_file:
                            st.download_button(
                                label="📥 Download PDF",
                                data=pdf_file,
                                file_name=f"{paper_info['title'][:TITLE_TRUNCATE_SHORT]}.pdf",
                                mime="application/pdf",
                                key=f"download_pdf_{paper_info['arxiv_id']}",
                                use_container_width=True
                            )
            else:
                st.info("🎙️ Audio not yet generated")

            # Content tabs - simplified logic
            tab_content = []
            if paper_info["abstract"]:
                tab_content.append(("Abstract", paper_info["abstract"], "text"))
            if paper_info["summary_path"]:
                tab_content.append(("Summary", paper_info["summary_path"], "file"))
            if paper_info["extract_path"]:
                tab_content.append(("Full Text", paper_info["extract_path"], "extract"))

            if tab_content:
                tab_names = [name for name, _, _ in tab_content]
                tabs = st.tabs(tab_names)

                for tab, (_, content, content_type) in zip(tabs, tab_content):
                    with tab:
                        try:
                            if content_type == "text":
                                st.write(content)
                            elif content_type == "file":
                                summary_text = Path(content).read_text()
                                st.write(summary_text)
                            elif content_type == "extract":
                                extract_text = Path(content).read_text()
                                if len(extract_text) > EXTRACT_TEXT_PREVIEW_LIMIT:
                                    st.markdown(extract_text[:EXTRACT_TEXT_PREVIEW_LIMIT] + "...")
                                    st.caption(f"(Showing first {EXTRACT_TEXT_PREVIEW_LIMIT:,} characters)")
                                else:
                                    st.markdown(extract_text)
                        except Exception as e:
                            st.error(f"Could not load content: {e}")
                            logger.error(f"Error loading content: {e}", exc_info=True)


# ============================================================================
# Sidebar
# ============================================================================

def render_sidebar():
    """Render the sidebar with navigation and info."""
    with st.sidebar:
        st.title("📚 Paper Podcasts")

        st.divider()

        # Stylish segmented control for navigation
        view = st.segmented_control(
            "Navigation",
            options=["search", "library"],
            format_func=lambda x: "🔍 Search" if x == "search" else "📚 Library",
            selection_mode="single",
            default="search",
            label_visibility="collapsed"
        )

        if view:  # Only update if a value is returned
            st.session_state.current_view = view

        st.divider()

        st.subheader("About")
        st.markdown("""
        Transform research papers into audio summaries.

        **How it works:**
        1. 🔍 Search arXiv for papers
        2. ✅ Select papers to process
        3. 🎙️ Listen to AI-generated podcasts
        """)


# ============================================================================
# Main App
# ============================================================================

def main():
    """Main application entry point."""
    init_session_state()
    services = init_services()

    render_header()
    render_sidebar()

    # Main content based on current view
    if st.session_state.current_view == "search":
        render_search_interface(services)
        st.divider()
        render_search_results(services)
    else:  # library view
        render_library()

    # Show toast notification after processing
    if st.session_state.processing_complete:
        st.toast("🎉 Processing complete! Check your library to listen.", icon="🎙️")
        st.session_state.processing_complete = False


if __name__ == "__main__":
    main()
