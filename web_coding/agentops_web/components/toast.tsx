'use client';
import { createContext, useContext, useEffect, useState } from 'react';
import { CheckCircle2, CircleAlert, X } from 'lucide-react';
const ToastContext = createContext<(message: string, error?: boolean) => void>(() => {});
export const useToast = () => useContext(ToastContext);
export function ToastProvider({ children }: { children: React.ReactNode }) {
  const [notice, setNotice] = useState<{ message: string; error: boolean; id: number } | null>(null);
  useEffect(() => {
    if (!notice) return;
    const timer = window.setTimeout(() => setNotice(null), 5000);
    return () => clearTimeout(timer);
  }, [notice]);
  return <ToastContext.Provider value={(message, error = false) => setNotice({ message, error, id: Date.now() })}>
    {children}<div className="toast-region" aria-live="polite" aria-atomic="true">{notice && <div className={`app-toast ${notice.error ? 'error' : ''}`}>
      {notice.error ? <CircleAlert size={18} /> : <CheckCircle2 size={18} />}<span>{notice.message}</span><button aria-label="关闭提示" onClick={() => setNotice(null)}><X size={16} /></button>
    </div>}</div>
  </ToastContext.Provider>;
}
