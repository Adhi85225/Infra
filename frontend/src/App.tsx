import { BrowserRouter } from 'react-router-dom';

import { AuthProvider } from '@/auth/AuthContext';
import { ToastProvider } from '@/components/ui/Toast';
import { AppRoutes } from '@/routes';

export function App() {
  return (
    <BrowserRouter>
      <ToastProvider>
        <AuthProvider>
          <AppRoutes />
        </AuthProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
