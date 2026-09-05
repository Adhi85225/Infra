/**
 * Regression tests for the Create User focus bug.
 *
 * Reported symptom: typing in a field, or clicking a control, silently moves
 * focus off the input.
 *
 * Root cause under test: <Modal>'s "focus the panel on open" effect listed
 * `onClose` in its dependency array. Callers pass an inline arrow function, so
 * `onClose` has a new identity on every parent render -- and the dialog's own
 * state updates re-render the parent of that arrow on every keystroke. The
 * effect therefore re-ran constantly and called panel.focus(), stealing focus
 * from whatever the user was typing into.
 */

import { useState } from 'react';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { Modal } from './Modal';

/** Mirrors how the real dialogs use Modal: inline arrow + local form state. */
function Harness() {
  const [open, setOpen] = useState(true);
  const [name, setName] = useState('');
  const [roles, setRoles] = useState<string[]>([]);

  return (
    <Modal
      open={open}
      title="Create user"
      // Deliberately a fresh function identity on every render.
      onClose={() => setOpen(false)}
      footer={<button type="button">Create user</button>}
    >
      <input
        aria-label="First name"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <label>
        <input
          type="checkbox"
          checked={roles.includes('ADMIN')}
          onChange={() =>
            setRoles((current) =>
              current.includes('ADMIN')
                ? current.filter((role) => role !== 'ADMIN')
                : [...current, 'ADMIN'],
            )
          }
        />
        Admin
      </label>
    </Modal>
  );
}

describe('Modal focus stability', () => {
  it('keeps focus in the input while typing', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const input = screen.getByLabelText('First name');
    await user.click(input);
    expect(input).toHaveFocus();

    await user.type(input, 'Alexandra');

    // The whole value must land, and focus must not have been stolen.
    expect(input).toHaveValue('Alexandra');
    expect(input).toHaveFocus();
  });

  it('does not steal focus when an unrelated control changes state', async () => {
    const user = userEvent.setup();
    render(<Harness />);

    const input = screen.getByLabelText('First name');
    await user.type(input, 'Alex');

    // Selecting a role re-renders the dialog; the typed value must survive.
    await user.click(screen.getByLabelText('Admin'));
    expect(input).toHaveValue('Alex');

    // Returning to the field and continuing to type must work normally.
    await user.click(input);
    await user.type(input, 'andra');
    expect(input).toHaveValue('Alexandra');
    expect(input).toHaveFocus();
  });

  it('moves focus into the dialog when it first opens', async () => {
    render(<Harness />);
    // Accessibility requirement: keyboard users must not be left behind the
    // dialog. Focus should be inside it on open.
    const dialog = screen.getByRole('dialog');
    expect(dialog.contains(document.activeElement)).toBe(true);
  });
});
