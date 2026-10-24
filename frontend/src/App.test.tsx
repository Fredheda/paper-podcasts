import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import App from './App';
import * as api from './api';
import { emptyJobs, libraryItem, paper } from './test/fixtures';

vi.mock('./api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('./api')>();
  return {
    ...actual,
    checkHealth: vi.fn(),
    searchPapers: vi.fn(),
    enqueuePapers: vi.fn(),
    fetchJobs: vi.fn(),
    fetchLibrary: vi.fn(),
    fetchLibraryContent: vi.fn(),
    updateListenStatus: vi.fn(),
    streamChat: vi.fn()
  };
});

// "Search" is both the nav tab and the form's submit button; pick the submit.
function searchSubmitButton(): HTMLElement {
  const button = screen
    .getAllByRole('button', { name: 'Search' })
    .find((candidate) => candidate.getAttribute('type') === 'submit');
  if (!button) throw new Error('Search submit button not found');
  return button;
}

beforeEach(() => {
  vi.mocked(api.checkHealth).mockReset().mockResolvedValue(undefined);
  vi.mocked(api.fetchJobs).mockReset().mockResolvedValue(emptyJobs);
  vi.mocked(api.fetchLibrary).mockReset().mockResolvedValue([]);
  vi.mocked(api.fetchLibraryContent)
    .mockReset()
    .mockResolvedValue({ arxiv_id: 'x', summary_text: null });
  vi.mocked(api.searchPapers).mockReset().mockResolvedValue([]);
  vi.mocked(api.enqueuePapers)
    .mockReset()
    .mockResolvedValue({ queued_count: 1, skipped_count: 0 });
  vi.mocked(api.updateListenStatus).mockReset();
});

describe('App', () => {
  it('shows the backend as online when the health check passes', async () => {
    render(<App />);
    expect(await screen.findByText('Backend online')).toBeInTheDocument();
  });

  it('shows the backend as offline when the health check fails', async () => {
    vi.mocked(api.checkHealth).mockRejectedValue(new Error('down'));
    render(<App />);
    expect(await screen.findByText('Backend offline')).toBeInTheDocument();
  });

  it('searches, selects a result, and queues it', async () => {
    const user = userEvent.setup();
    vi.mocked(api.searchPapers).mockResolvedValue([paper()]);
    render(<App />);

    await user.click(searchSubmitButton());

    expect(api.searchPapers).toHaveBeenCalledWith('large language models', true, 5);
    expect(await screen.findByText('Attention Is Enough')).toBeInTheDocument();
    expect(screen.getByText('Results: 1')).toBeInTheDocument();

    await user.click(screen.getByRole('checkbox', { name: 'Select' }));
    expect(screen.getByText('Selected: 1')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Queue selected papers' }));

    await waitFor(() => expect(api.enqueuePapers).toHaveBeenCalledWith([paper()]));
    expect(await screen.findByText('Queue monitor')).toBeInTheDocument();
  });

  it('shows the search error message', async () => {
    const user = userEvent.setup();
    vi.mocked(api.searchPapers).mockRejectedValue(new Error('Request failed (500).'));
    render(<App />);

    await user.click(searchSubmitButton());

    expect(await screen.findByText('Request failed (500).')).toBeInTheDocument();
  });

  it('switches tabs with the number keys', async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.keyboard('2');
    expect(await screen.findByText('Queue monitor')).toBeInTheDocument();

    await user.keyboard('3');
    expect(await screen.findByLabelText('Processing status')).toBeInTheDocument();

    await user.keyboard('1');
    expect(await screen.findByText('Search papers')).toBeInTheDocument();
  });

  it('filters the library by text', async () => {
    const user = userEvent.setup();
    vi.mocked(api.fetchLibrary).mockResolvedValue([
      libraryItem({ arxiv_id: '2301.00001', title: 'Alpha Paper' }),
      libraryItem({ arxiv_id: '2301.00002', title: 'Beta Paper' })
    ]);
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Library' }));
    expect(await screen.findByText('Alpha Paper')).toBeInTheDocument();
    expect(screen.getByText('Beta Paper')).toBeInTheDocument();

    await user.type(screen.getByPlaceholderText('Filter by title, author, or arXiv ID'), 'alpha');

    expect(screen.getByText('Alpha Paper')).toBeInTheDocument();
    expect(screen.queryByText('Beta Paper')).not.toBeInTheDocument();
    expect(screen.getByText('Showing 1')).toBeInTheDocument();
  });

  it('marks a library paper as listened', async () => {
    const user = userEvent.setup();
    const item = libraryItem({ arxiv_id: '2301.00001', title: 'Alpha Paper' });
    vi.mocked(api.fetchLibrary).mockResolvedValue([item]);
    vi.mocked(api.updateListenStatus).mockResolvedValue({ ...item, listen_status: 'listened' });
    render(<App />);

    await user.click(screen.getByRole('button', { name: 'Library' }));
    await user.click(await screen.findByRole('button', { name: 'Mark Listened' }));

    expect(api.updateListenStatus).toHaveBeenCalledWith('2301.00001', 'listened');
    expect(await screen.findByText('Marked as listened: Alpha Paper')).toBeInTheDocument();
  });
});
