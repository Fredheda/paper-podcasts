# Paper Podcasts - Design Document

## Project Overview

Paper Podcasts is an application that automatically creates audio summaries of research papers from arXiv. The system retrieves academic papers, extracts and analyzes their content using LLMs, and generates professional audio summaries for easy consumption.

## Goals and Requirements

### Core Functionality
1. **Paper Retrieval**: Fetch research papers from arXiv API based on various search criteria
2. **Content Extraction**: Extract text (and potentially images) from PDF papers
3. **Analysis & Summarization**: Use LLM APIs to analyze and create meaningful summaries
4. **Audio Generation**: Convert summaries to high-quality audio using text-to-speech
5. **Storage Management**: Organize PDFs and audio files in a structured manner

### Search Capabilities
1. **Recent Papers**: Find the most recent papers on a specific topic
2. **Popular Papers**: Retrieve the most popular papers of the week (popularity metric TBD)
3. **Specific Papers**: Search for and retrieve papers by exact title

## Architecture Overview

### High-Level Architecture

```
┌─────────────────┐
│  User Interface │
│   (CLI/API)     │
└────────┬────────┘
         │
┌────────▼────────────────────────────────────────┐
│           Application Layer                     │
│  ┌──────────────┐  ┌──────────────┐            │
│  │ Search       │  │ Pipeline     │            │
│  │ Controller   │  │ Orchestrator │            │
│  └──────────────┘  └──────────────┘            │
└─────────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────┐
│           Service Layer                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │  arXiv   │  │   LLM    │  │   TTS    │     │
│  │ Service  │  │ Service  │  │ Service  │     │
│  └──────────┘  └──────────┘  └──────────┘     │
│                                                  │
│  ┌──────────┐  ┌──────────┐                    │
│  │   PDF    │  │  Storage │                    │
│  │ Service  │  │ Service  │                    │
│  └──────────┘  └──────────┘                    │
└─────────────────────────────────────────────────┘
         │
┌────────▼────────────────────────────────────────┐
│           Data Layer                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐     │
│  │   PDFs   │  │  Audio   │  │ Metadata │     │
│  │  Folder  │  │  Folder  │  │   DB     │     │
│  └──────────┘  └──────────┘  └──────────┘     │
└─────────────────────────────────────────────────┘
```

## System Components

### 1. arXiv Service
**Responsibilities:**
- Interface with arXiv API
- Execute search queries (by topic, date, title)
- Download PDF files
- Parse arXiv metadata

**Key Methods:**
- `search_recent(topic, max_results)`: Search for recent papers on a topic
- `search_popular(time_window)`: Retrieve popular papers (based on citation count, download count, or social media mentions)
- `search_by_title(title)`: Find specific papers by title
- `download_pdf(arxiv_id, destination)`: Download paper PDF

**Data Returned:**
- arXiv ID
- Title
- Authors
- Abstract
- Publication date
- PDF URL
- Categories/tags

### 2. PDF Service
**Responsibilities:**
- Extract text from PDFs
- Extract images/figures (optional)
- Handle various PDF formats and encodings
- Clean and structure extracted content

**Technology Options:**
- **PyPDF2**: Basic PDF text extraction
- **pdfplumber**: Better text extraction with layout information
- **PyMuPDF (fitz)**: Fast extraction with image support
- **pdf2image + OCR (Tesseract)**: For scanned PDFs
- **Marker**: AI-powered PDF to markdown conversion

**Key Methods:**
- `extract_text(pdf_path)`: Extract text content
- `extract_images(pdf_path)`: Extract figures and diagrams
- `extract_structured(pdf_path)`: Extract with section headers, tables, etc.

**Output Format:**
```python
{
    "text": "full paper text",
    "sections": {
        "abstract": "...",
        "introduction": "...",
        "methods": "...",
        "results": "...",
        "conclusion": "..."
    },
    "images": ["path/to/fig1.png", ...]
}
```

