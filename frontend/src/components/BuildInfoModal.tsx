import { useEffect, useRef, useState } from 'react';
import {
    X, Download, Terminal, Info, Package, Loader2, Clock,
} from 'lucide-react';
import clsx from 'clsx';
import type { Build, BuildState } from '../types';
import { fetchBuild, fetchBuildLogs, buildArtifactUrl, commitUrl } from '../api';
import { ModalShell } from './ModalShell';
import { StateBadge, VersionTypeBadge, formatAge, isTerminal } from './buildStatus';

function colorize(line: string) {
    if (line.startsWith('[SUCCESS]')) return 'text-emerald-400';
    if (line.startsWith('[ERROR]') || line.startsWith('[FAIL]')) return 'text-red-400';
    if (line.startsWith('[WARN]')) return 'text-orange-400';
    if (line.startsWith('[INFO]')) return 'text-blue-400';
    return 'text-gray-400';
}

type Tab = 'details' | 'logs';

interface BuildInfoModalProps {
    buildId: string;
    initialTab?: Tab;
    initialFeaturesExpanded?: boolean;
    onClose: () => void;
}

export function BuildInfoModal({ buildId, initialTab = 'details', initialFeaturesExpanded = false, onClose }: BuildInfoModalProps) {
    const [tab, setTab] = useState<Tab>(initialTab);
    const [build, setBuild] = useState<Build | null>(null);
    const [loadingBuild, setLoadingBuild] = useState(true);
    const [logs, setLogs] = useState('');
    const [logsLoading, setLogsLoading] = useState(false);
    const [logsError, setLogsError] = useState<string | null>(null);

    const pollRef = useRef<ReturnType<typeof setTimeout>>();
    const logPollRef = useRef<ReturnType<typeof setTimeout>>();
    const buildStateRef = useRef<BuildState | undefined>();

    useEffect(() => {
        buildStateRef.current = build?.progress.state;
    }, [build?.progress.state]);

    useEffect(() => {
        let alive = true;
        setLoadingBuild(true);
        setBuild(null);

        const clearPoll = () => {
            clearTimeout(pollRef.current);
            pollRef.current = undefined;
        };

        const schedulePoll = () => {
            clearPoll();
            pollRef.current = setTimeout(async () => {
                if (!alive) return;
                try {
                    const updated = await fetchBuild(buildId);
                    if (!alive) return;
                    setBuild(updated);
                    if (isTerminal(updated.progress.state)) {
                        clearPoll();
                        return;
                    }
                } catch { /* ignore */ }
                if (alive) schedulePoll();
            }, 2000);
        };

        async function load() {
            try {
                const b = await fetchBuild(buildId);
                if (!alive) return;
                setBuild(b);
                setLoadingBuild(false);
                if (!isTerminal(b.progress.state)) schedulePoll();
            } catch {
                if (alive) setLoadingBuild(false);
            }
        }

        load();
        return () => {
            alive = false;
            clearPoll();
        };
    }, [buildId]);

    // Logs fetching / polling — serialized self-scheduling
    useEffect(() => {
        if (tab !== 'logs') {
            clearTimeout(logPollRef.current);
            logPollRef.current = undefined;
            return;
        }

        let alive = true;
        setLogsError(null);

        const clearLogPoll = () => {
            clearTimeout(logPollRef.current);
            logPollRef.current = undefined;
        };

        const scheduleLogPoll = () => {
            clearLogPoll();
            const state = buildStateRef.current;
            if (state && isTerminal(state)) return;
            logPollRef.current = setTimeout(runLogFetch, 3000);
        };

        async function runLogFetch() {
            if (!alive) return;
            setLogsLoading(true);
            try {
                const l = await fetchBuildLogs(buildId);
                if (!alive) return;
                setLogs(l);
                setLogsError(null);
            } catch {
                if (!alive) return;
                setLogsError('Failed to refresh logs');
            } finally {
                if (alive) setLogsLoading(false);
            }
            if (alive) scheduleLogPoll();
        }

        runLogFetch();
        return () => {
            alive = false;
            clearLogPoll();
        };
    }, [tab, buildId]);

    useEffect(() => {
        const state = build?.progress.state;
        if (state && isTerminal(state)) {
            clearTimeout(logPollRef.current);
            logPollRef.current = undefined;
        }
    }, [build?.progress.state]);

    const state = build?.progress.state ?? 'PENDING';
    const terminal = isTerminal(state);

    return (
        <ModalShell
            onClose={onClose}
            ariaLabelledBy="build-info-modal-title"
            panelClassName="w-full max-w-2xl max-h-[88vh] bg-surface-1 border border-surface-4 rounded-2xl shadow-yellow-lg"
            backdropStyle={{ background: 'rgba(0,0,0,0.75)', backdropFilter: 'blur(4px)' }}
        >
                <div className="flex items-center justify-between px-5 py-4 border-b border-surface-4 shrink-0">
                    <div className="flex items-center gap-3 min-w-0">
                        <Package className="w-4 h-4 text-yellow-400 shrink-0" />
                        <h2 id="build-info-modal-title" className="text-lg font-semibold text-white shrink-0">Build Info</h2>
                        <span className="font-mono text-xs text-gray-500 truncate">{buildId}</span>
                        {build && <StateBadge state={build.progress.state} />}
                    </div>
                    <button onClick={onClose} className="btn-ghost p-2 shrink-0" aria-label="Close">
                        <X className="w-4 h-4" />
                    </button>
                </div>

                <div className="flex border-b border-surface-4 shrink-0 bg-surface-2/40">
                    <TabButton active={tab === 'details'} onClick={() => setTab('details')}>
                        <Info className="w-3.5 h-3.5" />
                        Details
                    </TabButton>
                    <TabButton active={tab === 'logs'} onClick={() => setTab('logs')}>
                        <Terminal className="w-3.5 h-3.5" />
                        Logs
                        {!terminal && build && (
                            <span className="ml-1.5 w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse inline-block" />
                        )}
                    </TabButton>
                </div>

                <div className="flex-1 overflow-y-auto">
                    {loadingBuild ? (
                        <div className="flex items-center justify-center py-16 text-gray-500">
                            <Loader2 className="w-5 h-5 animate-spin mr-2" />
                            Loading…
                        </div>
                    ) : tab === 'details' ? (
                        <DetailsPane build={build} initialFeaturesExpanded={initialFeaturesExpanded} />
                    ) : (
                        <LogsPane logs={logs} loading={logsLoading} error={logsError} />
                    )}
                </div>

                <div className="flex items-center justify-between px-5 py-3 border-t border-surface-4 shrink-0 bg-surface-2/30">
                    {!terminal && build ? (
                        <div className="flex-1 flex items-center gap-3 mr-4">
                            <div className="flex-1 h-1.5 bg-surface-4 rounded-full overflow-hidden">
                                <div
                                    className="h-full rounded-full transition-all duration-700 bg-gradient-to-r from-yellow-500 to-yellow-300"
                                    style={{ width: `${build.progress.percent}%` }}
                                />
                            </div>
                            <span className="text-xs font-mono shrink-0 transition-colors duration-700 text-yellow-400">
                                {build.progress.percent}%
                            </span>
                        </div>
                    ) : (
                        <div />
                    )}

                    <div className="flex items-center gap-2">
                        <a
                            href={terminal ? buildArtifactUrl(buildId) : undefined}
                            download={terminal}
                            aria-disabled={!terminal}
                            className={terminal ? 'btn-primary text-sm py-2' : 'btn-primary text-sm py-2 opacity-40 pointer-events-none'}
                        >
                            <Download className="w-3.5 h-3.5" />
                            Download Artifacts
                        </a>
                        <button onClick={onClose} className="btn-secondary text-sm py-2">
                            Close
                        </button>
                    </div>
                </div>
        </ModalShell>
    );
}

