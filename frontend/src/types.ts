export type Author = {
  name: string;
  affiliation?: string | null;
};

export type Paper = {
  arxiv_id: string;
  title: string;
  authors: Author[];
  abstract: string;
  published: string;
  updated: string;
  categories: string[];
  primary_category: string;
  pdf_url: string;
  comment?: string | null;
  journal_ref?: string | null;
  doi?: string | null;
};

export type SearchResponse = {
  papers: Paper[];
};

export type EnqueueResponse = {
  queued_count: number;
  skipped_count: number;
};

export type Job = {
  arxiv_id: string;
  title: string;
  stage: string;
  message: string;
  progress: number;
  is_active: boolean;
  queue_position: number | null;
  error: string | null;
  started_at: string | null;
  updated_at: string | null;
  completed_at: string | null;
};

export type JobCounts = {
  queued: number;
  active: number;
  completed: number;
  failed: number;
};

export type JobsResponse = {
  counts: JobCounts;
  jobs: Job[];
};

export type LibraryItem = {
  title: string;
  arxiv_id: string;
  authors: { name?: string }[];
  status: string;
  abstract: string;
  listen_status: string;
  last_listened_at: string | null;
  arxiv_url: string | null;
  audio_url: string | null;
};

export type LibraryContent = {
  arxiv_id: string;
  summary_text: string | null;
  extract_text: string | null;
};