### 3. LLM Service
**Responsibilities:**
- Analyze research papers
- Generate structured summaries
- Create audio-ready scripts
- Handle context limits with chunking strategies

**Provider Options:**
- **Anthropic Claude** (via direct API or Azure)
- **OpenAI GPT** (via Azure)

**Key Methods:**
- `analyze_paper(text, metadata)`: Deep analysis of paper
- `generate_summary(analysis, style)`: Create summary in specified style
- `create_audio_script(summary)`: Format summary for audio narration

**Summary Structure:**
```python
{
    "title": "Paper title",
    "quick_overview": "2-3 sentence summary",
    "key_findings": ["finding 1", "finding 2", ...],
    "methodology": "Description of methods used",
    "significance": "Why this research matters",
    "limitations": "Study limitations",
    "audio_script": "Full narration-ready text with proper pacing"
}
```

**Prompt Strategy:**
- System prompt defining role as research paper summarizer
- Few-shot examples of good summaries
- Structured output format (JSON)
- Instructions for audio-friendly language (no complex symbols, spelled-out equations)

### 4. Text-to-Speech Service
**Responsibilities:**
- Convert summary text to natural-sounding audio
- Support different voices and languages
- Handle pronunciation of technical terms
- Manage audio quality and format

**Provider Options:**
- **OpenAI TTS**: High quality, multiple voices
- **Azure Speech Services**: Enterprise-grade, SSML support
- **ElevenLabs**: Very natural voices, good for longer content
- **Google Cloud TTS**: Good language support
- **Amazon Polly**: Cost-effective, neural voices

**Key Methods:**
- `text_to_speech(text, voice, output_path)`: Generate audio file
- `add_pronunciation_hints(text, terms)`: Handle technical terms
- `split_long_text(text)`: Handle text longer than API limits

**Output Format:**
- Audio format: MP3 or WAV
- Sample rate: 24kHz or higher
- Bitrate: 128kbps or higher

### 5. Storage Service
**Responsibilities:**
- Manage file system organization
- Track processed papers
- Prevent duplicate processing
- Provide file retrieval

**Directory Structure:**
```
data/
├── papers/
│   ├── {arxiv_id}/
│   │   ├── paper.pdf
│   │   ├── extracted_text.txt
│   │   ├── metadata.json
│   │   └── images/
│   │       ├── fig1.png
│   │       └── fig2.png
│   └── ...
├── summaries/
│   ├── {arxiv_id}/
│   │   ├── summary.json
│   │   └── summary.md
│   └── ...
└── audio/
    ├── {arxiv_id}/
    │   ├── full_summary.mp3
    │   └── quick_summary.mp3
    └── ...
```

**Key Methods:**
- `save_paper(arxiv_id, pdf_data, metadata)`: Store paper and metadata
- `save_summary(arxiv_id, summary)`: Store generated summary
- `save_audio(arxiv_id, audio_data)`: Store audio file
- `get_paper(arxiv_id)`: Retrieve paper data
- `paper_exists(arxiv_id)`: Check if already processed
- `list_papers(filters)`: Query processed papers

**Metadata Database:**
- SQLite for simplicity (can upgrade to PostgreSQL later)
- Track processing status, timestamps, search metadata

```sql
CREATE TABLE papers (
    arxiv_id TEXT PRIMARY KEY,
    title TEXT,
    authors TEXT,
    abstract TEXT,
    published_date DATE,
    pdf_path TEXT,
    search_query TEXT,
    downloaded_at TIMESTAMP,
    processed_at TIMESTAMP,
    status TEXT  -- 'downloaded', 'extracted', 'summarized', 'audio_generated'
);

CREATE TABLE summaries (
    arxiv_id TEXT PRIMARY KEY,
    summary_json TEXT,
    audio_path TEXT,
    created_at TIMESTAMP,
    FOREIGN KEY (arxiv_id) REFERENCES papers(arxiv_id)
);
```