function TabButton({ active, onClick, children }: {
    active: boolean;
    onClick: () => void;
    children: React.ReactNode;
}) {
    return (
        <button
            onClick={onClick}
            className={clsx(
                'flex items-center gap-1.5 px-5 py-3 text-xs font-medium border-b-2 transition-colors',
                active
                    ? 'border-yellow-400 text-yellow-400'
                    : 'border-transparent text-gray-500 hover:text-gray-300',
            )}
        >
            {children}
        </button>
    );
}

function FeaturesList({ features, initialExpanded = false }: { features: string[]; initialExpanded?: boolean }) {
    const [showAll, setShowAll] = useState(initialExpanded);
    const CAP = 20;
    const visible = showAll ? features : features.slice(0, CAP);
    const overflow = features.length - CAP;
    return (
        <div className="pt-3">
            <p className="text-xs text-gray-500 mb-2">Selected features</p>
            <div className="flex flex-wrap gap-1.5">
                {visible.map(f => (
                    <span key={f} className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-3 border border-surface-4 text-gray-400">
                        {f}
                    </span>
                ))}
                {!showAll && overflow > 0 && (
                    <button
                        onClick={() => setShowAll(true)}
                        className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-yellow-400/15 border border-yellow-400/40 text-yellow-400 hover:bg-yellow-400/25 transition-colors"
                    >
                        +{overflow} more
                    </button>
                )}
                {showAll && overflow > 0 && (
                    <button
                        onClick={() => setShowAll(false)}
                        className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-surface-3 border border-surface-4 text-gray-500 hover:text-gray-300 transition-colors"
                    >
                        Show less
                    </button>
                )}
            </div>
        </div>
    );
}

