import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import {
  API_BASE_URL,
  checkHealth,
  enqueuePapers,
  fetchJobs,
  fetchLibrary,
  fetchLibraryContent,
  searchPapers,
  updateListenStatus
} from './api';
import type { JobsResponse, LibraryContent, LibraryItem, Paper } from './types';
import { ChatPanel } from './ChatPanel';

const MAX_CHAT_PAPERS = 5;

type Tab = 'search' | 'queue' | 'library';
type LibraryStatusFilter = 'all' | 'completed' | 'in progress';
type ListenFilter = 'all' | 'unlistened' | 'listened';
type ContentTab = 'abstract' | 'summary';
type ToastTone = 'success' | 'info' | 'error';
type ToastState = { tone: ToastTone; message: string };

const POLL_INTERVAL_MS = 2500;

function formatAuthors(authors: { name?: string }[], max = 3): string {
  if (!authors.length) return 'Unknown authors';
  const names = authors.slice(0, max).map((author) => author.name || 'Unknown');
  return authors.length > max
    ? `${names.join(', ')} + ${authors.length - max} more`
    : names.join(', ');
}

function formatStage(stage: string): string {
  return stage.replace(/_/g, ' ').replace(/\b\w/g, (letter: string) => letter.toUpperCase());
}

function formatDateLabel(isoDate: string | null): string {
  if (!isoDate) return 'N/A';
  const parsed = new Date(isoDate);
  if (Number.isNaN(parsed.getTime())) return 'N/A';
  return parsed.toLocaleString();
}

function stageTone(stage: string): string {
  if (stage === 'completed') return 'bg-emerald-50 text-emerald-700 ring-emerald-200';
  if (stage === 'failed') return 'bg-rose-50 text-rose-700 ring-rose-200';
  if (stage === 'queued') return 'bg-amber-50 text-amber-700 ring-amber-200';
  return 'bg-sky-50 text-sky-700 ring-sky-200';
}

function sanitizeSummaryHtml(input: string): string {
  if (!input.trim()) return '';

  const parser = new DOMParser();
  const doc = parser.parseFromString(input, 'text/html');

  // Remove dangerous elements outright
  doc
    .querySelectorAll('script, style, iframe, object, embed, form, meta, link, base, svg, math, img, video, audio, source')
    .forEach((node) => {
      node.remove();
    });

  const isSafeHref = (value: string): boolean => {
    const trimmed = value.trim();
    if (!trimmed) return false;
    if (trimmed.startsWith('/')) return true;
    try {
      const url = new URL(trimmed, window.location.origin);
      return ['http:', 'https:', 'mailto:', 'tel:'].includes(url.protocol);
    } catch {
      return false;
    }
  };

  // Remove inline handlers/styles and unsafe URL attributes
  doc.querySelectorAll('*').forEach((element) => {
    Array.from(element.attributes).forEach((attr) => {
      const name = attr.name.toLowerCase();
      const value = attr.value.trim();
      const valueLower = value.toLowerCase();
      if (name.startsWith('on') || name === 'style') {
        element.removeAttribute(attr.name);
        return;
      }

      if (name === 'href') {
        if (!isSafeHref(value) || valueLower.startsWith('javascript:') || valueLower.startsWith('data:')) {
          element.removeAttribute(attr.name);
        }
        return;
      }

      if (['src', 'srcset', 'xlink:href'].includes(name)) {
        element.removeAttribute(attr.name);
      }
    });

    if (element.tagName.toLowerCase() === 'a') {
      element.setAttribute('rel', 'noopener noreferrer');
      element.setAttribute('target', '_blank');
    }
  });

  return doc.body.innerHTML;
}