### 6. Pipeline Orchestrator
**Responsibilities:**
- Coordinate end-to-end processing
- Handle errors and retries
- Manage rate limits
- Report progress

**Processing Pipeline:**
```
1. Search arXiv → Get paper list
2. For each paper:
   a. Download PDF
   b. Extract text/images
   c. Analyze with LLM
   d. Generate summary
   e. Create audio
   f. Store all artifacts
   g. Update metadata
```

**Key Methods:**
- `process_search_query(query, max_papers)`: Full pipeline from search to audio
- `process_single_paper(arxiv_id)`: Process one specific paper
- `process_batch(arxiv_ids)`: Process multiple papers with rate limiting
- `resume_failed()`: Retry failed processing jobs

## Data Flow

### Search & Process Flow
```
User Query
    ↓
Search Controller
    ↓
arXiv Service (API Call)
    ↓
Paper Metadata List
    ↓
For each paper:
    Download PDF → Storage
    ↓
    Extract Text → PDF Service
    ↓
    Analyze & Summarize → LLM Service
    ↓
    Generate Audio → TTS Service
    ↓
    Save Audio → Storage
    ↓
    Update Database
```

### Retrieval Flow
```
User Request (arxiv_id or query)
    ↓
Storage Service
    ↓
Check Database
    ↓
If exists:
    Return paths to PDF, summary, audio
Else:
    Trigger processing pipeline
```

## Technology Stack

### Core Languages & Frameworks
- **Python 3.10+**: Main development language
- **FastAPI** (optional): REST API for web interface
- **Click**: CLI interface

### Libraries & Dependencies

**arXiv Integration:**
- `arxiv`: Official arXiv API Python wrapper

**PDF Processing:**
- `PyPDF2` or `pdfplumber`: Text extraction
- `PyMuPDF (fitz)`: Advanced extraction with images
- `pdf2image`: Convert PDF to images (if needed)
- `pytesseract`: OCR for scanned PDFs (optional)

**LLM Integration:**
- `anthropic`: Anthropic Claude SDK
- `openai`: OpenAI SDK (works with Azure)
- `langchain` (optional): LLM orchestration and prompting

**Text-to-Speech:**
- Provider-specific SDKs (OpenAI, Azure, etc.)

**Storage & Database:**
- `sqlite3`: Metadata storage (built-in)
- `sqlalchemy`: ORM (optional, for easier database management)

**Utilities:**
- `python-dotenv`: Environment variable management
- `pydantic`: Data validation and settings
- `requests`: HTTP client
- `aiohttp`: Async HTTP client (for concurrent processing)
- `tqdm`: Progress bars
- `loguru`: Logging

### Configuration Management
- `.env` file for API keys and settings
- `config.py` for application configuration
- Pydantic Settings for type-safe configuration

Example `.env`:
```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_API_KEY=...
TTS_PROVIDER=openai
TTS_VOICE=alloy
DEFAULT_SEARCH_LIMIT=10
DATA_DIR=/path/to/data
```

## API Integrations

### arXiv API
**Endpoint**: `http://export.arxiv.org/api/query`

**Key Parameters:**
- `search_query`: Query string (e.g., `cat:cs.AI`, `ti:transformer`, `all:machine learning`)
- `start`: Pagination offset
- `max_results`: Number of results
- `sortBy`: `relevance`, `lastUpdatedDate`, `submittedDate`
- `sortOrder`: `ascending`, `descending`

**Rate Limits:**
- 1 request per 3 seconds recommended
- Bulk downloads: sleep between requests

**Popularity Metrics Options:**
- arXiv doesn't provide direct popularity metrics
- Possible approaches:
  - Use Semantic Scholar API to get citation counts
  - Use Altmetric API for social media mentions
  - Use arXiv's "number of updates" as proxy
  - Simply use "most recent" as default

### LLM APIs