function DetailsPane({ build, initialFeaturesExpanded }: { build: Build | null; initialFeaturesExpanded?: boolean }) {
    if (!build) return <p className="text-sm text-gray-500 text-center py-10">No data</p>;

    const rows: [string, React.ReactNode][] = [
        ['Vehicle',  build.vehicle.name],
        ['Board',    build.board.name],
        ['Version',  (
            <span className="flex items-center gap-1.5 flex-wrap">
                <span className="font-mono text-gray-300">{build.version.name ?? build.version.id}</span>
                {build.version.type && <VersionTypeBadge type={build.version.type} />}
            </span>
        )],
        ['Git hash', (
            <a
                href={commitUrl(build.version.remote_info.url, build.version.git_hash)}
                target="_blank" rel="noopener noreferrer"
                className="font-mono text-yellow-400 hover:underline"
            >
                {build.version.git_hash.substring(0, 8)}
            </a>
        )],
        ['Created',  <span className="flex items-center gap-1.5"><Clock className="w-3 h-3" />{formatAge(build.time_created)}</span>],
        ['Progress', `${build.progress.percent}%`],
        ['Features', build.selected_features.length === 0
            ? <span className="badge-gray badge text-[10px]">none</span>
            : <span className="badge-yellow badge text-[10px]">{build.selected_features.length} selected</span>
        ],
    ];

    return (
        <div className="px-5 py-4 space-y-1">
            {rows.map(([label, value]) => (
                <div key={label} className="flex items-start gap-4 py-2.5 border-b border-surface-4 last:border-0">
                    <span className="text-xs text-gray-500 w-24 shrink-0 pt-px">{label}</span>
                    <span className="text-sm text-gray-200 flex items-center gap-1 flex-wrap">{value}</span>
                </div>
            ))}

            {build.selected_features.length > 0 && (
                <FeaturesList features={build.selected_features} initialExpanded={initialFeaturesExpanded} />
            )}
        </div>
    );
}

function LogsPane({ logs, loading, error }: {
    logs: string;
    loading: boolean;
    error: string | null;
}) {
    const containerRef = useRef<HTMLDivElement>(null);
    const [autoScroll, setAutoScroll] = useState(true);
    const autoScrollRef = useRef(true);

    const NEAR_BOTTOM = 120;
    const MAX_LINES = 2000;

    const allLines = logs ? logs.split('\n') : [];
    const omitted = Math.max(0, allLines.length - MAX_LINES);
    const lines = omitted > 0 ? allLines.slice(-MAX_LINES) : allLines;

    const scrollToBottom = () => {
        const el = containerRef.current;
        if (!el) return;
        el.scrollTop = el.scrollHeight;
        autoScrollRef.current = true;
        setAutoScroll(true);
    };

    const handleScroll = () => {
        const el = containerRef.current;
        if (!el) return;
        const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < NEAR_BOTTOM;
        if (autoScrollRef.current !== atBottom) {
            autoScrollRef.current = atBottom;
            setAutoScroll(atBottom);
        }
    };

    useEffect(() => {
        const el = containerRef.current;
        if (!el || !autoScrollRef.current) return;
        el.scrollTop = el.scrollHeight;
    }, [logs]);

    return (
        <div className="relative h-full min-h-[300px]">
            {error && (
                <div className="absolute top-2 left-2 right-2 z-10 text-[10px] font-mono text-red-300 bg-red-950/80 border border-red-500/30 rounded px-2 py-1">
                    {error}
                </div>
            )}
            <div
                ref={containerRef}
                onScroll={handleScroll}
                className="h-full bg-surface p-4 font-mono text-xs leading-relaxed overflow-y-auto overflow-x-hidden min-h-[300px] max-h-[calc(88vh-12rem)]"
            >
                {loading && !logs ? (
                    <div className="flex items-center gap-2 text-gray-500">
                        <span className="w-2 h-2 rounded-full bg-yellow-400 animate-pulse" />
                        Fetching logs…
                    </div>
                ) : (
                    <>
                        {omitted > 0 && (
                            <div className="text-gray-600 mb-2">
                                … {omitted.toLocaleString()} earlier lines omitted
                            </div>
                        )}
                        {lines.map((line, i) => (
                            <div key={i + omitted} className={clsx('break-all', colorize(line))}>{line || <br />}</div>
                        ))}
                    </>
                )}
            </div>
            {!autoScroll && (
                <button
                    onClick={scrollToBottom}
                    className="absolute bottom-4 right-4 flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-yellow-400/15 border border-yellow-400/40 text-yellow-400 text-[10px] font-mono hover:bg-yellow-400/25 transition-colors shadow-lg"
                >
                    ↓ scroll to bottom
                </button>
            )}
        </div>
    );
}
