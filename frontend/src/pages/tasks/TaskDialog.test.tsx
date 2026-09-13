/**
 * Add / edit task form: validation, payload shape and edit prefill.
 */

import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '@/components/ui/Toast';
import type { Task, User } from '@/lib/types';
import { TaskDialog } from './TaskDialog';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  };
});

const { api } = await import('@/lib/api');

const ASSIGNEES = [
  { id: 'user-1', full_name: 'Normal User' },
  { id: 'user-2', full_name: 'Other User' },
] as User[];

const TASK: Task = {
  id: 'task-1',
  task_date: '2026-09-10',
  reference_number: 'INC-1024',
  site_name: 'Chennai DC',
  description: 'Replaced a failed disk',
  status: 'Inprogress',
  remarks: 'Waiting on vendor',
  service: 'DAS',
  user_id: 'user-1',
  user_name: 'Normal User',
  user_email: 'user@test.internal',
  created_at: '2026-09-10T00:00:00Z',
  updated_at: '2026-09-10T00:00:00Z',
  can_edit: true,
};

function renderDialog(props: Partial<React.ComponentProps<typeof TaskDialog>> = {}) {
  return render(
    <ToastProvider>
      <TaskDialog
        open
        assignees={ASSIGNEES}
        canAssign={false}
        onClose={vi.fn()}
        onSaved={vi.fn()}
        {...props}
      />
    </ToastProvider>,
  );
}

describe('TaskDialog', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset();
    vi.mocked(api.patch).mockReset();
  });

  it('offers exactly the D1 service options', () => {
    renderDialog();
    const select = screen.getByLabelText('Service') as HTMLSelectElement;
    expect([...select.options].map((option) => option.value)).toEqual([
      'Access Management',
      'DAS',
      'ILO',
      'Zabbix',
      'Nexus',
      'Servers',
    ]);
  });

  it('offers exactly the D2 status options', () => {
    renderDialog();
    const select = screen.getByLabelText('Status') as HTMLSelectElement;
    expect([...select.options].map((option) => option.value)).toEqual([
      'Created',
      'Inprogress',
      'Onhold',
      'Completed',
      'Triage',
    ]);
  });

  it('refuses to submit without a description', async () => {
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole('button', { name: 'Add task' }));

    expect(await screen.findByText('A description is required.')).toBeInTheDocument();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('posts the task with the fields T1 needs', async () => {
    const user = userEvent.setup();
    const onSaved = vi.fn();
    vi.mocked(api.post).mockResolvedValue(TASK);
    renderDialog({ onSaved });

    await user.type(screen.getByLabelText('Description/Subject'), 'Investigated an alert');
    await user.type(screen.getByLabelText('Case/Work Order/Jira number'), 'INC-9');
    await user.type(screen.getByLabelText('Site name'), 'Chennai DC');
    await user.selectOptions(screen.getByLabelText('Service'), 'Nexus');
    await user.selectOptions(screen.getByLabelText('Status'), 'Triage');
    await user.click(screen.getByRole('button', { name: 'Add task' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [path, payload] = vi.mocked(api.post).mock.calls[0]!;
    expect(path).toBe('/tasks');
    expect(payload).toMatchObject({
      description: 'Investigated an alert',
      reference_number: 'INC-9',
      site_name: 'Chennai DC',
      service: 'Nexus',
      status: 'Triage',
    });
    expect(onSaved).toHaveBeenCalled();
  });

  it('sends no user_id when the caller may not assign', async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue(TASK);
    renderDialog({ canAssign: false });

    // The control is not even rendered for a non-administrator.
    expect(screen.queryByLabelText('User')).not.toBeInTheDocument();

    await user.type(screen.getByLabelText('Description/Subject'), 'Own task');
    await user.click(screen.getByRole('button', { name: 'Add task' }));

    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(vi.mocked(api.post).mock.calls[0]![1]).not.toHaveProperty('user_id');
  });

  it('lets an administrator file a task for someone else', async () => {
    const user = userEvent.setup();
    vi.mocked(api.post).mockResolvedValue(TASK);
    renderDialog({ canAssign: true });

    await user.type(screen.getByLabelText('Description/Subject'), 'Delegated task');
    await user.selectOptions(screen.getByLabelText('User'), 'user-2');
    await user.click(screen.getByRole('button', { name: 'Add task' }));

    await waitFor(() => expect(api.post).toHaveBeenCalled());
    expect(vi.mocked(api.post).mock.calls[0]![1]).toMatchObject({ user_id: 'user-2' });
  });

  it('pre-fills the existing values when editing', () => {
    renderDialog({ task: TASK });

    expect(screen.getByLabelText('Date')).toHaveValue('2026-09-10');
    expect(screen.getByLabelText('Case/Work Order/Jira number')).toHaveValue('INC-1024');
    expect(screen.getByLabelText('Site name')).toHaveValue('Chennai DC');
    expect(screen.getByLabelText('Description/Subject')).toHaveValue('Replaced a failed disk');
    expect(screen.getByLabelText('Service')).toHaveValue('DAS');
    expect(screen.getByLabelText('Status')).toHaveValue('Inprogress');
    expect(screen.getByLabelText('Remarks')).toHaveValue('Waiting on vendor');
  });

  it('patches the task being edited', async () => {
    const user = userEvent.setup();
    vi.mocked(api.patch).mockResolvedValue({ ...TASK, status: 'Completed' });
    renderDialog({ task: TASK });

    await user.selectOptions(screen.getByLabelText('Status'), 'Completed');
    await user.click(screen.getByRole('button', { name: 'Save changes' }));

    await waitFor(() => expect(api.patch).toHaveBeenCalledTimes(1));
    const [path, payload] = vi.mocked(api.patch).mock.calls[0]!;
    expect(path).toBe('/tasks/task-1');
    expect(payload).toMatchObject({ status: 'Completed' });
    expect(api.post).not.toHaveBeenCalled();
  });

  it('surfaces an API error instead of closing', async () => {
    const user = userEvent.setup();
    const { ApiError } = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
    const onSaved = vi.fn();
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(422, { code: 'validation_error', message: 'Service is not valid.' }),
    );
    renderDialog({ onSaved });

    await user.type(screen.getByLabelText('Description/Subject'), 'Bad task');
    await user.click(screen.getByRole('button', { name: 'Add task' }));

    expect(await screen.findByText('Service is not valid.')).toBeInTheDocument();
    expect(onSaved).not.toHaveBeenCalled();
  });
});