**Anthropic Claude:**
- Endpoint: `https://api.anthropic.com/v1/messages`
- Models: `claude-3-5-sonnet-20241022`, `claude-3-opus-20240229`
- Context: Up to 200K tokens
- Recommended for: Complex analysis, structured output

**OpenAI (Azure):**
- Endpoint: Custom Azure endpoint
- Models: `gpt-4`, `gpt-4-turbo`, `gpt-4o`
- Context: Up to 128K tokens
- Recommended for: Integration with Azure TTS

### Text-to-Speech APIs

**OpenAI TTS:**
- Endpoint: `https://api.openai.com/v1/audio/speech`
- Models: `tts-1`, `tts-1-hd`
- Voices: `alloy`, `echo`, `fable`, `onyx`, `nova`, `shimmer`
- Max input: 4096 characters per request

**Azure Speech Services:**
- Supports SSML for fine control
- Many neural voices
- Batch processing support

## Project Structure

```
paper-podcasts/
├── .env                          # Environment variables (git-ignored)
├── .env.example                  # Example environment file
├── .gitignore
├── README.md
├── requirements.txt
├── setup.py                      # Package setup
│
├── src/
│   ├── DESIGN.md                # This document
│   │
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py              # Application entry point
│   │   ├── cli.py               # CLI interface
│   │   └── api.py               # REST API (optional)
│   │
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Application settings
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── arxiv_service.py     # arXiv API integration
│   │   ├── pdf_service.py       # PDF text extraction
│   │   ├── llm_service.py       # LLM analysis & summarization
│   │   ├── tts_service.py       # Text-to-speech
│   │   └── storage_service.py   # File and metadata management
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── paper.py             # Paper data models
│   │   ├── summary.py           # Summary data models
│   │   └── database.py          # Database models
│   │
│   ├── controllers/
│   │   ├── __init__.py
│   │   ├── search_controller.py # Search orchestration
│   │   └── pipeline_controller.py # Processing pipeline
│   │
│   └── utils/
│       ├── __init__.py
│       ├── logging.py           # Logging setup
│       ├── rate_limiter.py      # API rate limiting
│       └── validators.py        # Input validation
│
├── data/                        # Data directory (git-ignored)
│   ├── papers/
│   ├── summaries/
│   ├── audio/
│   └── database.db
│
├── tests/
│   ├── __init__.py
│   ├── test_arxiv_service.py
│   ├── test_pdf_service.py
│   ├── test_llm_service.py
│   └── ...
│
├── notebooks/                   # Jupyter notebooks for experimentation
│   └── experiments/
│
└── docs/                        # Additional documentation
    ├── api_reference.md
    └── user_guide.md
```

## Implementation Phases

### Phase 1: Foundation (MVP)
**Goal**: Basic end-to-end pipeline for one paper

- Set up project structure
- Implement arXiv service (basic search and download)
- Implement PDF text extraction (simple method)
- Implement LLM summarization (Claude or OpenAI)
- Implement basic TTS (OpenAI or Azure)
- Implement storage service (filesystem only)
- CLI for processing a single paper by arXiv ID
- Basic error handling and logging

**Success Criteria**: Can take arXiv ID, download paper, generate summary, create audio

### Phase 2: Search Capabilities
**Goal**: Multiple search modes

- Implement "recent papers by topic" search
- Implement "specific paper by title" search
- Add batch processing for multiple papers
- Add progress tracking and reporting
- Implement rate limiting for APIs
- Add resume capability for interrupted processing

**Success Criteria**: Can search and process multiple papers from different queries

### Phase 3: Popularity & Advanced Features
**Goal**: Popular papers and improved quality

- Implement "popular papers" (integrate external metrics)
- Add metadata database (SQLite)
- Implement duplicate detection
- Add advanced PDF extraction (images, structured content)
- Improve LLM prompts for better summaries
- Add multiple summary formats (quick vs. detailed)
- Add voice selection for TTS

