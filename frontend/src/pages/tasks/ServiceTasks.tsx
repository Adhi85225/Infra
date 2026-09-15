/**
 * The task panel an existing service page embeds.
 *
 * This is not a page and owns no route: DAS Onboarding, ILO Inventory, Zabbix,
 * Nexus, Servers and Access Management each render it from their own existing
 * route. It is T1 with the service fixed and the Action column switched on.
 *
 * The scoping note is presentation only — the API decides which rows come back.
 */

import { canManage, type PermissionMap } from '@/auth/permissions';
import { Alert } from '@/components/ui/Alert';
import type { TaskService } from '@/lib/types';
import { TaskTable } from './TaskTable';

export function ServiceTasks({
  service,
  permissionMap,
}: {
  service: TaskService;
  permissionMap: PermissionMap;
}) {
  // Mirrors the API rule: a task administrator holds MANAGE on Access Management.
  const isTaskAdmin = canManage(permissionMap, 'ACCESS_MANAGEMENT');

  return (
    <div>
      {!isTaskAdmin && (
        <div className="mb-4">
          <Alert tone="info">
            These are your own {service} tasks. Task Updates lists everyone's.
          </Alert>
        </div>
      )}

      <TaskTable service={service} permissionMap={permissionMap} />
    </div>
  );
}
