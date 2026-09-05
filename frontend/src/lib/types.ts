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
