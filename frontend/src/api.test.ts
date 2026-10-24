import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  enqueuePapers,
  fetchLibraryContent,
  searchPapers,
  streamChat,
  updateListenStatus
} from './api';
import { paper } from './test/fixtures';

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' }
  });
}

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    }
  });
  return new Response(stream, { status: 200 });
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('request helpers', () => {
  it('searchPapers posts the query and returns the papers', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ papers: [paper()] }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await searchPapers('llm', true, 5);

    expect(result).toHaveLength(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/search');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual({ query: 'llm', exact_match: true, max_results: 5 });
  });

  it('throws a readable error when the response is not ok', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({}, 500)));
    await expect(searchPapers('llm', true, 5)).rejects.toThrow('Request failed (500).');
  });

  it('enqueuePapers posts the papers', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ queued_count: 1, skipped_count: 0 }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await enqueuePapers([paper()]);

    expect(result).toEqual({ queued_count: 1, skipped_count: 0 });
    expect(fetchMock.mock.calls[0][0]).toBe('/api/jobs/enqueue');
  });

  it('encodes the arXiv id in library URLs', async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse({ arxiv_id: 'cs/0112017', summary_text: null }));
    vi.stubGlobal('fetch', fetchMock);

    await fetchLibraryContent('cs/0112017');

    expect(fetchMock.mock.calls[0][0]).toBe('/api/library/cs%2F0112017/content');
  });

  it('updateListenStatus posts the new status', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ arxiv_id: 'x' }));
    vi.stubGlobal('fetch', fetchMock);

    await updateListenStatus('2301.00001', 'listened');

    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/library/2301.00001/listen');
    expect(JSON.parse(init.body)).toEqual({ listen_status: 'listened' });
  });
});

describe('streamChat', () => {
  const handlers = () => ({
    onToken: vi.fn(),
    onDone: vi.fn(),
    onError: vi.fn()
  });

  it('delivers tokens in order and then completes', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sseResponse([
          'event: token\ndata: {"text":"Hello "}\n\n',
          'event: token\ndata: {"text":"world"}\n\n',
          'event: done\ndata: {}\n\n'
        ])
      )
    );
    const h = handlers();

    await streamChat(['2301.00001'], [{ role: 'user', content: 'hi' }], h);

    expect(h.onToken.mock.calls.map((c) => c[0])).toEqual(['Hello ', 'world']);
    expect(h.onDone).toHaveBeenCalledTimes(1);
    expect(h.onError).not.toHaveBeenCalled();
  });

  it('reassembles an event split across chunks', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sseResponse([
          'event: token\ndata: {"te',
          'xt":"split"}\n\nevent: done\ndata: {}\n\n'
        ])
      )
    );
    const h = handlers();

    await streamChat([], [], h);

    expect(h.onToken).toHaveBeenCalledWith('split');
  });

  it('reports a server error event', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(sseResponse(['event: error\ndata: {"message":"boom"}\n\n']))
    );
    const h = handlers();

    await streamChat([], [], h);

    expect(h.onError).toHaveBeenCalledWith('boom');
    expect(h.onDone).not.toHaveBeenCalled();
  });

  it('reports a failed HTTP response', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('nope', { status: 502 })));
    const h = handlers();

    await streamChat([], [], h);

    expect(h.onError).toHaveBeenCalledWith('Chat request failed (502).');
  });

  it('skips malformed events', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        sseResponse(['event: token\ndata: not-json\n\n', 'event: done\ndata: {}\n\n'])
      )
    );
    const h = handlers();

    await streamChat([], [], h);

    expect(h.onToken).not.toHaveBeenCalled();
    expect(h.onDone).toHaveBeenCalledTimes(1);
  });
});
