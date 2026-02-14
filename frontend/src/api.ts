import type {
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
