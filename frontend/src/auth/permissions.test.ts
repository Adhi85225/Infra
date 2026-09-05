/**
 * Client-side permission helpers.
 *
 * These mirror the server's rules for rendering only. Each assertion here has a
 * server-side counterpart in the Python suite -- the UI must agree with the
 * API, but the API is what enforces.
 */

import { describe, expect, it } from 'vitest';

import type { Permission } from '@/lib/types';
import {
  ASSIGNABLE_ACCESS_LEVELS,
  accessibleModules,
  accessLevel,
  atLeast,
  can,
  canManage,
  canView,
  moduleForRoute,
  toPermissionMap,
} from './permissions';

function permission(
  moduleKey: string,
  level: Permission['access_level'],
  sortOrder = 10,
): Permission {
  const canViewIt = level !== 'NONE';
  return {
    module_key: moduleKey,
    module_name: moduleKey,
    icon: null,
    route: `/${moduleKey.toLowerCase().replace(/_/g, '-')}`,
    description: null,
    sort_order: sortOrder,
    is_implemented: false,
    access_level: level,
    can_view: canViewIt,
    can_manage: level === 'COMPLETE',
  };
}

const PERMISSIONS: Permission[] = [
  permission('DASHBOARD', 'COMPLETE', 10),
  permission('ASSET_INVENTORY', 'COMPLETE', 40),
  permission('ZABBIX', 'READ_ONLY', 70),
  permission('NEXUS', 'NONE', 80),
  permission('CLOUD_INFORMATION', 'NONE', 90),
  permission('REPORTS', 'READ_ONLY', 110),
];

describe('accessLevel', () => {
  it('reads the level from the map', () => {
    const map = toPermissionMap(PERMISSIONS);
    expect(accessLevel(map, 'ASSET_INVENTORY')).toBe('COMPLETE');
    expect(accessLevel(map, 'ZABBIX')).toBe('READ_ONLY');
  });

  it('treats an unknown module as no access', () => {
    expect(accessLevel(toPermissionMap(PERMISSIONS), 'NOT_A_MODULE')).toBe('NONE');
  });
});

describe('can', () => {
  const map = toPermissionMap(PERMISSIONS);

  it('allows every action at COMPLETE', () => {
    for (const action of ['VIEW', 'CREATE', 'UPDATE', 'DELETE', 'MANAGE'] as const) {
      expect(can(map, 'ASSET_INVENTORY', action)).toBe(true);
    }
  });

  it('allows only VIEW at READ_ONLY', () => {
    expect(can(map, 'ZABBIX', 'VIEW')).toBe(true);
    expect(can(map, 'ZABBIX', 'CREATE')).toBe(false);
    expect(can(map, 'ZABBIX', 'UPDATE')).toBe(false);
    expect(can(map, 'ZABBIX', 'DELETE')).toBe(false);
  });

  it('allows nothing at NONE', () => {
    expect(can(map, 'NEXUS', 'VIEW')).toBe(false);
    expect(can(map, 'NEXUS', 'UPDATE')).toBe(false);
  });

  it('exposes the common shorthands', () => {
    expect(canView(map, 'ZABBIX')).toBe(true);
    expect(canManage(map, 'ZABBIX')).toBe(false);
    expect(canManage(map, 'ASSET_INVENTORY')).toBe(true);
  });
});

describe('atLeast', () => {
  const map = toPermissionMap(PERMISSIONS);

  it('compares levels by rank', () => {
    expect(atLeast(map, 'ASSET_INVENTORY', 'READ_ONLY')).toBe(true);
    expect(atLeast(map, 'ZABBIX', 'COMPLETE')).toBe(false);
    expect(atLeast(map, 'NEXUS', 'READ_ONLY')).toBe(false);
  });
});

describe('accessibleModules', () => {
  it('returns only modules the user may open', () => {
    expect(accessibleModules(PERMISSIONS).map((p) => p.module_key)).toEqual([
      'DASHBOARD',
      'ASSET_INVENTORY',
      'ZABBIX',
      'REPORTS',
    ]);
  });

  it('excludes every module with no access', () => {
    const keys = accessibleModules(PERMISSIONS).map((p) => p.module_key);
    expect(keys).not.toContain('NEXUS');
    expect(keys).not.toContain('CLOUD_INFORMATION');
  });

  it('orders by sort_order', () => {
    const shuffled = [...PERMISSIONS].reverse();
    expect(accessibleModules(shuffled).map((p) => p.sort_order)).toEqual([10, 40, 70, 110]);
  });

  it('returns nothing when the user has no access at all', () => {
    const none = PERMISSIONS.map((p) => permission(p.module_key, 'NONE'));
    expect(accessibleModules(none)).toEqual([]);
  });
});

describe('moduleForRoute', () => {
  it('matches an exact route', () => {
    expect(moduleForRoute(PERMISSIONS, '/zabbix')?.module_key).toBe('ZABBIX');
  });

  it('matches a nested route', () => {
    expect(moduleForRoute(PERMISSIONS, '/zabbix/hosts/42')?.module_key).toBe('ZABBIX');
  });

  it('returns undefined for an unknown route', () => {
    expect(moduleForRoute(PERMISSIONS, '/nothing-here')).toBeUndefined();
  });
});

describe('assignable access levels', () => {
  it('offers exactly No access / Read only / Complete', () => {
    // GUEST is legacy: guest access is an ordinary READ_ONLY grant now.
    expect(ASSIGNABLE_ACCESS_LEVELS).toEqual(['NONE', 'READ_ONLY', 'COMPLETE']);
  });
});
