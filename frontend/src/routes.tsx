/**
 * Routing.
 *
 * Route protection is layered:
 *   1. `RequireAuth`   -- must be signed in.
 *   2. `RequireCurrentPassword` -- redirects to the mandatory change screen.
 *   3. `RequireModule` -- checks the module permission the route belongs to.
 *
 * Module routes are generated from the server's permission map, so adding a
 * module to the backend registry gives it a guarded route automatically.
 */

import { Navigate, Route, Routes, useLocation, useParams } from 'react-router-dom';
import type { ReactNode } from 'react';

import { useAuth } from '@/auth/AuthContext';
import { moduleForRoute } from '@/auth/permissions';
import { Layout } from '@/components/Layout';
import { LoadingState } from '@/components/ui/States';
import { AccessManagementPage } from '@/pages/AccessManagementPage';
import { ChangePasswordPage } from '@/pages/ChangePasswordPage';
import { DashboardPage } from '@/pages/DashboardPage';
import { ForbiddenPage } from '@/pages/ForbiddenPage';
import { ForgotPasswordPage } from '@/pages/ForgotPasswordPage';
import { LoginPage } from '@/pages/LoginPage';
import { ModulePlaceholderPage } from '@/pages/ModulePlaceholderPage';
import { NotFoundPage } from '@/pages/NotFoundPage';
import { ResetPasswordPage } from '@/pages/ResetPasswordPage';
import { SettingsPage } from '@/pages/SettingsPage';
import { ServiceTasksPage } from '@/pages/tasks/ServiceTasksPage';
import { TaskUpdatesPage } from '@/pages/TaskUpdatesPage';

function RequireAuth({ children }: { children: ReactNode }) {
  const { isAuthenticated, initialising } = useAuth();
  const location = useLocation();

  if (initialising) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <LoadingState label="Restoring your session…" />
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

function RequireCurrentPassword({ children }: { children: ReactNode }) {
  const { mustChangePassword } = useAuth();
  // The API blocks every other endpoint in this state; mirror that in the UI.
  if (mustChangePassword) return <Navigate to="/change-password" replace />;
  return <>{children}</>;
}

/** Guards a route using the permission the server resolved for its module. */
function RequireModule({ moduleKey, children }: { moduleKey: string; children: ReactNode }) {
  const { permissionMap } = useAuth();
  const permission = permissionMap[moduleKey];
  if (!permission?.can_view) {
    return <ForbiddenPage moduleName={permission?.module_name} />;
  }
  return <>{children}</>;
}

/** Renders whichever component a module route maps to. */
function ModuleRoute() {
  const { permissions } = useAuth();
  const location = useLocation();
  // Set only on the `/task-updates/:serviceSlug` route below; the service pages
  // share this module's permission rather than declaring one of their own.
  const { serviceSlug } = useParams<{ serviceSlug: string }>();

  const module = moduleForRoute(permissions, location.pathname);
  if (!module) return <NotFoundPage />;

  return (
    <RequireModule moduleKey={module.module_key}>
      {module.module_key === 'ACCESS_MANAGEMENT' ? (
        <AccessManagementPage />
      ) : module.module_key === 'SETTINGS' ? (
        <SettingsPage />
      ) : module.module_key === 'TASK_UPDATES' ? (
        serviceSlug ? (
          <ServiceTasksPage />
        ) : (
          <TaskUpdatesPage />
        )
      ) : (
        <ModulePlaceholderPage />
      )}
    </RequireModule>
  );
}

export function AppRoutes() {
  const { permissions, initialising, isAuthenticated } = useAuth();

  // Every module route except the dashboard, which has its own component.
  const moduleRoutes = permissions
    .filter((permission) => permission.module_key !== 'DASHBOARD')
    .map((permission) => permission.route);

  return (
    <Routes>
      {/* Public */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Mandatory password change: signed in, but outside the app shell. */}
      <Route
        path="/change-password"
        element={
          <RequireAuth>
            <ChangePasswordPage />
          </RequireAuth>
        }
      />

      {/* Authenticated application */}
      <Route
        element={
          <RequireAuth>
            <RequireCurrentPassword>
              <Layout />
            </RequireCurrentPassword>
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/account/password" element={<ChangePasswordPage />} />
        {moduleRoutes.map((route) => (
          <Route key={route} path={route} element={<ModuleRoute />} />
        ))}
        {/* Service views live under the Task Updates module and are guarded by
            its permission -- `moduleForRoute` matches the route prefix. */}
        <Route path="/task-updates/:serviceSlug" element={<ModuleRoute />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route
        path="/"
        element={
          <Navigate to={isAuthenticated || initialising ? '/dashboard' : '/login'} replace />
        }
      />
    </Routes>
  );
}
