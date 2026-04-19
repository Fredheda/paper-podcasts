import { FormEvent, useEffect, useRef, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { streamChat } from './api';
import type { ChatMessage, LibraryItem } from './types';

type Props = {
  selectedPapers: LibraryItem[];
  onClearSelection: () => void;
  onDeselect: (arxivId: string) => void;
};

function isMobileWidth(): boolean {
  return typeof window !== 'undefined' && window.innerWidth <= 768;
}

export function ChatPanel({ selectedPapers, onClearSelection, onDeselect }: Props): JSX.Element {
  const [isOpen, setIsOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [streaming, setStreaming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  useEffect(() => () => abortRef.current?.abort(), []);

  useEffect(() => {
    const lockScroll = isOpen && isFullscreen && isMobileWidth();
    document.body.style.overflow = lockScroll ? 'hidden' : '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen, isFullscreen]);

  const hasSelection = selectedPapers.length > 0;
  const canSend = hasSelection && input.trim().length > 0 && !streaming;

  function handleOpen(): void {
    setIsOpen(true);
    if (isMobileWidth()) setIsFullscreen(true);
  }

  function handleClose(): void {
    setIsOpen(false);
    setIsFullscreen(false);
  }

  async function handleSubmit(event: FormEvent): Promise<void> {
    event.preventDefault();
    if (!canSend) return;

    const userMessage: ChatMessage = { role: 'user', content: input.trim() };
    const next = [...messages, userMessage, { role: 'assistant' as const, content: '' }];
    setMessages(next);
    setInput('');
    setError(null);
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    await streamChat(
      selectedPapers.map((p) => p.arxiv_id),
      [...messages, userMessage],
      {
        onToken: (text) => {
          setMessages((prev) => {
            const copy = prev.slice();
            const last = copy[copy.length - 1];
            if (last && last.role === 'assistant') {
              copy[copy.length - 1] = { ...last, content: last.content + text };
            }
            return copy;
          });
        },
        onDone: () => {
          setStreaming(false);
        },
        onError: (message) => {
          setError(message);
          setStreaming(false);
          setMessages((prev) => {
            const copy = prev.slice();
            const last = copy[copy.length - 1];
            if (last && last.role === 'assistant' && last.content === '') {
              copy.pop();
            }
            return copy;
          });
        },
        signal: controller.signal
      }
    );
  }

  function handleClearChat(): void {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setStreaming(false);
  }

  const panelSizeClass = isFullscreen
    ? 'bottom-0 right-0 w-screen h-screen rounded-none'
    : 'bottom-20 right-5 w-[400px] h-[550px]';

  return (
    <>
      <div
        className={`fixed z-50 flex flex-col glass-card p-4 origin-bottom-right transition-[transform,opacity,width,height,bottom,right,border-radius] duration-300 ease-out
          ${panelSizeClass}
          ${isOpen ? 'scale-100 opacity-100 visible' : 'scale-0 opacity-0 invisible pointer-events-none'}`}
      >
        <header className="mb-3 flex items-start justify-between gap-2">
          <div>
            <h3 className="text-sm font-bold text-ink-950">
              Chat {hasSelection ? `(${selectedPapers.length} paper${selectedPapers.length > 1 ? 's' : ''})` : ''}
            </h3>
            <p className="text-xs text-slate-500">Grounded in selected papers.</p>
          </div>
          <div className="flex gap-1">
            <button
              type="button"
              className="soft-btn !px-2 !py-1 text-xs hidden md:inline-flex"
              onClick={() => setIsFullscreen((v) => !v)}
              title={isFullscreen ? 'Exit fullscreen' : 'Expand'}
            >
              {isFullscreen ? '⤡' : '⤢'}
            </button>
            {messages.length > 0 && (
              <button type="button" className="soft-btn !px-2 !py-1 text-xs" onClick={handleClearChat}>
                New
              </button>
            )}
            {hasSelection && (
              <button type="button" className="soft-btn !px-2 !py-1 text-xs" onClick={onClearSelection}>
                Clear
              </button>
            )}
            <button
              type="button"
              className="soft-btn !px-2 !py-1 text-xs"
              onClick={handleClose}
              title="Close"
              aria-label="Close chat"
            >
              ×
            </button>
          </div>
        </header>

        {hasSelection && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {selectedPapers.map((p) => (
              <button
                key={p.arxiv_id}
                onClick={() => onDeselect(p.arxiv_id)}
                title="Remove from chat"
                className="inline-flex max-w-full items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-xs text-slate-700 hover:border-rose-300 hover:text-rose-600"
              >
                <span className="line-clamp-1 max-w-[14ch]">{p.title}</span>
                <span aria-hidden>×</span>
              </button>
            ))}
          </div>
        )}

        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto rounded-xl border border-slate-200 bg-slate-50/60 p-3"
        >
          {!hasSelection && (
            <p className="text-xs text-slate-500">
              Select up to 5 completed papers from the library to start chatting.
            </p>
          )}
          {hasSelection && messages.length === 0 && (
            <p className="text-xs text-slate-500">
              Ask a question about the selected paper{selectedPapers.length > 1 ? 's' : ''}.
            </p>
          )}
          <div className="space-y-3">
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div
                  className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
                    m.role === 'user'
                      ? 'whitespace-pre-wrap bg-ink-900 text-white'
                      : 'border border-slate-200 bg-white text-slate-800'
                  }`}
                >
                  {m.role === 'user' ? (
                    m.content || ''
                  ) : m.content ? (
                    <div className="chat-markdown">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{m.content}</ReactMarkdown>
                    </div>
                  ) : streaming && i === messages.length - 1 ? (
                    '…'
                  ) : (
                    ''
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {error && <p className="mt-2 text-xs text-rose-600">{error}</p>}

        <form onSubmit={handleSubmit} className="mt-3 flex gap-2">
          <textarea
            className="field resize-none"
            rows={2}
            placeholder={hasSelection ? 'Ask a question…' : 'Select papers first'}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                void handleSubmit(e as unknown as FormEvent);
              }
            }}
            disabled={!hasSelection || streaming}
          />
          <button type="submit" className="primary-btn" disabled={!canSend}>
            {streaming ? '…' : 'Send'}
          </button>
        </form>
      </div>

      <button
        type="button"
        onClick={handleOpen}
        className={`fixed bottom-5 right-5 z-50 primary-btn !rounded-full !px-5 !py-3 flex items-center gap-2 shadow-lg transition-all duration-300
          ${isOpen ? 'opacity-0 invisible pointer-events-none scale-90' : 'opacity-100 visible scale-100'}`}
        aria-label="Open chat"
      >
        <span className="pointer-events-none absolute inset-0 rounded-full bg-ink-900/20 animate-ping" />
        <svg
          className="relative h-4 w-4"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
        </svg>
        <span className="relative text-sm font-semibold">
          Chat{selectedPapers.length > 0 ? ` (${selectedPapers.length})` : ''}
        </span>
      </button>
    </>
  );
}
