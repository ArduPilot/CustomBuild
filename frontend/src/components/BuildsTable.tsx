import { useState, useEffect, useRef } from 'react';
import {
    ChevronLeft, ChevronRight,
    Clock, RotateCcw, Info, Download, Loader2,
} from 'lucide-react';
import clsx from 'clsx';
import type { Build } from '../types';
import { fetchBuilds, commitUrl, buildArtifactUrl, fetchBuildConfig } from '../api';
import { BuildInfoModal } from './BuildInfoModal';
import type { BuildConfig } from '../buildConfig';
import { Tooltip } from './Tooltip';
import {
    NON_TERMINAL_BUILD_STATES,
    isTerminal,
    StateBadge,
    VersionTypeBadge,
    formatAge,
} from './buildStatus';

const PAGE_SIZE = 5;
const POLL_INTERVAL_MS = 4000;

// Fixed tracks so header/rows share identical widths. Actions must fit 3 icon buttons
// (~26px each + gaps); too-narrow tracks overflow and look like header/row drift.
const COLS = 'grid-cols-[140px_130px_140px_minmax(220px,1fr)_110px_96px_128px]';
const TABLE_MIN = 'min-w-[1100px]';


function VersionCell({ version }: { version: Build['version'] }) {
    const label = version.name ?? version.id;
    return (
        <div className="min-w-0">
            <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-xs text-gray-200 font-medium truncate">{label}</span>
                {version.type && <VersionTypeBadge type={version.type} />}
            </div>
            <a
                href={commitUrl(version.remote_info.url, version.git_hash)}
                target="_blank"
                rel="noopener noreferrer"
                className="font-mono text-[10px] text-yellow-500/70 hover:text-yellow-400 hover:underline underline-offset-2 mt-0.5 truncate inline-block transition-colors"
            >
                {version.git_hash.slice(0, 10)}
            </a>
        </div>
    );
}

interface BuildsTableProps {
    onRebuild?: (config: BuildConfig) => void;
}

