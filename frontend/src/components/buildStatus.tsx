import type { ReactNode } from 'react';
import { CheckCircle2, XCircle, Loader2, CircleDot } from 'lucide-react';
import clsx from 'clsx';
import type { BuildState } from '../types';

const TERMINAL_BUILD_STATES: BuildState[] = [
    'SUCCESS', 'FAILURE', 'ERROR', 'TIMED_OUT',
];

export const NON_TERMINAL_BUILD_STATES: BuildState[] = ['PENDING', 'RUNNING'];

export function isTerminal(state: BuildState): boolean {
    return TERMINAL_BUILD_STATES.includes(state);
}

export function formatAge(ts: number): string {
    const diff = Date.now() / 1000 - ts;
    if (diff < 60) return `${Math.round(diff)}s ago`;
    if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
    return `${Math.round(diff / 86400)}d ago`;
}

export function StateBadge({ state }: { state: BuildState }) {
    const map: Record<BuildState, { cls: string; icon: ReactNode; label: string }> = {
        SUCCESS: { cls: 'badge-green', icon: <CheckCircle2 className="w-3 h-3" />, label: 'Success' },
        FAILURE: { cls: 'badge-red', icon: <XCircle className="w-3 h-3" />, label: 'Failed' },
        ERROR: { cls: 'badge-red', icon: <XCircle className="w-3 h-3" />, label: 'Error' },
        RUNNING: { cls: 'badge-blue', icon: <Loader2 className="w-3 h-3 animate-spin" />, label: 'Running' },
        PENDING: { cls: 'badge-orange', icon: <CircleDot className="w-3 h-3" />, label: 'Pending' },
        TIMED_OUT: { cls: 'badge-red', icon: <XCircle className="w-3 h-3" />, label: 'Timed out' },
    };
    const { cls, icon, label } = map[state] ?? map.FAILURE;
    return (
        <span className={clsx('badge', cls)}>
            {icon}
            {label}
        </span>
    );
}

export function VersionTypeBadge({ type }: { type: string }) {
    const map: Record<string, string> = {
        stable: 'badge-green',
        beta: 'badge-yellow',
        latest: 'badge-blue',
        tag: 'badge-gray',
    };
    return (
        <span className={clsx('badge text-[9px] uppercase tracking-wide', map[type] ?? 'badge-gray')}>
            {type}
        </span>
    );
}
