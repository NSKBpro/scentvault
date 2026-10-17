import { createContext, useContext } from 'react';

export type Kind = 'success' | 'error' | 'info';

export const ToastContext = createContext<(message: string, kind?: Kind) => void>(() => {});

/** Show a toast: `toast('Saved')`, `toast('Failed', 'error')`. */
export const useToast = () => useContext(ToastContext);