**Success Criteria**: Full search capabilities with quality summaries

### Phase 4: Polish & Optimization
**Goal**: Production-ready application

- Add comprehensive error handling
- Implement retry logic with exponential backoff
- Add caching for LLM responses (cost optimization)
- Improve CLI with rich formatting
- Add configuration validation
- Write comprehensive tests
- Add documentation
- Optimize for cost and speed
- Add optional web interface (FastAPI)

**Success Criteria**: Reliable, well-documented, cost-effective system

## Open Questions & Future Considerations

### Open Questions

1. **PDF Extraction Method**:
   - Which library provides best quality/speed tradeoff?
   - Do we need image extraction initially, or text-only?
   - How to handle scanned/image-based PDFs?

2. **Popularity Metric**:
   - Use Semantic Scholar citation count?
   - Use social media mentions (Altmetric)?
   - Combine multiple signals?
   - Cost vs. benefit of external APIs?

3. **LLM Provider**:
   - Claude vs. OpenAI via Azure?
   - Consider cost per paper
   - Context window requirements (papers can be long)
   - Output quality differences

4. **TTS Provider**:
   - Which provider has best voice quality for technical content?
   - Cost per minute of audio
   - Handling of technical terms and equations
   - Language support requirements (English only initially?)

5. **Summary Formats**:
   - Single comprehensive summary?
   - Multiple lengths (quick/medium/detailed)?
   - Different audiences (expert/general)?

### Future Enhancements

**Content Quality**:
- Multi-modal analysis (include figures/graphs in analysis)
- Comparative summaries (how paper relates to others in field)
- Citation network analysis
- Quality scoring of papers

**User Experience**:
- Web interface for browsing and searching
- User accounts and preferences
- Playlist creation (collections of summaries)
- Playback controls and bookmarking
- RSS feed generation

**Audio Quality**:
- Background music
- Multiple voices (host + expert)
- Sound effects for section transitions
- Variable playback speed optimization

**Distribution**:
- Podcast feed generation
- Integration with podcast platforms
- Email digest subscriptions
- API for third-party integrations

**Advanced Features**:
- Custom summarization styles (formal/casual)
- Multi-language support
- Scheduled processing (daily digests)
- Topic tracking and alerts
- Personalized recommendations

**Scalability**:
- Async processing with queues (Celery/RQ)
- Caching layer (Redis)
- Distributed storage (S3)
- PostgreSQL for metadata
- Container deployment (Docker)
- Horizontal scaling

## Cost Estimation

### Per Paper Estimates (Rough)

**LLM Analysis** (assuming ~10K tokens input, 1K tokens output):
- Claude Sonnet: ~$0.03 - $0.05
- GPT-4 Turbo: ~$0.10 - $0.15
- GPT-4o: ~$0.02 - $0.05

**Text-to-Speech** (assuming 5-minute summary = ~750 words):
- OpenAI TTS: ~$0.02
- Azure TTS: ~$0.02 - $0.04
- ElevenLabs: ~$0.30 (higher quality)

**Total per paper**: ~$0.05 - $0.50 depending on provider choices

**Storage**: Negligible for small scale (GB range)

### Monthly Estimates (Example: 100 papers/month)
- Processing: $5 - $50
- Storage: < $1
- Total: ~$10 - $50/month

## Success Metrics

**Technical Metrics**:
- Processing time per paper
- API error rates
- Storage usage
- Cost per paper

**Quality Metrics**:
- Summary accuracy (manual review)
- Audio clarity and naturalness
- User comprehension (if user feedback available)
- Coverage of key paper elements

**Usage Metrics** (if multi-user):
- Papers processed
- Audio downloads/plays
- Search queries
- User retention

---

## Next Steps

1. Review and approve this design document
2. Set up development environment
3. Create `.env.example` with required API keys
4. Decide on initial provider choices (LLM, TTS)
5. Begin Phase 1 implementation
6. Test with sample papers from arXiv