export function BuildsTable({ onRebuild }: BuildsTableProps = {}) {
    const [builds, setBuilds] = useState<Build[]>([]);
    const [page, setPage] = useState(0);
    const [hasMore, setHasMore] = useState(false);
    const [loading, setLoading] = useState(true);
    const [selectedBuildId, setSelectedBuildId] = useState<string | null>(null);
    const [modalInitialTab, setModalInitialTab] = useState<'details' | 'logs'>('details');
    const [modalFeaturesExpanded, setModalFeaturesExpanded] = useState(false);
    const [rebuildLoadingId, setRebuildLoadingId] = useState<string | null>(null);
    const [rebuildError, setRebuildError] = useState<string | null>(null);
    const sectionRef = useRef<HTMLElement | null>(null);
    const pollTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const pageRef = useRef(page);
    const fetchGenRef = useRef(0);
    const inFlightRef = useRef(false);
    pageRef.current = page;

    function openBuild(b: Build) {
        const tab = NON_TERMINAL_BUILD_STATES.includes(b.progress.state) ? 'logs' : 'details';
        setModalInitialTab(tab);
        setModalFeaturesExpanded(false);
        setSelectedBuildId(b.build_id);
    }

    function openBuildFeatures(b: Build) {
        setModalInitialTab('details');
        setModalFeaturesExpanded(true);
        setSelectedBuildId(b.build_id);
    }

    async function handleRebuildClick(buildId: string) {
        if (!onRebuild || rebuildLoadingId) return;
        setRebuildError(null);
        setRebuildLoadingId(buildId);
        try {
            const config = await fetchBuildConfig(buildId);
            onRebuild(config);
        } catch (e: unknown) {
            setRebuildError(
                e instanceof Error ? e.message : `Failed to load config for ${buildId}`,
            );
        } finally {
            setRebuildLoadingId(null);
        }
    }

    function doFetch(p: number, isInitial = false) {
        if (!isInitial && inFlightRef.current) return;

        const gen = ++fetchGenRef.current;
        inFlightRef.current = true;
        if (isInitial) setLoading(true);

        fetchBuilds(PAGE_SIZE + 1, p * PAGE_SIZE)
            .then(data => {
                if (gen !== fetchGenRef.current) return;
                setHasMore(data.length > PAGE_SIZE);
                setBuilds(data.slice(0, PAGE_SIZE));
            })
            .finally(() => {
                if (gen === fetchGenRef.current) {
                    inFlightRef.current = false;
                    if (isInitial) setLoading(false);
                }
            });
    }

    const doFetchRef = useRef(doFetch);
    doFetchRef.current = doFetch;

    useEffect(() => {
        inFlightRef.current = false;
        doFetchRef.current(pageRef.current, true);
    }, [page]);

    useEffect(() => {
        const el = sectionRef.current;
        if (!el) return;

        function startPolling() {
            if (pollTimerRef.current) return;
            pollTimerRef.current = setInterval(() => {
                doFetchRef.current(pageRef.current);
            }, POLL_INTERVAL_MS);
        }

        function stopPolling() {
            if (pollTimerRef.current) {
                clearInterval(pollTimerRef.current);
                pollTimerRef.current = null;
            }
        }

        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting) startPolling();
                else stopPolling();
            },
            { threshold: 0.1 }
        );
        observer.observe(el);

        return () => { observer.disconnect(); stopPolling(); };
    }, []);

    return (
        <>
            <section ref={sectionRef} className="mt-24 px-6 md:px-10 max-w-7xl mx-auto pb-16">
                <div className="mb-6">
                    <h2 className="text-2xl font-semibold text-white">Recent Builds</h2>
                    <p className="text-sm text-gray-500 mt-1 font-mono">All builds across the server</p>
                </div>

                <div className="card overflow-hidden">
                    {rebuildError && (
                        <div className="px-5 py-2.5 border-b border-red-500/30 bg-red-500/10 text-xs text-red-400">
                            {rebuildError}
                        </div>
                    )}
                    <div className="overflow-x-auto">
                        <div className={clsx(TABLE_MIN, 'w-full')}>
                            <div className={clsx('grid gap-4 px-5 py-3 w-full bg-surface-3 border-b border-surface-4 dark-chrome', COLS)}>
                                {([
                                    { top: 'Build ID' },
                                    { top: 'Vehicle', btm: 'Board' },
                                    { top: 'Version', btm: 'Git SHA' },
                                    { top: 'Features' },
                                    { top: 'Status' },
                                    { top: 'Age' },
                                    { top: 'Actions' },
                                ] as { top: string; btm?: string }[]).map(({ top, btm }) => (
                                    <div key={top} className="flex flex-col leading-none gap-[3px]">
                                        <span className="text-[10px] font-mono uppercase tracking-widest text-white/80">
                                            {top}{btm && <span className="text-[8px] text-white/40 font-semibold tracking-widest ml-0.5">/</span>}
                                        </span>
                                        {btm && <span className="text-[10px] font-mono uppercase tracking-widest text-white/80">{btm}</span>}
                                    </div>
                                ))}
                            </div>

                            {loading ? (
                                <div className="divide-y divide-surface-4">
                                    {Array.from({ length: PAGE_SIZE }).map((_, i) => (
                                        <div key={i} className={clsx('grid gap-4 px-5 py-4 w-full', COLS)}>
                                            {Array.from({ length: 7 }).map((_, j) => (
                                                <div key={j} className="h-4 bg-skeleton rounded animate-pulse" />
                                            ))}
                                        </div>
                                    ))}
                                </div>
                            ) : builds.length === 0 ? (
                                <div className="py-16 text-center text-gray-500 text-sm">No builds found</div>
                            ) : (
                                <div className="divide-y divide-surface-4">
                                    {builds.map(b => {
                                        const terminal = isTerminal(b.progress.state);
                                        return (
                                        <div
                                            key={b.build_id}
                                            className={clsx('grid gap-4 px-5 py-4 w-full hover:bg-hover transition-colors', COLS)}
                                        >
                                            <div className="flex items-center min-w-0">
                                                <button
                                                    onClick={() => openBuild(b)}
                                                    className="font-mono text-xs text-yellow-400 hover:text-yellow-300 hover:underline underline-offset-2 transition-colors text-left truncate max-w-full"
                                                >
                                                    {b.build_id}
                                                </button>
                                            </div>

                                            <div className="min-w-0">
                                                <div className="text-sm text-gray-200 font-medium truncate">{b.vehicle.name}</div>
                                                <div className="text-xs text-gray-500 font-mono mt-0.5 truncate">{b.board.name}</div>
                                            </div>

                                            <VersionCell version={b.version} />

                                            <div className="flex items-start min-w-0">
                                                {b.selected_features.length === 0 ? (
                                                    <span className="badge-gray badge text-[10px]">none</span>
                                                ) : (
                                                    <div className="flex flex-wrap gap-1 min-w-0">
                                                        {b.selected_features.slice(0, 5).map(f => (
                                                            <span
                                                                key={f}
                                                                className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-surface-3 border border-surface-4 text-gray-400 truncate max-w-[96px]"
                                                                title={f}
                                                            >
                                                                {f}
                                                            </span>
                                                        ))}
                                                        {b.selected_features.length > 5 && (
                                                            <button
                                                                onClick={() => openBuildFeatures(b)}
                                                                className="text-[10px] font-mono px-1.5 py-0.5 rounded-full bg-yellow-400/15 border border-yellow-400/40 text-yellow-400 hover:bg-yellow-400/25 transition-colors"
                                                            >
                                                                +{b.selected_features.length - 5} more
                                                            </button>
                                                        )}
                                                    </div>
                                                )}
                                            </div>

                                            <div className="flex items-center min-w-0">
                                                <StateBadge state={b.progress.state} />
                                            </div>

                                            <div className="flex items-center gap-1 text-xs text-gray-500 whitespace-nowrap min-w-0">
                                                <Clock className="w-3 h-3 shrink-0" />
                                                {formatAge(b.time_created)}
                                            </div>

                                            <div className="flex items-center gap-1 shrink-0">
                                                <Tooltip text="Build details">
                                                    <button
                                                        onClick={() => openBuild(b)}
                                                        className="p-1.5 rounded-md text-gray-500 hover:text-yellow-400 hover:bg-yellow-400/10 transition-colors"
                                                    >
                                                        <Info className="w-3.5 h-3.5" />
                                                    </button>
                                                </Tooltip>
                                                <Tooltip text={terminal ? 'Download artifacts' : 'Artifacts available when build finishes'}>
                                                    <button
                                                        type="button"
                                                        onClick={() => {
                                                            window.location.href = buildArtifactUrl(b.build_id);
                                                        }}
                                                        disabled={!terminal}
                                                        className="p-1.5 rounded-md text-gray-500 hover:text-yellow-400 hover:bg-yellow-400/10 transition-colors disabled:opacity-40 disabled:pointer-events-none"
                                                    >
                                                        <Download className="w-3.5 h-3.5" />
                                                    </button>
                                                </Tooltip>
                                                <Tooltip text="Rebuild with same config">
                                                    <button
                                                        onClick={() => handleRebuildClick(b.build_id)}
                                                        disabled={rebuildLoadingId === b.build_id}
                                                        className="p-1.5 rounded-md text-gray-500 hover:text-yellow-400 hover:bg-yellow-400/10 transition-colors disabled:opacity-40 disabled:pointer-events-none"
                                                    >
                                                        {rebuildLoadingId === b.build_id
                                                            ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                                            : <RotateCcw className="w-3.5 h-3.5" />}
                                                    </button>
                                                </Tooltip>
                                            </div>
                                        </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>

                    {(page > 0 || hasMore) && (
                        <div className="flex items-center justify-between px-5 py-3 border-t border-surface-4 bg-surface-2">
                            <span className="text-xs text-gray-500">
                                Page {page + 1}
                            </span>
                            <div className="flex gap-2">
                                <button
                                    onClick={() => setPage(p => Math.max(0, p - 1))}
                                    disabled={page === 0}
                                    className="btn-ghost p-1.5 disabled:opacity-30"
                                >
                                    <ChevronLeft className="w-4 h-4" />
                                </button>
                                <button
                                    onClick={() => setPage(p => p + 1)}
                                    disabled={!hasMore}
                                    className="btn-ghost p-1.5 disabled:opacity-30"
                                >
                                    <ChevronRight className="w-4 h-4" />
                                </button>
                            </div>
                        </div>
                    )}
                </div>
            </section>

            {selectedBuildId && (
                <BuildInfoModal
                    buildId={selectedBuildId}
                    initialTab={modalInitialTab}
                    initialFeaturesExpanded={modalFeaturesExpanded}
                    onClose={() => setSelectedBuildId(null)}
                />
            )}
        </>
    );
}
