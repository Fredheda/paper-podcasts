import type {
  ChatMessage,
  EnqueueResponse,
  JobsResponse,
  LibraryContent,
  LibraryItem,
  Paper,
  SearchResponse
} from './types';

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.toString() || 'http://localhost:8000';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json'
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...init
  });

  if (!response.ok) {
    throw new Error(`Request failed (${response.status}).`);
  }

  return (await response.json()) as T;
}

export async function searchPapers(
  query: string,
  exactMatch: boolean,
  maxResults: number
): Promise<Paper[]> {
  const data = await request<SearchResponse>('/api/search', {
    method: 'POST',
    body: JSON.stringify({
      query,
      exact_match: exactMatch,
      max_results: maxResults
    })
  });
  return data.papers;
}

export async function enqueuePapers(papers: Paper[]): Promise<EnqueueResponse> {
  return request<EnqueueResponse>('/api/jobs/enqueue', {
    method: 'POST',
    body: JSON.stringify({ papers })
  });
}

export async function fetchJobs(): Promise<JobsResponse> {
  return request<JobsResponse>('/api/jobs');
}

export async function fetchLibrary(): Promise<LibraryItem[]> {
  return request<LibraryItem[]>('/api/library');
}

export async function fetchLibraryContent(arxivId: string): Promise<LibraryContent> {
  return request<LibraryContent>(`/api/library/${encodeURIComponent(arxivId)}/content`);
}

export async function updateListenStatus(
  arxivId: string,
  listenStatus: 'listened' | 'unlistened'
): Promise<LibraryItem> {
  return request<LibraryItem>(`/api/library/${encodeURIComponent(arxivId)}/listen`, {
    method: 'POST',
    body: JSON.stringify({
      listen_status: listenStatus
    })
  });
}

export async function checkHealth(): Promise<void> {
  await request<{ status: string }>('/health');
}

export type ChatStreamHandlers = {
  onToken: (text: string) => void;
  onDone: () => void;
  onError: (message: string) => void;
  signal?: AbortSignal;
};

export async function streamChat(
  arxivIds: string[],
  messages: ChatMessage[],
  handlers: ChatStreamHandlers
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
    body: JSON.stringify({ arxiv_ids: arxivIds, messages }),
    signal: handlers.signal
  });

  if (!response.ok || !response.body) {
    handlers.onError(`Chat request failed (${response.status}).`);
    return;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let idx: number;
      while ((idx = buffer.indexOf('\n\n')) !== -1) {
        const raw = buffer.slice(0, idx);
        buffer = buffer.slice(idx + 2);

        let event = 'message';
        let data = '';
        for (const line of raw.split('\n')) {
          if (line.startsWith('event:')) event = line.slice(6).trim();
          else if (line.startsWith('data:')) data += line.slice(5).trim();
        }
        if (!data) continue;

        try {
          const parsed = JSON.parse(data);
          if (event === 'token') handlers.onToken(parsed.text ?? '');
          else if (event === 'done') {
            handlers.onDone();
            return;
          } else if (event === 'error') {
            handlers.onError(parsed.message ?? 'Unknown error');
            return;
          }
        } catch {
          // skip malformed events
        }
      }
    }
    handlers.onDone();
  } catch (err) {
    if ((err as { name?: string }).name === 'AbortError') return;
    handlers.onError((err as Error).message);
  }
}
