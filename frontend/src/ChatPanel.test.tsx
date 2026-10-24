import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { ChatPanel } from './ChatPanel';
import { streamChat } from './api';
import { libraryItem } from './test/fixtures';

vi.mock('./api', () => ({ streamChat: vi.fn() }));

const alpha = libraryItem({ arxiv_id: '2301.00001', title: 'Alpha Paper' });
const beta = libraryItem({ arxiv_id: '2301.00002', title: 'Beta Paper' });

function renderPanel(selected = [alpha], overrides: Partial<Parameters<typeof ChatPanel>[0]> = {}) {
  const props = {
    selectedPapers: selected,
    onClearSelection: vi.fn(),
    onDeselect: vi.fn(),
    ...overrides
  };
  render(<ChatPanel {...props} />);
  return props;
}

beforeEach(() => {
  vi.mocked(streamChat).mockReset();
});

describe('ChatPanel', () => {
  it('asks the user to select papers first and disables input', () => {
    renderPanel([]);
    expect(
      screen.getByText('Select up to 5 completed papers (broken on purpose).')
    ).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Select papers first')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send' })).toBeDisabled();
  });

  it('shows the selected paper count on the launcher and the chips', () => {
    renderPanel([alpha, beta]);
    expect(screen.getByRole('button', { name: 'Open chat' })).toHaveTextContent('Chat (2)');
    expect(screen.getByText('Alpha Paper')).toBeInTheDocument();
    expect(screen.getByText('Beta Paper')).toBeInTheDocument();
  });

  it('removes a paper when its chip is clicked', async () => {
    const user = userEvent.setup();
    const props = renderPanel([alpha, beta]);

    await user.click(screen.getAllByTitle('Remove from chat')[0]);

    expect(props.onDeselect).toHaveBeenCalledTimes(1);
    expect(props.onDeselect).toHaveBeenCalledWith('2301.00001');
  });

  it('clears the selection with the Clear button', async () => {
    const user = userEvent.setup();
    const props = renderPanel();

    await user.click(screen.getByRole('button', { name: 'Clear' }));

    expect(props.onClearSelection).toHaveBeenCalledTimes(1);
  });

  it('streams an answer into the transcript', async () => {
    const user = userEvent.setup();
    vi.mocked(streamChat).mockImplementation(async (_ids, _messages, handlers) => {
      handlers.onToken('Hello ');
      handlers.onToken('there');
      handlers.onDone();
    });
    renderPanel([alpha]);

    await user.type(screen.getByPlaceholderText('Ask a question…'), 'What is this about?');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(streamChat).toHaveBeenCalledTimes(1);
    const [ids, messages] = vi.mocked(streamChat).mock.calls[0];
    expect(ids).toEqual(['2301.00001']);
    expect(messages).toEqual([{ role: 'user', content: 'What is this about?' }]);
    expect(await screen.findByText('What is this about?')).toBeInTheDocument();
    expect(await screen.findByText('Hello there')).toBeInTheDocument();
  });

  it('shows an error and drops the empty assistant bubble', async () => {
    const user = userEvent.setup();
    vi.mocked(streamChat).mockImplementation(async (_ids, _messages, handlers) => {
      handlers.onError('Backend unavailable');
    });
    renderPanel([alpha]);

    await user.type(screen.getByPlaceholderText('Ask a question…'), 'hello');
    await user.click(screen.getByRole('button', { name: 'Send' }));

    expect(await screen.findByText('Backend unavailable')).toBeInTheDocument();
    // Streaming has ended, so the input is usable again and can send a retry.
    const input = screen.getByPlaceholderText('Ask a question…');
    await waitFor(() => expect(input).toBeEnabled());
    await user.type(input, 'retry');
    expect(screen.getByRole('button', { name: 'Send' })).toBeEnabled();
  });

  it('starts a new chat with the New button', async () => {
    const user = userEvent.setup();
    vi.mocked(streamChat).mockImplementation(async (_ids, _messages, handlers) => {
      handlers.onToken('An answer');
      handlers.onDone();
    });
    renderPanel([alpha]);

    await user.type(screen.getByPlaceholderText('Ask a question…'), 'hello');
    await user.click(screen.getByRole('button', { name: 'Send' }));
    await screen.findByText('An answer');
    await user.click(screen.getByRole('button', { name: 'New' }));

    expect(screen.queryByText('An answer')).not.toBeInTheDocument();
  });
});
