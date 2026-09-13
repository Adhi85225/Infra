/** Types mirroring the API contract. See backend `app/schemas`. */

export type UserStatus = 'ACTIVE' | 'INACTIVE' | 'SUSPENDED';

/** Ordered from least to most privileged. */
export type AccessLevel = 'NONE' | 'GUEST' | 'READ_ONLY' | 'COMPLETE';

export interface Role {
  id: string;
  key: string;
  name: string;
  description: string | null;
  is_system: boolean;
  is_superuser: boolean;
  sort_order: number;
  /** How many users currently hold this role. */
  user_count: number;
  /** False for seeded/system roles, which are protected from deletion. */
  is_deletable: boolean;
}

export interface User {
  id: string;
  email: string;
  first_name: string;
  last_name: string;
  full_name: string;
  status: UserStatus;
  must_change_password: boolean;
  job_title: string | null;
  department: string | null;
  phone: string | null;
  last_login_at: string | null;
  created_at: string;
  roles: Role[];
}

/** One module's resolved access for the signed-in user. */
export interface Permission {
  module_key: string;
  module_name: string;
  icon: string | null;
  route: string;
  description: string | null;
  sort_order: number;
  is_implemented: boolean;
  access_level: AccessLevel;
  can_view: boolean;
  can_manage: boolean;
}

export interface SessionResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  must_change_password: boolean;
  user: User;
  permissions: Permission[];
}

export interface MeResponse {
  user: User;
  permissions: Permission[];
  must_change_password: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ModuleSummary {
  id: string;
  key: string;
  name: string;
  description: string | null;
  icon: string | null;
  route: string;
  sort_order: number;
  is_active: boolean;
  is_core: boolean;
  is_implemented: boolean;
}

export interface RoleWithPermissions extends Role {
  permissions: Record<string, AccessLevel>;
}

export interface PasswordPolicy {
  min_length: number;
  max_length: number;
  require_uppercase: boolean;
  require_lowercase: boolean;
  require_digit: boolean;
  require_symbol: boolean;
  history_depth: number;
}

export interface AuditLogEntry {
  id: string;
  actor_user_id: string | null;
  actor_email: string | null;
  action: string;
  success: boolean;
  entity_type: string | null;
  entity_id: string | null;
  ip_address: string | null;
  context: Record<string, unknown> | null;
  created_at: string;
}

// --- Task updates ----------------------------------------------------------

/**
 * Dropdown D1. The value *is* the label -- the API stores and filters on these
 * exact strings, so they must not be reworded here.
 */
export const TASK_SERVICES = [
  'Access Management',
  'DAS',
  'ILO',
  'Zabbix',
  'Nexus',
  'Patch Management',
] as const;

export type TaskService = (typeof TASK_SERVICES)[number];

/** Dropdown D2. Single-word spellings are deliberate; see D1. */
export const TASK_STATUSES = [
  'Created',
  'Inprogress',
  'Onhold',
  'Completed',
  'Triage',
] as const;

export type TaskStatus = (typeof TASK_STATUSES)[number];

/**
 * What the status filter offers: the real statuses plus one grouping.
 *
 * `Ongoing` is every status except `Completed` — a query over statuses, not one
 * a task can be in, so no row is ever stored with it.
 */
export const ONGOING = 'Ongoing' as const;

export const TASK_STATUS_FILTERS = [...TASK_STATUSES, ONGOING] as const;

export type TaskStatusFilter = (typeof TASK_STATUS_FILTERS)[number];

/**
 * Which **existing** module page shows each service's tasks.
 *
 * Task Updates is a cross-service layer, not a parent of the services: a task
 * tagged `DAS` surfaces on the existing DAS Onboarding page. The names differ
 * because those modules were named before this feature existed.
 *
 * Mirrors `_SERVICE_MODULES` in `app/models/enums.py`; the API also serves the
 * mapping on `/tasks/options` so the two cannot drift. Routes are never
 * hardcoded here — they are looked up from the server's permission map.
 */
export const SERVICE_MODULES: Record<TaskService, string> = {
  'Access Management': 'ACCESS_MANAGEMENT',
  DAS: 'DAS_ONBOARDING',
  ILO: 'ILO_INVENTORY',
  Zabbix: 'ZABBIX',
  Nexus: 'NEXUS',
  'Patch Management': 'SERVERS',
};

/** The service a module page shows tasks for, if it is one of the six. */
export function serviceForModule(moduleKey: string): TaskService | undefined {
  return TASK_SERVICES.find((service) => SERVICE_MODULES[service] === moduleKey);
}

export interface Task {
  id: string;
  task_date: string;
  reference_number: string | null;
  site_name: string | null;
  description: string;
  status: TaskStatus;
  remarks: string | null;
  service: TaskService;
  user_id: string;
  user_name: string;
  user_email: string;
  created_at: string;
  updated_at: string;
  /** Resolved by the API for the signed-in caller. Never re-derived here. */
  can_edit: boolean;
}

export interface TaskOptions {
  services: TaskService[];
  statuses: TaskStatus[];
  /** Service -> the existing module whose page shows its tasks. */
  service_modules: Record<TaskService, string>;
  /** What the status filter accepts: the statuses plus `Ongoing`. */
  status_filters: TaskStatusFilter[];
}

// --- Dashboard analytics ---------------------------------------------------

export interface StatusCount {
  status: TaskStatus;
  count: number;
}

export interface ServiceCount {
  service: TaskService;
  /** The existing module this bar links to. */
  module_key: string;
  count: number;
}

/** Everything the dashboard renders, aggregated server-side in one response. */
export interface TaskAnalytics {
  total: number;
  by_status: StatusCount[];
  by_service: ServiceCount[];
  /**
   * The latest matching rows, narrowed by exactly the same filters as the
   * counts — the panel and the charts always describe the same set.
   */
  recent: Task[];
}