function escapeHtml(input: string): string {
  return input
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function inlineMarkdownToHtml(text: string): string {
  // Preserve inline HTML tags for mixed markdown+HTML content,
  // while escaping everything else before markdown transforms.
  const htmlTags: string[] = [];
  const withPlaceholders = text.replace(/<\/?[a-zA-Z][^>]*>/g, (tag) => {
    const token = `@@HTMLTAG${htmlTags.length}@@`;
    htmlTags.push(tag);
    return token;
  });

  const rendered = escapeHtml(withPlaceholders)
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
    .replace(/__([^_]+)__/g, '<strong>$1</strong>')
    .replace(/\*([^*]+)\*/g, '<em>$1</em>')
    .replace(/_([^_]+)_/g, '<em>$1</em>')
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noreferrer">$1</a>');

  return rendered.replace(/@@HTMLTAG(\d+)@@/g, (_m, index) => htmlTags[Number(index)] || '');
}

function markdownToHtml(markdown: string): string {
  const normalized = markdown.replace(/\r\n/g, '\n');
  const lines = normalized.split('\n');
  const chunks: string[] = [];
  let inList = false;
  let listType: 'ul' | 'ol' | null = null;
  let inCodeBlock = false;
  let codeLines: string[] = [];
  let paragraphBuffer: string[] = [];

  const flushList = (): void => {
    if (inList) {
      chunks.push(`</${listType || 'ul'}>`);
      inList = false;
      listType = null;
    }
  };

  const flushCodeBlock = (): void => {
    if (inCodeBlock) {
      chunks.push(`<pre><code>${codeLines.join('\n')}</code></pre>`);
      inCodeBlock = false;
      codeLines = [];
    }
  };

  const flushParagraph = (): void => {
    if (paragraphBuffer.length > 0) {
      const paragraph = paragraphBuffer.join(' ').trim();
      if (paragraph) chunks.push(`<p>${inlineMarkdownToHtml(paragraph)}</p>`);
      paragraphBuffer = [];
    }
  };

  for (const rawLine of lines) {
    const line = rawLine.trim();

    if (line.startsWith('```')) {
      flushParagraph();
      flushList();
      if (inCodeBlock) {
        flushCodeBlock();
      } else {
        inCodeBlock = true;
      }
      continue;
    }

    if (inCodeBlock) {
      codeLines.push(escapeHtml(rawLine));
      continue;
    }

    if (!line.trim()) {
      flushParagraph();
      flushList();
      continue;
    }

    const headingMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (headingMatch) {
      flushParagraph();
      flushList();
      const level = headingMatch[1].length;
      chunks.push(`<h${level}>${inlineMarkdownToHtml(headingMatch[2])}</h${level}>`);
      continue;
    }

    if (/^---+$/.test(line) || /^\*\*\*+$/.test(line)) {
      flushParagraph();
      flushList();
      chunks.push('<hr />');
      continue;
    }

    const unorderedMatch = line.match(/^[-*]\s+(.*)$/);
    const orderedMatch = line.match(/^\d+[.)]\s+(.*)$/);
    if (unorderedMatch || orderedMatch) {
      const nextListType: 'ul' | 'ol' = orderedMatch ? 'ol' : 'ul';
      flushParagraph();
      if (!inList || listType !== nextListType) {
        flushList();
        chunks.push(`<${nextListType}>`);
        inList = true;
        listType = nextListType;
      }
      const listText = (orderedMatch?.[1] || unorderedMatch?.[1] || '').trim();
      chunks.push(`<li>${inlineMarkdownToHtml(listText)}</li>`);
      continue;
    }

    const blockQuoteMatch = line.match(/^>\s?(.*)$/);
    if (blockQuoteMatch) {
      flushParagraph();
      if (!inList) {
        chunks.push(`<blockquote><p>${inlineMarkdownToHtml(blockQuoteMatch[1])}</p></blockquote>`);
      } else {
        chunks.push(`<li>${inlineMarkdownToHtml(blockQuoteMatch[1])}</li>`);
      }
      continue;
    }

    flushList();
    paragraphBuffer.push(line);
  }

  flushParagraph();
  flushList();
  flushCodeBlock();

  return chunks.join('');
}

