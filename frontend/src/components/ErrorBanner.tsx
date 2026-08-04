import { AlertTriangle } from 'lucide-react';

export function ErrorBanner({ message }: { message: string | null }) {
    if (!message) return null;
    return (
        <p className="flex items-center gap-1.5 text-xs text-red-400 bg-red-400/10 border border-red-400/20 rounded-lg px-3 py-2">
            <AlertTriangle className="w-3.5 h-3.5 shrink-0" />
            {message}
        </p>
    );
}
