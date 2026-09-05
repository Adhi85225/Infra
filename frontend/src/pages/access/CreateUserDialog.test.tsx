/**
 * Create User workflow: focus stability, value retention and role selection.
 *
 * These cover the reported bug end-to-end through the real dialog, not just the
 * Modal primitive.
 */

import { useCallback, useState } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ToastProvider } from '@/components/ui/Toast';
import type { Role } from '@/lib/types';
import { CreateUserDialog } from './CreateUserDialog';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return { ...actual, api: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() } };
});

const { api } = await import('@/lib/api');

function role(key: string, name: string): Role {
  return {
    id: `id-${key}`,
    key,
    name,
    description: `${name} role`,
    is_system: true,
    is_superuser: false,
    sort_order: 10,
    user_count: 0,
    is_deletable: false,
  };
}

const ROLES = [role('ADMIN', 'Admin'), role('USER', 'User'), role('GUEST', 'Guest')];

/** Mirrors UsersTab: the dialog lives inside a parent that also re-renders. */
function Harness() {
  const [open, setOpen] = useState(true);
  const [tick, setTick] = useState(0);

  const onClose = useCallback(() => setOpen(false), []);
  const onCreated = useCallback(() => setOpen(false), []);

  return (
    <ToastProvider>
      {/* Simulates an unrelated parent update, e.g. the user list reloading. */}
      <button type="button" onClick={() => setTick((value) => value + 1)}>
        parent update {tick}
      </button>
      <CreateUserDialog open={open} roles={ROLES} onClose={onClose} onCreated={onCreated} />
    </ToastProvider>
  );
}

describe('CreateUserDialog', () => {
  beforeEach(() => {
    vi.mocked(api.post).mockReset();
  });

  it('accepts typed input without losing focus', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const firstName = screen.getByLabelText('First name');
    await user.click(firstName);
    await user.type(firstName, 'Alexandra');

    expect(firstName).toHaveValue('Alexandra');
    expect(firstName).toHaveFocus();
  });

  it('retains values when moving between fields', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('First name'), 'Ada');
    await user.type(screen.getByLabelText('Last name'), 'Lovelace');
    await user.type(screen.getByLabelText('Email address'), 'ada@example.internal');
    await user.type(screen.getByLabelText('Job title'), 'Engineer');

    expect(screen.getByLabelText('First name')).toHaveValue('Ada');
    expect(screen.getByLabelText('Last name')).toHaveValue('Lovelace');
    expect(screen.getByLabelText('Email address')).toHaveValue('ada@example.internal');
    expect(screen.getByLabelText('Job title')).toHaveValue('Engineer');
  });

  it('keeps entered values when roles are selected', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('First name'), 'Ada');
    await user.click(screen.getByRole('checkbox', { name: /Admin/ }));
    await user.click(screen.getByRole('checkbox', { name: /User/ }));

    expect(screen.getByLabelText('First name')).toHaveValue('Ada');
    expect(screen.getByRole('checkbox', { name: /Admin/ })).toBeChecked();
    expect(screen.getByRole('checkbox', { name: /User/ })).toBeChecked();
  });

  it('keeps entered values when the parent re-renders', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('First name'), 'Ada');
    // An unrelated parent update must not disturb the open form.
    await user.click(screen.getByRole('button', { name: /parent update/ }));

    expect(screen.getByLabelText('First name')).toHaveValue('Ada');
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('supports selecting multiple roles and submits them all', async () => {
    vi.mocked(api.post).mockResolvedValue({
      user: {
        id: 'u1',
        email: 'ada@example.internal',
        first_name: 'Ada',
        last_name: 'Lovelace',
        full_name: 'Ada Lovelace',
        status: 'ACTIVE',
        must_change_password: true,
        job_title: null,
        department: null,
        phone: null,
        last_login_at: null,
        created_at: '2026-01-01T00:00:00Z',
        roles: [],
      },
      temporary_password: 'Temp!Password123',
      email_delivered: true,
    });

    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('First name'), 'Ada');
    await user.type(screen.getByLabelText('Last name'), 'Lovelace');
    await user.type(screen.getByLabelText('Email address'), 'ada@example.internal');
    await user.click(screen.getByRole('checkbox', { name: /Admin/ }));
    await user.click(screen.getByRole('checkbox', { name: /User/ }));

    await user.click(screen.getByRole('button', { name: 'Create user' }));

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1));
    const [path, body] = vi.mocked(api.post).mock.calls[0]!;
    expect(path).toBe('/users');
    expect((body as { role_keys: string[] }).role_keys).toEqual(['ADMIN', 'USER']);
  });

  it('shows the temporary password once and stays open until dismissed', async () => {
    vi.mocked(api.post).mockResolvedValue({
      user: {
        id: 'u1',
        email: 'ada@example.internal',
        first_name: 'Ada',
        last_name: 'Lovelace',
        full_name: 'Ada Lovelace',
        status: 'ACTIVE',
        must_change_password: true,
        job_title: null,
        department: null,
        phone: null,
        last_login_at: null,
        created_at: '2026-01-01T00:00:00Z',
        roles: [],
      },
      temporary_password: 'Temp!Password123',
      email_delivered: false,
    });

    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('First name'), 'Ada');
    await user.type(screen.getByLabelText('Last name'), 'Lovelace');
    await user.type(screen.getByLabelText('Email address'), 'ada@example.internal');
    await user.click(screen.getByRole('button', { name: 'Create user' }));

    expect(await screen.findByText('Temp!Password123')).toBeInTheDocument();
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('surfaces a server validation error without clearing the form', async () => {
    const { ApiError } = await import('@/lib/api');
    vi.mocked(api.post).mockRejectedValue(
      new ApiError(409, { code: 'email_taken', message: 'A user with this email already exists.' }),
    );

    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('First name'), 'Ada');
    await user.type(screen.getByLabelText('Last name'), 'Lovelace');
    await user.type(screen.getByLabelText('Email address'), 'ada@example.internal');
    await user.click(screen.getByRole('button', { name: 'Create user' }));

    expect(
      await screen.findByText('A user with this email already exists.'),
    ).toBeInTheDocument();
    // The form must still hold what was typed so it can be corrected.
    expect(screen.getByLabelText('First name')).toHaveValue('Ada');
    expect(screen.getByLabelText('Email address')).toHaveValue('ada@example.internal');
  });

  it('stays open until the user explicitly cancels', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    await user.type(screen.getByLabelText('First name'), 'Ada');
    expect(screen.getByRole('dialog')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Cancel' }));
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
  });
});
