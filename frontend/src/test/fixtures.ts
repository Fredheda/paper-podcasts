import type { JobsResponse, LibraryItem, Paper } from '../types';

export const paper = (overrides: Partial<Paper> = {}): Paper => ({
  arxiv_id: '2301.00001',
  title: 'Attention Is Enough',
  authors: [{ name: 'Ada Lovelace' }],
  abstract: 'A short abstract about attention.',
  published: '2023-01-01T00:00:00',
  updated: '2023-01-01T00:00:00',
  categories: ['cs.AI'],
  primary_category: 'cs.AI',
  pdf_url: 'https://arxiv.org/pdf/2301.00001',
  ...overrides
});

export const libraryItem = (overrides: Partial<LibraryItem> = {}): LibraryItem => ({
  title: 'Alpha Paper',
  arxiv_id: '2301.00001',
  authors: [{ name: 'Ada Lovelace' }],
  status: 'completed',
  listen_status: 'unlistened',
  last_listened_at: null,
  arxiv_url: 'https://arxiv.org/abs/2301.00001',
  audio_url: null,
  ...overrides
});

export const emptyJobs: JobsResponse = {
  counts: { queued: 0, active: 0, completed: 0, failed: 0 },
  jobs: []
};