function looksLikeMarkdown(input: string): boolean {
  const sample = input.trim();
  if (!sample) return false;
  return (
    /(^|\n)\s{0,3}#{1,6}\s+/.test(sample) ||
    /(^|\n)\s*[-*]\s+/.test(sample) ||
    /(^|\n)\s*\d+[.)]\s+/.test(sample) ||
    /(^|\n)\s*>\s+/.test(sample) ||
    /(^|\n)\s*```/.test(sample) ||
    /\[[^\]]+\]\((?:https?:\/\/|\/)[^)]+\)/.test(sample) ||
    /(\*\*|__)[^*_]+(\*\*|__)/.test(sample)
  );
}

function summaryTextToSafeHtml(summaryText: string): string {
  if (!summaryText.trim()) return '';
  const hasHtmlTag = /<\/?[a-z][\s\S]*>/i.test(summaryText);
  const markdownLikely = looksLikeMarkdown(summaryText);
  const candidate = markdownLikely || hasHtmlTag ? markdownToHtml(summaryText) : summaryText;
  return sanitizeSummaryHtml(candidate);
}

export default function App(): JSX.Element {
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const [tab, setTab] = useState<Tab>('search');
  const [query, setQuery] = useState('large language models');
  const [exactMatch, setExactMatch] = useState(true);
  const [maxResults, setMaxResults] = useState(5);

  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [searchResults, setSearchResults] = useState<Paper[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [queueMessage, setQueueMessage] = useState<string | null>(null);

  const [jobsData, setJobsData] = useState<JobsResponse | null>(null);
  const [jobsError, setJobsError] = useState<string | null>(null);

  const [library, setLibrary] = useState<LibraryItem[]>([]);
  const [libraryError, setLibraryError] = useState<string | null>(null);

  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  const [libraryStatusFilter, setLibraryStatusFilter] = useState<LibraryStatusFilter>('all');
  const [listenFilter, setListenFilter] = useState<ListenFilter>('all');
  const [librarySearchQuery, setLibrarySearchQuery] = useState<string>('');
  const [contentByPaperId, setContentByPaperId] = useState<Record<string, LibraryContent>>({});
  const [contentLoadingIds, setContentLoadingIds] = useState<Set<string>>(new Set());
  const [activeContentTabByPaperId, setActiveContentTabByPaperId] = useState<Record<string, ContentTab>>({});
  const [listenUpdatingIds, setListenUpdatingIds] = useState<Set<string>>(new Set());
  const [toast, setToast] = useState<ToastState | null>(null);
  const [selectedForChat, setSelectedForChat] = useState<Set<string>>(new Set());

  function toggleChatSelection(arxivId: string): void {
    setSelectedForChat((prev) => {
      const next = new Set(prev);
      if (next.has(arxivId)) {
        next.delete(arxivId);
      } else if (next.size < MAX_CHAT_PAPERS) {
        next.add(arxivId);
      }
      return next;
    });
  }

  const selectedForChatPapers = useMemo(
    () => library.filter((item) => selectedForChat.has(item.arxiv_id)),
    [library, selectedForChat]
  );

  const selectedPapers = useMemo(
    () => searchResults.filter((paper) => selectedIds.has(paper.arxiv_id)),
    [searchResults, selectedIds]
  );

  const filteredLibrary = useMemo(() => {
    const query = librarySearchQuery.trim().toLowerCase();
    return library.filter((item) => {
      const statusMatch =
        libraryStatusFilter === 'all' ||
        (libraryStatusFilter === 'completed' ? item.status === 'completed' : item.status !== 'completed');

      const listenMatch =
        listenFilter === 'all' ||
        (listenFilter === 'listened' ? item.listen_status === 'listened' : item.listen_status === 'unlistened');

      const searchMatch =
        !query ||
        item.title.toLowerCase().includes(query) ||
        item.arxiv_id.toLowerCase().includes(query) ||
        item.authors.some((author) => author.name?.toLowerCase().includes(query));

      return statusMatch && listenMatch && searchMatch;
    });
  }, [library, libraryStatusFilter, listenFilter, librarySearchQuery]);

  useEffect(() => {
    async function bootstrap(): Promise<void> {
      try {
        await checkHealth();
        setBackendOnline(true);
      } catch {
        setBackendOnline(false);
      }
    }

    void bootstrap();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 2800);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    function handleGlobalShortcuts(event: KeyboardEvent): void {
      const target = event.target as HTMLElement | null;
      const isTextInput =
        target?.tagName === 'INPUT' ||
        target?.tagName === 'TEXTAREA' ||
        target?.tagName === 'SELECT' ||
        Boolean(target?.isContentEditable);

      if (event.key === '/' && !isTextInput) {
        event.preventDefault();
        setTab('search');
        searchInputRef.current?.focus();
        setToast({ tone: 'info', message: 'Focused search. Shortcut: 1/2/3 switches tabs.' });
        return;
      }

      if (isTextInput || event.metaKey || event.ctrlKey || event.altKey) return;

      if (event.key === '1') setTab('search');
      if (event.key === '2') setTab('queue');
      if (event.key === '3') setTab('library');
    }

    window.addEventListener('keydown', handleGlobalShortcuts);
    return () => window.removeEventListener('keydown', handleGlobalShortcuts);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function refresh(): Promise<void> {
      try {
        const [jobs, items] = await Promise.all([fetchJobs(), fetchLibrary()]);
        if (cancelled) return;
        setJobsData(jobs);
        setLibrary(items);
        setJobsError(null);
        setLibraryError(null);
      } catch (error) {
        if (cancelled) return;
        const message = error instanceof Error ? error.message : 'Failed to fetch backend data.';
        setJobsError(message);
        setLibraryError(message);
      }
    }

    void refresh();
    const timer = window.setInterval(() => {
      void refresh();
    }, POLL_INTERVAL_MS);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  async function onSearch(event: FormEvent): Promise<void> {
    event.preventDefault();
    const trimmed = query.trim();
    if (!trimmed) return;

    setSearching(true);
    setSearchError(null);
    setQueueMessage(null);

    try {
      const papers = await searchPapers(trimmed, exactMatch, maxResults);
      setSearchResults(papers);
      setSelectedIds(new Set());
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Search failed.';
      setSearchError(message);
    } finally {
      setSearching(false);
    }
  }

  async function onEnqueue(): Promise<void> {
    if (!selectedPapers.length) return;

    try {
      const result = await enqueuePapers(selectedPapers);
      setQueueMessage(`Queued ${result.queued_count}, skipped ${result.skipped_count} already active/queued.`);
      setToast({
        tone: 'success',
        message: `Queued ${result.queued_count} paper(s).`
      });
      setSelectedIds(new Set());
      const jobs = await fetchJobs();
      setJobsData(jobs);
      setTab('queue');
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to enqueue papers.';
      setQueueMessage(message);
      setToast({ tone: 'error', message });
    }
  }

  function toggleSelection(arxivId: string): void {
    setSelectedIds((previous) => {
      const next = new Set(previous);
      if (next.has(arxivId)) next.delete(arxivId);
      else next.add(arxivId);
      return next;
    });
  }

  async function loadContentForPaper(arxivId: string): Promise<void> {
    if (contentByPaperId[arxivId]) return;
    if (contentLoadingIds.has(arxivId)) return;

    setContentLoadingIds((previous) => new Set(previous).add(arxivId));

    try {
      const content = await fetchLibraryContent(arxivId);
      setContentByPaperId((previous) => ({ ...previous, [arxivId]: content }));
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to load paper content.';
      setLibraryError(message);
    } finally {
      setContentLoadingIds((previous) => {
        const next = new Set(previous);
        next.delete(arxivId);
        return next;
      });
    }
  }

  function setActiveContentTab(arxivId: string, contentTab: ContentTab): void {
    setActiveContentTabByPaperId((previous) => ({ ...previous, [arxivId]: contentTab }));
    if (contentTab !== 'abstract') void loadContentForPaper(arxivId);
  }

  async function onToggleListenStatus(item: LibraryItem): Promise<void> {
    const nextStatus = item.listen_status === 'listened' ? 'unlistened' : 'listened';

    setListenUpdatingIds((previous) => new Set(previous).add(item.arxiv_id));

    try {
      const updatedItem = await updateListenStatus(item.arxiv_id, nextStatus);
      setLibrary((previous) => previous.map((entry) => (entry.arxiv_id === updatedItem.arxiv_id ? updatedItem : entry)));
      setToast({
        tone: 'success',
        message: `${nextStatus === 'listened' ? 'Marked as listened' : 'Marked as unlistened'}: ${updatedItem.title}`
      });
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Failed to update listen status.';
      setLibraryError(message);
      setToast({ tone: 'error', message });
    } finally {
      setListenUpdatingIds((previous) => {
        const next = new Set(previous);
        next.delete(item.arxiv_id);
        return next;
      });
    }
  }

  const queueCounts = jobsData?.counts || { active: 0, queued: 0, completed: 0, failed: 0 };

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-7xl flex-col gap-6 px-4 py-6 md:px-8">
      <header className="glass-card relative overflow-hidden p-5 md:p-7">
        <div className="pointer-events-none absolute -top-20 right-0 h-60 w-60 rounded-full bg-coral-500/20 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-16 -left-14 h-52 w-52 rounded-full bg-mint-500/20 blur-3xl" />

        <div className="relative flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div className="max-w-2xl space-y-3">
            <p className="pill">Paper Podcasts Platform</p>
            <h1 className="text-3xl font-black tracking-tight text-ink-950 md:text-5xl">
              Discover, process, and listen to research at production speed.
            </h1>
            <p className="text-sm text-slate-600 md:text-base">
              Designed for async paper operations with queue visibility, rich library tools, and clear status feedback.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <StatCard label="Active" value={String(queueCounts.active)} />
            <StatCard label="Queued" value={String(queueCounts.queued)} />
            <StatCard label="Done" value={String(queueCounts.completed)} />
            <StatCard label="Library" value={String(library.length)} />
          </div>
        </div>
      </header>

      <div className="glass-card p-3">
        <div className="flex flex-wrap items-center gap-2">
          <NavButton active={tab === 'search'} onClick={() => setTab('search')} label="Search" />
          <NavButton active={tab === 'queue'} onClick={() => setTab('queue')} label="Queue" />
          <NavButton active={tab === 'library'} onClick={() => setTab('library')} label="Library" />
          <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-500">
            Shortcuts: `/` focus, `1/2/3` tabs
          </span>
          <div className="ml-auto inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-semibold">
            <span
              className={`h-2.5 w-2.5 rounded-full ${
                backendOnline === true
                  ? 'bg-emerald-500'
                  : backendOnline === false
                  ? 'bg-rose-500'
                  : 'bg-amber-500'
              }`}
            />
            {backendOnline === null && 'Checking backend'}
            {backendOnline === true && 'Backend online'}
            {backendOnline === false && 'Backend offline'}
          </div>
        </div>
      </div>

      {tab === 'search' && (
        <section className="glass-card p-5 md:p-6">
          <div className="mb-5 flex flex-col gap-2">
            <h2 className="text-xl font-bold text-ink-950">Search papers</h2>
            <p className="text-sm text-slate-600">Find papers, select multiple, and enqueue with one action.</p>
          </div>

          <form onSubmit={onSearch} className="grid gap-3 lg:grid-cols-[1fr_auto_auto_auto] lg:items-center">
            <input
              ref={searchInputRef}
              className="field"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Try: retrieval augmented generation"
              required
            />

            <label className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={exactMatch}
                onChange={(event) => setExactMatch(event.target.checked)}
                className="h-4 w-4 rounded border-slate-300"
              />
              Exact match
            </label>

            <label className="inline-flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700">
              <span>Max</span>
              <input
                className="w-14 rounded-md border border-slate-200 px-2 py-1 text-right"
                type="number"
                min={1}
                max={20}
                value={maxResults}
                onChange={(event) => setMaxResults(Number(event.target.value))}
              />
            </label>

            <button type="submit" className="primary-btn" disabled={searching}>
              {searching ? 'Searching...' : 'Search'}
            </button>
          </form>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
            <span className="pill">Results: {searchResults.length}</span>
            <span className="pill">Selected: {selectedPapers.length}</span>
            <button className="primary-btn ml-auto" onClick={onEnqueue} disabled={!selectedPapers.length}>
              Queue selected papers
            </button>
          </div>

          {searchError && <Alert tone="error" message={searchError} className="mt-4" />}
          {queueMessage && <Alert tone="success" message={queueMessage} className="mt-4" />}

          {searchResults.length === 0 ? (
            <EmptyState
              title="No search results yet"
              description="Run a search to build your queue and start the pipeline."
              className="mt-6"
            />
          ) : (
            <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {searchResults.map((paper, index) => {
                const selected = selectedIds.has(paper.arxiv_id);
                return (
                  <article
                    key={paper.arxiv_id}
                    className={`animate-[fade-in_320ms_ease-out_both] rounded-2xl border bg-white p-4 shadow-sm transition ${
                      selected ? 'border-mint-500 ring-4 ring-mint-500/15' : 'border-slate-200 hover:border-slate-300'
                    }`}
                    style={{ animationDelay: `${Math.min(index * 45, 260)}ms` }}
                  >
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <label className="inline-flex cursor-pointer items-center gap-2 text-sm font-medium text-slate-700">
                        <input
                          type="checkbox"
                          className="h-4 w-4 rounded border-slate-300"
                          checked={selected}
                          onChange={() => toggleSelection(paper.arxiv_id)}
                        />
                        Select
                      </label>
                      <span className="pill">{paper.arxiv_id}</span>
                    </div>

                    <h3 className="line-clamp-2 text-base font-bold text-ink-950">{paper.title}</h3>
                    <p className="mt-1 text-xs text-slate-500">{formatAuthors(paper.authors)}</p>
                    <p className="mt-3 line-clamp-5 text-sm leading-relaxed text-slate-700">{paper.abstract}</p>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      )}

      {tab === 'queue' && (
        <section className="glass-card p-5 md:p-6">
          <div className="mb-5 flex flex-col gap-2">
            <h2 className="text-xl font-bold text-ink-950">Queue monitor</h2>
            <p className="text-sm text-slate-600">Live throughput and per-paper progress from the background workers.</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <MetricCard label="Active" value={queueCounts.active} accent="mint" />
            <MetricCard label="Queued" value={queueCounts.queued} accent="slate" />
            <MetricCard label="Completed" value={queueCounts.completed} accent="emerald" />
            <MetricCard label="Failed" value={queueCounts.failed} accent="rose" />
          </div>

          {jobsError && <Alert tone="error" message={jobsError} className="mt-4" />}

          {!jobsData?.jobs.length ? (
            <EmptyState
              title="No jobs yet"
              description="Select papers from Search and enqueue them to see progress here."
              className="mt-6"
            />
          ) : (
            <div className="mt-6 grid gap-3">
              {jobsData.jobs.map((job, index) => (
                <article
                  key={job.arxiv_id}
                  className="animate-[fade-in_300ms_ease-out_both] rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                  style={{ animationDelay: `${Math.min(index * 35, 200)}ms` }}
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h3 className="font-semibold text-ink-950">{job.title}</h3>
                      <p className="mt-1 text-sm text-slate-500">{job.message}</p>
                    </div>
                    <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${stageTone(job.stage)}`}>
                      {formatStage(job.stage)}
                    </span>
                  </div>

                  <div className="mt-3 h-2.5 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-gradient-to-r from-mint-500 to-cyan-500 transition-all"
                      style={{ width: `${Math.round(job.progress * 100)}%` }}
                    />
                  </div>

                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                    <span>{job.is_active ? 'Running now' : job.queue_position ? `Queue #${job.queue_position}` : 'Idle'}</span>
                    <span>Updated: {formatDateLabel(job.updated_at)}</span>
                  </div>

                  {job.error && <Alert tone="error" message={job.error} className="mt-3" />}
                </article>
              ))}
            </div>
          )}
        </section>
      )}

      {tab === 'library' && (
        <>
        <section className="glass-card p-5 md:p-6">
          <div className="mb-5 flex flex-col gap-2">
            <h2 className="text-xl font-bold text-ink-950">Library</h2>
            <p className="text-sm text-slate-600">
              Filter by processing/listening status, play audio, and inspect summaries and extracted content.
            </p>
          </div>

          <label className="mb-3 block space-y-1 text-sm font-medium text-slate-700">
            Search
            <input
              type="search"
              className="field"
              placeholder="Filter by title, author, or arXiv ID"
              value={librarySearchQuery}
              onChange={(event) => setLibrarySearchQuery(event.target.value)}
            />
          </label>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <label className="space-y-1 text-sm font-medium text-slate-700">
              Processing status
              <select
                className="field"
                value={libraryStatusFilter}
                onChange={(event) => setLibraryStatusFilter(event.target.value as LibraryStatusFilter)}
              >
                <option value="all">All</option>
                <option value="completed">Completed</option>
                <option value="in progress">In progress</option>
              </select>
            </label>

            <label className="space-y-1 text-sm font-medium text-slate-700">
              Listen status
              <select
                className="field"
                value={listenFilter}
                onChange={(event) => setListenFilter(event.target.value as ListenFilter)}
              >
                <option value="all">All</option>
                <option value="unlistened">Unlistened</option>
                <option value="listened">Listened</option>
              </select>
            </label>

            <div className="glass-card flex items-center justify-center rounded-xl px-3 py-2 text-sm font-semibold text-slate-600">
              Showing {filteredLibrary.length}
            </div>
            <div className="glass-card flex items-center justify-center rounded-xl px-3 py-2 text-sm font-semibold text-slate-600">
              Unlistened {library.filter((item) => item.listen_status === 'unlistened').length}
            </div>
          </div>

          {libraryError && <Alert tone="error" message={libraryError} className="mt-4" />}

          {!filteredLibrary.length ? (
            <EmptyState
              title="No library matches"
              description="Try changing filters or process additional papers from the Search tab."
              className="mt-6"
            />
          ) : (
            <div className="mt-6 grid gap-4 lg:grid-cols-2">
              {filteredLibrary.map((item, index) => {
                const activeContentTab = activeContentTabByPaperId[item.arxiv_id] || 'abstract';
                const content = contentByPaperId[item.arxiv_id];
                const isLoadingContent = contentLoadingIds.has(item.arxiv_id);
                const isListenUpdating = listenUpdatingIds.has(item.arxiv_id);
                const audioUrl = item.audio_url ? `${API_BASE_URL}${item.audio_url}` : null;

                return (
                  <article
                    key={`${item.arxiv_id}-${item.title}`}
                    className="animate-[fade-in_320ms_ease-out_both] rounded-2xl border border-slate-200 bg-white p-4 shadow-sm"
                    style={{ animationDelay: `${Math.min(index * 40, 260)}ms` }}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div className="flex min-w-0 items-start gap-2">
                        {item.status === 'completed' && (
                          <input
                            type="checkbox"
                            title={
                              selectedForChat.has(item.arxiv_id)
                                ? 'Remove from chat'
                                : selectedForChat.size >= MAX_CHAT_PAPERS
                                ? `Chat limit is ${MAX_CHAT_PAPERS} papers`
                                : 'Add to chat'
                            }
                            checked={selectedForChat.has(item.arxiv_id)}
                            disabled={
                              !selectedForChat.has(item.arxiv_id) && selectedForChat.size >= MAX_CHAT_PAPERS
                            }
                            onChange={() => toggleChatSelection(item.arxiv_id)}
                            className="mt-1 h-4 w-4 cursor-pointer accent-ink-900"
                          />
                        )}
                        <div className="min-w-0">
                          <h3 className="line-clamp-2 text-base font-bold text-ink-950">{item.title}</h3>
                          <p className="mt-1 text-xs text-slate-500">{formatAuthors(item.authors)}</p>
                        </div>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        <span className={`rounded-full px-2.5 py-1 text-xs font-semibold ring-1 ${stageTone(item.status)}`}>
                          {item.status}
                        </span>
                        <span className="rounded-full bg-slate-50 px-2.5 py-1 text-xs font-semibold text-slate-600 ring-1 ring-slate-200">
                          {item.listen_status}
                        </span>
                      </div>
                    </div>

                    <div className="mt-3 flex flex-wrap gap-2">
                      <button className="soft-btn" onClick={() => void onToggleListenStatus(item)} disabled={isListenUpdating}>
                        {isListenUpdating
                          ? 'Updating...'
                          : item.listen_status === 'listened'
                          ? 'Mark Unlistened'
                          : 'Mark Listened'}
                      </button>
                      {item.arxiv_url && (
                        <a href={item.arxiv_url} target="_blank" rel="noreferrer" className="soft-btn">
                          Open on arXiv
                        </a>
                      )}
                    </div>

                    <p className="mt-2 text-xs text-slate-500">Last listened: {formatDateLabel(item.last_listened_at)}</p>

                    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-2">
                      {audioUrl ? (
                        <audio controls preload="none" src={audioUrl} className="w-full" />
                      ) : (
                        <p className="px-1 py-2 text-xs text-slate-500">Audio not yet generated.</p>
                      )}
                    </div>

                    <div className="mt-4 flex flex-wrap gap-2">
                      <button
                        className={`tab-btn ${activeContentTab === 'abstract' ? 'tab-btn-active' : ''}`}
                        onClick={() => setActiveContentTab(item.arxiv_id, 'abstract')}
                      >
                        Abstract
                      </button>
                      <button
                        className={`tab-btn ${activeContentTab === 'summary' ? 'tab-btn-active' : ''}`}
                        onClick={() => setActiveContentTab(item.arxiv_id, 'summary')}
                      >
                        Summary
                      </button>
                    </div>

                    <div className="mt-3 rounded-xl border border-slate-200 bg-slate-50 p-3 text-sm leading-relaxed text-slate-700">
                      {activeContentTab === 'abstract' && <p className="whitespace-pre-wrap">{item.abstract}</p>}

                      {activeContentTab === 'summary' && (
                        <>
                          {isLoadingContent && <p className="text-slate-500">Loading summary...</p>}
                          {!isLoadingContent && (
                            <RichSummaryBlock summaryText={content?.summary_text || ''} />
                          )}
                        </>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
        <ChatPanel
          selectedPapers={selectedForChatPapers}
          onClearSelection={() => setSelectedForChat(new Set())}
          onDeselect={(id) => toggleChatSelection(id)}
        />
        </>
      )}

      {toast && <Toast tone={toast.tone} message={toast.message} />}
    </div>
  );
}

function NavButton({ active, onClick, label }: { active: boolean; onClick: () => void; label: string }): JSX.Element {
  return (
    <button className={`tab-btn ${active ? 'tab-btn-active' : ''}`} onClick={onClick}>
      {label}
    </button>
  );
}

function StatCard({ label, value }: { label: string; value: string }): JSX.Element {
  return (
    <div className="rounded-xl border border-white/70 bg-white/85 px-3 py-2 text-center shadow-sm">
      <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="text-xl font-black text-ink-950">{value}</p>
    </div>
  );
}

function MetricCard({
  label,
  value,
  accent
}: {
  label: string;
  value: number;
  accent: 'mint' | 'slate' | 'emerald' | 'rose';
}): JSX.Element {
  const tone: Record<'mint' | 'slate' | 'emerald' | 'rose', string> = {
    mint: 'from-mint-500/20 to-cyan-500/10 text-ink-950',
    slate: 'from-slate-300/35 to-slate-100/60 text-ink-900',
    emerald: 'from-emerald-300/30 to-emerald-100/60 text-emerald-800',
    rose: 'from-rose-300/30 to-rose-100/60 text-rose-800'
  };

  return (
    <div className={`rounded-2xl border border-slate-200 bg-gradient-to-br p-4 shadow-sm ${tone[accent]}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.14em] text-slate-500">{label}</p>
      <p className="mt-1 text-3xl font-black">{value}</p>
    </div>
  );
}

function Alert({
  tone,
  message,
  className = ''
}: {
  tone: 'error' | 'success';
  message: string;
  className?: string;
}): JSX.Element {
  const toneClass =
    tone === 'error'
      ? 'border-rose-200 bg-rose-50 text-rose-700'
      : 'border-emerald-200 bg-emerald-50 text-emerald-700';

  return <p className={`${className} rounded-xl border px-3 py-2 text-sm font-medium ${toneClass}`}>{message}</p>;
}

function EmptyState({
  title,
  description,
  className = ''
}: {
  title: string;
  description: string;
  className?: string;
}): JSX.Element {
  return (
    <div className={`${className} rounded-2xl border border-dashed border-slate-300 bg-slate-50 p-8 text-center`}>
      <h3 className="text-base font-bold text-ink-950">{title}</h3>
      <p className="mt-1 text-sm text-slate-600">{description}</p>
    </div>
  );
}

function Toast({ tone, message }: { tone: ToastTone; message: string }): JSX.Element {
  const toneClasses =
    tone === 'success'
      ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
      : tone === 'error'
      ? 'border-rose-200 bg-rose-50 text-rose-700'
      : 'border-sky-200 bg-sky-50 text-sky-700';

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-50 animate-[slide-up_220ms_ease-out]">
      <div className={`rounded-xl border px-4 py-3 text-sm font-semibold shadow-lg ${toneClasses}`}>{message}</div>
    </div>
  );
}

function RichSummaryBlock({ summaryText }: { summaryText: string }): JSX.Element {
  if (!summaryText.trim()) {
    return <p className="text-slate-500">No summary available.</p>;
  }

  const safeHtml = summaryTextToSafeHtml(summaryText);
  if (!safeHtml.trim()) {
    return <p className="text-slate-500">No summary available.</p>;
  }

  return (
    <div
      className="max-h-72 overflow-y-auto rounded-lg bg-white px-3 py-2 text-[0.95rem] leading-relaxed text-slate-800
      [&_h1]:mb-2 [&_h1]:mt-4 [&_h1]:text-xl [&_h1]:font-bold
      [&_h2]:mb-2 [&_h2]:mt-4 [&_h2]:text-lg [&_h2]:font-bold
      [&_h3]:mb-1 [&_h3]:mt-3 [&_h3]:text-base [&_h3]:font-semibold
      [&_p]:my-2
      [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5
      [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5
      [&_li]:my-1
      [&_strong]:font-semibold
      [&_em]:italic
      [&_code]:rounded [&_code]:bg-slate-100 [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-[0.9em]"
      dangerouslySetInnerHTML={{ __html: safeHtml }}
    />
  );
}
