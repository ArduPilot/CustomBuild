import {
    CheckCircle2, XCircle, AlertTriangle,
    Download, Terminal, RotateCcw,
} from 'lucide-react';
import clsx from 'clsx';
import type { Vehicle, Version, Board, BuildState } from '../types';
import { buildArtifactUrl } from '../api';
import type { BuildConfig } from '../buildConfig';

interface DoneStepProps {
    buildState: BuildState;
    buildId: string | null;
    vehicle: Vehicle | null;
    version: Version | null;
    board: Board | null;
    selected: Set<string>;
    onViewLogs: () => void;
    onRebuild: (config: BuildConfig) => void;
}

export function DoneStep({
    buildState, buildId, vehicle, version, board, selected,
    onViewLogs, onRebuild,
}: DoneStepProps) {
    const isSuccess = buildState === 'SUCCESS';
    const isTimeout = buildState === 'TIMED_OUT';
    const icon = isSuccess
        ? <CheckCircle2 className="w-8 h-8 text-emerald-400 shrink-0" />
        : isTimeout
            ? <AlertTriangle className="w-8 h-8 text-orange-400 shrink-0" />
            : <XCircle className="w-8 h-8 text-red-400 shrink-0" />;
    const message = isSuccess ? 'Build complete!' : isTimeout ? 'Build timed out' : 'Build failed';

    function makeConfig(): BuildConfig | null {
        if (!vehicle || !version || !board) return null;
        return {
            config_version: '0.0.1',
            vehicle: { id: vehicle.id, name: vehicle.name },
            version: {
                id: version.id,
                name: version.name,
                type: version.type,
                remote_name: version.remote.name,
            },
            board: { id: board.id, name: board.name },
            selected_features: Array.from(selected),
        };
    }

    return (
        <div className="space-y-5">
            <div className="flex items-center gap-3 py-2">
                {icon}
                <div>
                    <div className="text-white font-semibold text-base">{message}</div>
                    <div className="flex items-center gap-2 flex-wrap mt-1 text-xs">
                        {buildId && (
                            <span className="text-gray-500">Build ID: <span className="font-mono text-yellow-400">{buildId}</span></span>
                        )}
                        {vehicle && (
                            <span className="text-gray-500">Vehicle: <span className="font-mono text-yellow-400">{vehicle.name}</span></span>
                        )}
                        {vehicle && board && <span className="text-gray-700">·</span>}
                        {board && (
                            <span className="text-gray-500">Board: <span className="font-mono text-yellow-400">{board.name}</span></span>
                        )}
                        {board && buildId && <span className="text-gray-700">·</span>}
                    </div>
                </div>
            </div>

            <div className="flex gap-2 pt-1">
                <button
                    onClick={() => { const c = makeConfig(); if (c) onRebuild(c); }}
                    className={clsx(
                        'flex flex-col items-center justify-center gap-1.5 px-3 py-4 rounded-lg border text-xs font-medium transition-all duration-150 min-w-0 flex-1',
                        'border-yellow-400/50 text-yellow-400 bg-transparent',
                        'hover:bg-yellow-400/10 hover:border-yellow-400 hover:shadow-[0_0_10px_rgba(250,204,21,0.15)]',
                    )}
                >
                    <RotateCcw className="w-4 h-4 shrink-0" />
                    <span className="truncate">Rebuild</span>
                </button>

                {isSuccess && (
                    <button
                        onClick={onViewLogs}
                        className={clsx(
                            'flex flex-col items-center justify-center gap-1.5 px-3 py-4 rounded-lg border text-xs font-medium transition-all duration-150 min-w-0 flex-1',
                            'border-yellow-400/50 text-yellow-400 bg-transparent',
                            'hover:bg-yellow-400/10 hover:border-yellow-400 hover:shadow-[0_0_10px_rgba(250,204,21,0.15)]',
                        )}
                    >
                        <Terminal className="w-4 h-4 shrink-0" />
                        <span className="truncate">View Logs</span>
                    </button>
                )}

                {isSuccess ? (
                    <a
                        href={buildArtifactUrl(buildId!)}
                        download
                        className={clsx(
                            'flex flex-col items-center justify-center gap-1.5 px-3 py-4 rounded-lg text-xs font-semibold transition-all duration-150 min-w-0 flex-[2]',
                            'bg-yellow-400 text-black border border-yellow-400',
                            'hover:bg-yellow-300 hover:border-yellow-300 hover:shadow-[0_0_16px_rgba(250,204,21,0.35)]',
                        )}
                    >
                        <Download className="w-4 h-4 shrink-0" />
                        Download Bundle
                    </a>
                ) : (
                    <button
                        onClick={onViewLogs}
                        className={clsx(
                            'flex flex-col items-center justify-center gap-1.5 px-3 py-4 rounded-lg text-xs font-semibold transition-all duration-150 min-w-0 flex-[2]',
                            'bg-yellow-400 text-black border border-yellow-400',
                            'hover:bg-yellow-300 hover:border-yellow-300 hover:shadow-[0_0_16px_rgba(250,204,21,0.35)]',
                        )}
                    >
                        <Terminal className="w-4 h-4 shrink-0" />
                        View Logs
                    </button>
                )}
            </div>
        </div>
    );
}
