import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

type Tone = 'success' | 'error' | 'info';

interface Toast {
  id: number;
  tone: Tone;
  message: string;
}

interface ToastApi {
  notify: (message: string, tone?: Tone) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const TONES: Record<Tone, string> = {
  success: 'bg-emerald-600',
  error: 'bg-red-600',
  info: 'bg-slate-800',
};

let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const notify = useCallback((message: string, tone: Tone = 'info') => {
    const id = nextId++;
    setToasts((current) => [...current, { id, tone, message }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((toast) => toast.id !== id));
    }, 5000);
  }, []);

  const value = useMemo(() => ({ notify }), [notify]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      {/* aria-live so screen readers announce results without stealing focus */}
      <div
        aria-live="polite"
        aria-atomic="false"
        className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-full max-w-sm flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            className={`pointer-events-auto rounded-md px-4 py-3 text-sm font-medium
                        text-white shadow-lg ${TONES[toast.tone]}`}
          >
            {toast.message}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (context === null) throw new Error('useToast must be used inside a <ToastProvider>');
  return context;
}
