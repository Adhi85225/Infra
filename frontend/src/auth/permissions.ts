/**
 * Client-side view of the authorization model.
 *
 * These helpers exist so components never compare access levels by hand.
 * They are a **rendering aid only** -- every rule here is also enforced by the
 * API, and hiding a control is never the security boundary.
 */

import type { AccessLevel, Permission } from '@/lib/types';

export type ModuleAction = 'VIEW' | 'CREATE' | 'UPDATE' | 'DELETE' | 'MANAGE';

const RANK: Record<AccessLevel, number> = {
  NONE: 0,
  GUEST: 1,
  READ_ONLY: 2,
  COMPLETE: 3,
};

/** Mirrors `app/models/enums.py::_ALLOWED_ACTIONS`. */
const ALLOWED: Record<AccessLevel, ReadonlySet<ModuleAction>> = {
  NONE: new Set(),
  GUEST: new Set(['VIEW']),
  READ_ONLY: new Set(['VIEW']),
  COMPLETE: new Set(['VIEW', 'CREATE', 'UPDATE', 'DELETE', 'MANAGE']),
};

export type PermissionMap = Record<string, Permission>;

export function toPermissionMap(permissions: Permission[]): PermissionMap {
  return Object.fromEntries(permissions.map((permission) => [permission.module_key, permission]));
}

export function accessLevel(map: PermissionMap, moduleKey: string): AccessLevel {
  return map[moduleKey]?.access_level ?? 'NONE';
}

export function can(map: PermissionMap, moduleKey: string, action: ModuleAction): boolean {
  return ALLOWED[accessLevel(map, moduleKey)].has(action);
}

export function canView(map: PermissionMap, moduleKey: string): boolean {
  return can(map, moduleKey, 'VIEW');
}

export function canManage(map: PermissionMap, moduleKey: string): boolean {
  return can(map, moduleKey, 'MANAGE');
}

export function atLeast(map: PermissionMap, moduleKey: string, level: AccessLevel): boolean {
  return RANK[accessLevel(map, moduleKey)] >= RANK[level];
}

/** Modules ordered for navigation. */
export function orderedModules(permissions: Permission[]): Permission[] {
  return [...permissions].sort((a, b) => a.sort_order - b.sort_order);
}

/**
 * Modules the user may actually open, in display order.
 *
 * The single helper behind both the dashboard grid and the sidebar, so the two
 * can never disagree about what a user can see.
 */
export function accessibleModules(permissions: Permission[]): Permission[] {
  return orderedModules(permissions).filter((permission) => permission.can_view);
}

/** Find the module owning a route, so a page can name its own permission. */
export function moduleForRoute(permissions: Permission[], pathname: string): Permission | undefined {
  return permissions.find(
    (permission) => pathname === permission.route || pathname.startsWith(`${permission.route}/`),
  );
}

export const ACCESS_LABELS: Record<AccessLevel, string> = {
  NONE: 'No access',
  GUEST: 'Guest (legacy)',
  READ_ONLY: 'Read only',
  COMPLETE: 'Complete',
};

/**
 * Levels an administrator may assign to a role.
 *
 * `GUEST` is deliberately absent: guest access is expressed through an ordinary
 * READ_ONLY grant on the Guest role rather than a distinct level. The value
 * still exists in {@link AccessLevel} so rows written before that change keep
 * rendering correctly.
 */
export const ASSIGNABLE_ACCESS_LEVELS: AccessLevel[] = ['NONE', 'READ_ONLY', 'COMPLETE'];

/** All levels, including the legacy one, for display purposes. */
export const ACCESS_LEVELS: AccessLevel[] = ['NONE', 'GUEST', 'READ_ONLY', 'COMPLETE'];
