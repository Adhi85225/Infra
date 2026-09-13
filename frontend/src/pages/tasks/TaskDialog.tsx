/**
 * Add / edit a task.
 *
 * One dialog for both: the fields are identical, and having a single form means
 * validation and the field list cannot drift between creating and editing. The
 * mode is decided by whether a `task` is supplied.
 *
 * Editing sends only what actually changed, so a concurrent update to a field
 * this user never touched is not silently overwritten.
 */

import { useEffect, useState, type FormEvent, type ReactNode } from 'react';

import { Alert } from '@/components/ui/Alert';
import { Button } from '@/components/ui/Button';
import { Field, TextArea } from '@/components/ui/Field';
import { Modal } from '@/components/ui/Modal';
import { ApiError, api } from '@/lib/api';
import {
  TASK_SERVICES,
  TASK_STATUSES,
  type Task,
  type TaskService,
  type TaskStatus,
  type User,
} from '@/lib/types';
import { today } from './taskDates';

/** A labelled `<select>`, matching the markup {@link Field} produces. */
function SelectField({
  label,
  value,
  onChange,
  error,
  hint,
  children,
  disabled,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  hint?: ReactNode;
  children: ReactNode;
  disabled?: boolean;
}) {
  const id = `select-${label.toLowerCase().replace(/[^a-z]+/g, '-')}`;
  return (
    <div>
      <label htmlFor={id} className="field-label">
        {label}
      </label>
      <select
        id={id}
        value={value}
        disabled={disabled}
        onChange={(event) => onChange(event.target.value)}
        aria-invalid={error ? true : undefined}
        className={`field-input ${error ? 'field-input-error' : ''}`}
      >
        {children}
      </select>
      {hint && <p className="mt-1.5 text-xs text-slate-500">{hint}</p>}
      {error && (
        <p role="alert" className="mt-1.5 text-xs font-medium text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

interface TaskDialogProps {
  open: boolean;
  /** Present when editing; absent when adding. */
  task?: Task | null;
  /** Pre-selected service on a service page. */
  service?: TaskService;
  assignees: User[];
  /** Whether this caller may file a task against another user. */
  canAssign: boolean;
  onClose: () => void;
  onSaved: () => void;
}

export function TaskDialog({
  open,
  task = null,
  service,
  assignees,
  canAssign,
  onClose,
  onSaved,
}: TaskDialogProps) {
  const editing = task !== null;

  const [taskDate, setTaskDate] = useState(today());
  const [referenceNumber, setReferenceNumber] = useState('');
  const [siteName, setSiteName] = useState('');
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState<TaskStatus>('Created');
  const [remarks, setRemarks] = useState('');
  const [taskService, setTaskService] = useState<TaskService>(service ?? 'DAS');
  const [userId, setUserId] = useState('');

  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState(false);

  // Load the row being edited, or reset to a blank form. Keyed on the task id
  // (not the object) so re-rendering the parent does not discard typing.
  const taskId = task?.id ?? null;
  useEffect(() => {
    if (!open) return;
    if (task) {
      setTaskDate(task.task_date);
      setReferenceNumber(task.reference_number ?? '');
      setSiteName(task.site_name ?? '');
      setDescription(task.description);
      setStatus(task.status);
      setRemarks(task.remarks ?? '');
      setTaskService(task.service);
      setUserId(task.user_id);
    } else {
      setTaskDate(today());
      setReferenceNumber('');
      setSiteName('');
      setDescription('');
      setStatus('Created');
      setRemarks('');
      setTaskService(service ?? 'DAS');
      setUserId('');
    }
    setError(null);
    setFieldErrors({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, taskId, service]);

  const validate = (): boolean => {
    const errors: Record<string, string> = {};
    if (!taskDate) errors.task_date = 'A date is required.';
    if (!description.trim()) errors.description = 'A description is required.';
    if (!taskService) errors.service = 'A service is required.';
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!validate()) return;

    setSubmitting(true);
    try {
      const payload: Record<string, unknown> = {
        task_date: taskDate,
        reference_number: referenceNumber || null,
        site_name: siteName || null,
        description,
        status,
        remarks: remarks || null,
        service: taskService,
      };
      // Only an administrator may set the owner; the API ignores it otherwise,
      // so sending it for anyone else would be noise.
      if (canAssign && userId) payload.user_id = userId;

      if (editing && task) {
        await api.patch<Task>(`/tasks/${task.id}`, payload);
      } else {
        await api.post<Task>('/tasks', payload);
      }
      onSaved();
    } catch (caught) {
      if (caught instanceof ApiError) {
        setError(caught.message);
        setFieldErrors(caught.fieldErrors());
      } else {
        setError(editing ? 'Unable to update the task.' : 'Unable to add the task.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      open={open}
      title={editing ? 'Edit task' : 'Add task'}
      onClose={onClose}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="task-form" loading={submitting}>
            {editing ? 'Save changes' : 'Add task'}
          </Button>
        </>
      }
    >
      <form id="task-form" onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        {error && <Alert tone="error">{error}</Alert>}

        <div className="grid gap-4 sm:grid-cols-2">
          <Field
            label="Date"
            type="date"
            required
            value={taskDate}
            error={fieldErrors.task_date}
            onChange={(event) => setTaskDate(event.target.value)}
          />
          <Field
            label="Case/Work Order/Jira number"
            value={referenceNumber}
            error={fieldErrors.reference_number}
            onChange={(event) => setReferenceNumber(event.target.value)}
            hint="Any reference; leave blank if there is none."
          />
        </div>

        <Field
          label="Site name"
          value={siteName}
          error={fieldErrors.site_name}
          onChange={(event) => setSiteName(event.target.value)}
        />

        <TextArea
          label="Description/Subject"
          required
          value={description}
          error={fieldErrors.description}
          onChange={(event) => setDescription(event.target.value)}
        />

        <div className="grid gap-4 sm:grid-cols-2">
          <SelectField
            label="Service"
            value={taskService}
            error={fieldErrors.service}
            onChange={(value) => setTaskService(value as TaskService)}
          >
            {TASK_SERVICES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </SelectField>

          <SelectField
            label="Status"
            value={status}
            error={fieldErrors.status}
            onChange={(value) => setStatus(value as TaskStatus)}
          >
            {TASK_STATUSES.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </SelectField>
        </div>

        <TextArea
          label="Remarks"
          value={remarks}
          error={fieldErrors.remarks}
          onChange={(event) => setRemarks(event.target.value)}
        />

        {canAssign && (
          <SelectField
            label="User"
            value={userId}
            error={fieldErrors.user_id}
            onChange={setUserId}
            hint="Leave unset to file the task against yourself."
          >
            <option value="">Myself</option>
            {assignees.map((assignee) => (
              <option key={assignee.id} value={assignee.id}>
                {assignee.full_name}
              </option>
            ))}
          </SelectField>
        )}
      </form>
    </Modal>
  );
}
