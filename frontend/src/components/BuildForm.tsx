import { useState, useEffect, useRef, useCallback } from 'react';
import {
    Sliders, ChevronRight, Terminal,
    ArrowRight, RefreshCw, PackageOpen,
} from 'lucide-react';
import clsx from 'clsx';
import type {
    Vehicle, Version, Board, Feature, FormStep, StandardArtifact, BuildState,
} from '../types';
import {
    fetchVehicles, submitBuild, fetchStandardArtifacts,
} from '../api';
import {
    StepHeader, SearchableDropdown, VersionSelector, FormSection, ChosenPill, LoadingFiller, VehicleSelector,
} from './StepComponents';
import { FeaturesModal } from './FeaturesModal';
import { BuildInfoModal } from './BuildInfoModal';
import { ConfigDropZone } from './ConfigDropZone';
import { ConfigConflictModal } from './ConfigConflictModal';
import { CollapsibleBanner } from './CollapsibleBanner';
import { ErrorBanner } from './ErrorBanner';
import { StandardArtifactsGrid } from './StandardArtifactsGrid';
import { DoneStep } from './DoneStep';
import { parseConfigYaml, type BuildConfig } from '../buildConfig';
import { useBuildPolling } from '../hooks/useBuildPolling';
import { useConfigLoad, type ConfigPhase } from '../hooks/useConfigLoad';

const STEPS = [
    { id: 'vehicle', label: 'Vehicle' },
    { id: 'version', label: 'Version' },
    { id: 'board', label: 'Board' },
];

function headerStep(step: FormStep): string {
    if (['choice', 'standard-files', 'features', 'building', 'done'].includes(step)) return '__done__';
    return step;
}

function versionSupportsStandardArtifacts(version: Version): boolean {
    return version.remote.name === 'ardupilot';
}

const TYPE_ORDER: Record<Version['type'], number> = { stable: 0, beta: 1, latest: 2, tag: 3 };

function sortVersions(vs: Version[]): Version[] {
    return [...vs].sort((a, b) => {
        const typeDiff = TYPE_ORDER[a.type] - TYPE_ORDER[b.type];
        if (typeDiff !== 0) return typeDiff;
        if (a.type === 'stable' || a.type === 'beta') {
            const aParts = a.name.split('.').map(Number);
            const bParts = b.name.split('.').map(Number);
            for (let i = 0; i < Math.max(aParts.length, bParts.length); i++) {
                const diff = (bParts[i] ?? 0) - (aParts[i] ?? 0);
                if (diff !== 0) return diff;
            }
        }
        return 0;
    });
}

function versionBadge(t: Version['type']) {
    return ({
        stable: 'badge-green', beta: 'badge-yellow', latest: 'badge-blue', tag: 'badge-gray',
    } as const)[t];
}

interface BuildFormProps {
    initialConfig?: BuildConfig | null;
    onConsumeInitialConfig?: () => void;
}

export function BuildForm({ initialConfig, onConsumeInitialConfig }: BuildFormProps) {
    const [step, setStep] = useState<FormStep>('vehicle');
    const [vehicles, setVehicles] = useState<Vehicle[]>([]);
    const [versions, setVersions] = useState<Version[]>([]);
    const [boards, setBoards] = useState<Board[]>([]);
    const [features, setFeatures] = useState<Feature[]>([]);

    const [vehicle, setVehicle] = useState<Vehicle | null>(null);
    const [version, setVersion] = useState<Version | null>(null);
    const [board, setBoard] = useState<Board | null>(null);
    const [selected, setSelected] = useState<Set<string>>(new Set());
    const [showFeatsModal, setShowFeatsModal] = useState(false);
    const [showBuildModal, setShowBuildModal] = useState(false);

    const [buildId, setBuildId] = useState<string | null>(null);
    const [buildProgress, setBuildProgress] = useState(0);
    const [buildState, setBuildState] = useState<BuildState>('PENDING');

    const [standardArtifacts, setStandardArtifacts] = useState<StandardArtifact[] | null>(null);
    const [standardFilesLoading, setStandardFilesLoading] = useState(false);

    const [vehiclesLoading, setVehiclesLoading] = useState(false);
    const [versionsLoading, setVersionsLoading] = useState(false);
    const [boardsLoading, setBoardsLoading] = useState(false);
    const [featuresLoading, setFeaturesLoading] = useState(false);
    const [submitting, setSubmitting] = useState(false);

    const [error, setError] = useState<string | null>(null);

    const [unavailableFeatures, setUnavailableFeatures] = useState<string[]>([]);
    const [dismissedUnavailable, setDismissedUnavailable] = useState(false);
    const [autoAddedFeatures, setAutoAddedFeatures] = useState<string[]>([]);
    const [dismissedAutoAdded, setDismissedAutoAdded] = useState(false);

    const [featureConfigParseError, setFeatureConfigParseError] = useState<string | null>(null);

    const [configPhase, setConfigPhase] = useState<ConfigPhase>({ phase: 'idle' });
    const [configParseError, setConfigParseError] = useState<string | null>(null);

    const loadGenRef = useRef(0);
    const vehiclesRef = useRef<Vehicle[]>([]);
    const versionsRef = useRef<Version[]>([]);
    const boardsRef = useRef<Board[]>([]);
    const featuresRef = useRef<Feature[]>([]);
    const resetRef = useRef<() => void>(() => {});

    useEffect(() => { vehiclesRef.current = vehicles; }, [vehicles]);
    useEffect(() => { versionsRef.current = versions; }, [versions]);
    useEffect(() => { boardsRef.current = boards; }, [boards]);
    useEffect(() => { featuresRef.current = features; }, [features]);

    function bumpLoadGen(): number {
        return ++loadGenRef.current;
    }

    const { startPolling, stopBuildPolling } = useBuildPolling({
        setBuildProgress,
        setBuildState,
        setStep,
    });

    const reset = useCallback(() => {
        bumpLoadGen();
        stopBuildPolling();
        setStep('vehicle');
        setVehicle(null); setVersion(null); setBoard(null);
        setSelected(new Set()); setBuildId(null);
        setBuildProgress(0); setBuildState('PENDING');
        setVersionsLoading(false); setBoardsLoading(false);
        setFeaturesLoading(false); setSubmitting(false);
        setError(null);
        setUnavailableFeatures([]); setDismissedUnavailable(false);
        setAutoAddedFeatures([]); setDismissedAutoAdded(false);
        setFeatureConfigParseError(null);
        setConfigPhase({ phase: 'idle' }); setConfigParseError(null);
        setStandardArtifacts(null); setStandardFilesLoading(false);
    }, [stopBuildPolling]);

    resetRef.current = reset;

    const {
        startConfigLoad,
        applyConfigFeatures,
        handleConflictSelect,
        handleConflictCancel,
        loadVersions,
        loadBoards,
        loadDefaultFeatures,
    } = useConfigLoad({
        loadGenRef,
        bumpLoadGen,
        reset: () => resetRef.current(),
        vehiclesRef,
        versionsRef,
        boardsRef,
        vehicle,
        version,
        setConfigPhase,
        setError,
        setVehicles,
        setVersions,
        setBoards,
        setFeatures,
        setVehicle,
        setVersion,
        setBoard,
        setSelected,
        setStep,
        setVersionsLoading,
        setBoardsLoading,
        setFeaturesLoading,
        setUnavailableFeatures,
        setDismissedUnavailable,
        setAutoAddedFeatures,
        setDismissedAutoAdded,
    });

    function goToStep(next: FormStep) {
        bumpLoadGen();
        setVersionsLoading(false);
        setBoardsLoading(false);
        setFeaturesLoading(false);
        setStandardFilesLoading(false);
        setError(null);
        setFeatureConfigParseError(null);
        setShowFeatsModal(false);

        if (next === 'vehicle') {
            setVersion(null);
            setBoard(null);
            setVersions([]);
            setBoards([]);
            setFeatures([]);
            setSelected(new Set());
            setStandardArtifacts(null);
            setUnavailableFeatures([]);
            setDismissedUnavailable(false);
            setAutoAddedFeatures([]);
            setDismissedAutoAdded(false);
        } else if (next === 'version') {
            setBoard(null);
            setBoards([]);
            setFeatures([]);
            setSelected(new Set());
            setStandardArtifacts(null);
            setUnavailableFeatures([]);
            setDismissedUnavailable(false);
            setAutoAddedFeatures([]);
            setDismissedAutoAdded(false);
        } else if (next === 'board') {
            setFeatures([]);
            setSelected(new Set());
            setStandardArtifacts(null);
            setUnavailableFeatures([]);
            setDismissedUnavailable(false);
            setAutoAddedFeatures([]);
            setDismissedAutoAdded(false);
        }

        setStep(next);
    }

    useEffect(() => {
        const gen = bumpLoadGen();
        setVehiclesLoading(true);
        fetchVehicles()
            .then(data => {
                if (gen !== loadGenRef.current) return;
                setVehicles(data);
            })
            .catch(() => {
                if (gen !== loadGenRef.current) return;
                setError('Failed to fetch vehicles from server');
            })
            .finally(() => {
                if (gen !== loadGenRef.current) return;
                setVehiclesLoading(false);
            });
    }, []);

    const startConfigLoadRef = useRef(startConfigLoad);
    startConfigLoadRef.current = startConfigLoad;

    useEffect(() => {
        if (!initialConfig) return;
        onConsumeInitialConfig?.();
        startConfigLoadRef.current(initialConfig);
    }, [initialConfig, onConsumeInitialConfig]);

    const handleFileDrop = useCallback((yamlText: string) => {
        setConfigParseError(null);
        parseConfigYaml(yamlText)
            .then(config => startConfigLoadRef.current(config))
            .catch((e: unknown) => setConfigParseError(e instanceof Error ? e.message : 'Invalid config file'));
    }, []);

    const applyConfigFeaturesRef = useRef(applyConfigFeatures);
    applyConfigFeaturesRef.current = applyConfigFeatures;

    const handleFeatureConfigDrop = useCallback((yamlText: string) => {
        setFeatureConfigParseError(null);
        parseConfigYaml(yamlText)
            .then(config => {
                setUnavailableFeatures([]); setDismissedUnavailable(false);
                setAutoAddedFeatures([]); setDismissedAutoAdded(false);
                applyConfigFeaturesRef.current(config, featuresRef.current);
            })
            .catch((e: unknown) =>
                setFeatureConfigParseError(e instanceof Error ? e.message : 'Invalid config file'),
            );
    }, []);

    function selectVehicle(id: string) {
        const v = vehicles.find(x => x.id === id)!;
        setStep('version');
        void loadVersions(v);
    }

    function selectVersion(id: string) {
        const v = versions.find(x => x.id === id)!;
        setStandardArtifacts(null);
        setStep('board');
        void loadBoards(vehicle!, v);
    }

    function selectBoard(id: string) {
        const b = boards.find(x => x.id === id)!;
        setBoard(b);
        setError(null);
        setStep('choice');
    }

    function chooseCustom() {
        void loadDefaultFeatures(vehicle!, version!, board!);
    }

    function chooseStandard() {
        const gen = bumpLoadGen();
        setStandardArtifacts(null);
        setStandardFilesLoading(true);
        setError(null);
        setStep('standard-files');
        fetchStandardArtifacts(vehicle!.id, version!.id, board!.id)
            .then(result => {
                if (gen !== loadGenRef.current) return;
                setStandardArtifacts(result);
            })
            .catch(() => {
                if (gen !== loadGenRef.current) return;
                setStandardArtifacts(null);
                setError('Failed to fetch standard build artifacts');
            })
            .finally(() => {
                if (gen !== loadGenRef.current) return;
                setStandardFilesLoading(false);
            });
    }

    async function startBuild() {
        try {
            setSubmitting(true);
            setError(null);
            const res = await submitBuild({
                vehicle_id: vehicle!.id,
                board_id: board!.id,
                version_id: version!.id,
                selected_features: Array.from(selected),
            });
            setBuildId(res.build_id);
            setBuildProgress(0);
            setBuildState('PENDING');
            setStep('building');
            startPolling(res.build_id);
        } catch (e: unknown) {
            setError(e instanceof Error ? e.message : 'Build submit failed');
        } finally {
            setSubmitting(false);
        }
    }

    const isConfigLoading = configPhase.phase === 'loading';
    const failedBuild = buildState === 'FAILURE' || buildState === 'ERROR' || buildState === 'TIMED_OUT';

    return (
        <>
            <div className="card h-full flex flex-col p-6 md:p-8">
                <div className="flex items-start justify-between gap-4 mb-2">
                    <div className="flex-1 min-w-0">
                        <StepHeader
                            steps={STEPS}
                            currentStep={headerStep(step)}
                            onStepClick={!['building', 'done'].includes(step) ? (id => goToStep(id as FormStep)) : undefined}
                        />
                    </div>
                    {step !== 'vehicle' && (
                        <button onClick={reset} className="btn-ghost text-xs py-1 px-2 shrink-0 mt-0.5">
                            <RefreshCw className="w-3 h-3" /> Start over
                        </button>
                    )}
                </div>

                {isConfigLoading && (
                    <div className="mb-4 flex items-center gap-2 rounded-lg border border-yellow-400/30 bg-yellow-400/5 px-4 py-2.5">
                        <span className="inline-block w-2 h-2 rounded-full bg-yellow-400 animate-ping shrink-0" />
                        <span className="text-xs text-yellow-400 font-mono">Loading config…</span>
                    </div>
                )}

                {step === 'vehicle' && (
                    <div className="space-y-5">
                        <FormSection label="Select vehicle">
                            <VehicleSelector
                                loading={vehiclesLoading}
                                options={vehicles.map(v => ({ id: v.id, name: v.name }))}
                                selected={vehicle?.id}
                                onSelect={selectVehicle}
                            />
                        </FormSection>

                        <div className="flex items-center gap-3">
                            <div className="flex-1 h-px bg-surface-4" />
                            <span className="text-xs text-gray-500 font-mono uppercase tracking-wider">or</span>
                            <div className="flex-1 h-px bg-surface-4" />
                        </div>

                        <ConfigDropZone onLoad={handleFileDrop} />
                        <ErrorBanner message={configParseError} />
                        <ErrorBanner message={error} />
                    </div>
                )}

                {step === 'version' && (
                    <div className="space-y-4">
                        <ChosenPill label="Vehicle" value={vehicle!.name} onEdit={() => goToStep('vehicle')} />
                        <FormSection label="Select version">
                            <VersionSelector
                                loading={versionsLoading}
                                options={sortVersions(versions).map(v => ({
                                    id: v.id, name: v.name,
                                    type: v.type, badge: v.type,
                                    badgeColor: versionBadge(v.type),
                                    remote: v.remote.name !== 'ardupilot' ? v.remote.name : undefined,
                                }))}
                                selected={version?.id}
                                onSelect={selectVersion}
                            />
                        </FormSection>
                        <ErrorBanner message={error} />
                    </div>
                )}

                {step === 'board' && (
                    <div className="space-y-4">
                        <ChosenPill label="Vehicle" value={vehicle!.name} onEdit={() => goToStep('vehicle')} />
                        <ChosenPill label="Version" value={version!.name} onEdit={() => goToStep('version')} />
                        <FormSection label="Select board">
                            <SearchableDropdown
                                loading={boardsLoading}
                                options={boards.map(b => ({ id: b.id, name: b.name }))}
                                selected={board?.id}
                                onSelect={selectBoard}
                                placeholder="Choose a board…"
                            />
                            <LoadingFiller kind="boards" loading={boardsLoading} />
                        </FormSection>
                        <ErrorBanner message={error} />
                    </div>
                )}

                {step === 'choice' && (
                    <div className="space-y-4">
                        <ChosenPill label="Vehicle" value={vehicle!.name} onEdit={() => goToStep('vehicle')} />
                        <ChosenPill label="Version" value={version!.name} onEdit={() => goToStep('version')} />
                        <ChosenPill label="Board" value={board!.name} onEdit={() => goToStep('board')} />
                        <FormSection label="How would you like to proceed?">
                            <div className={clsx(
                                'grid gap-3 mt-2',
                                version && versionSupportsStandardArtifacts(version) ? 'grid-cols-2' : 'grid-cols-1',
                            )}>
                                {version && versionSupportsStandardArtifacts(version) && (
                                    <button
                                        onClick={chooseStandard}
                                        className="group relative flex flex-col items-start p-4 rounded-xl border border-surface-4 bg-surface-3 hover:border-yellow-400/50 hover:bg-hover transition-all duration-200 text-left"
                                    >
                                        <PackageOpen className="w-5 h-5 text-gray-300 mb-2" />
                                        <div className="font-semibold text-white text-sm">Standard Build Artifacts</div>
                                        <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                                            Pre-built official firmware from firmware.ardupilot.org.
                                        </p>
                                        <ArrowRight className="w-4 h-4 text-gray-400 mt-3 transition-all group-hover:translate-x-1" />
                                    </button>
                                )}
                                <button
                                    onClick={chooseCustom}
                                    className="group flex flex-col items-start p-4 rounded-xl border border-yellow-400/30 bg-yellow-400/5 hover:border-yellow-400/70 hover:bg-yellow-400/10 transition-all duration-200 text-left"
                                >
                                    <Sliders className="w-5 h-5 text-yellow-400 mb-2" />
                                    <div className="font-semibold text-white text-sm">Customise</div>
                                    <p className="text-xs text-gray-400 mt-1 leading-relaxed">
                                        Select features, compile a tailored build, and download.
                                    </p>
                                    <ArrowRight className="w-4 h-4 text-yellow-400 mt-3 transition-all group-hover:translate-x-1" />
                                </button>
                            </div>
                        </FormSection>
                        <ErrorBanner message={error} />
                    </div>
                )}

                {step === 'standard-files' && (
                    <div className="space-y-4">
                        <ChosenPill label="Vehicle" value={vehicle!.name} onEdit={() => goToStep('vehicle')} />
                        <ChosenPill label="Version" value={version!.name} onEdit={() => goToStep('version')} />
                        <ChosenPill label="Board" value={board!.name} onEdit={() => goToStep('board')} />
                        {standardFilesLoading ? (
                            <FormSection label="Standard build files">
                                <div className="grid grid-cols-4 gap-2">
                                    {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
                                        <div key={i} className="h-24 bg-skeleton rounded-xl animate-pulse" />
                                    ))}
                                </div>
                            </FormSection>
                        ) : standardArtifacts === null || standardArtifacts.length === 0 ? (
                            <FormSection label="Standard build files">
                                <div className="space-y-3">
                                    <ErrorBanner message={error ?? 'Standard firmware is not available for this version and board combination.'} />
                                    <button
                                        type="button"
                                        onClick={chooseStandard}
                                        className="btn-secondary text-sm py-2"
                                    >
                                        <RefreshCw className="w-3.5 h-3.5" />
                                        Retry
                                    </button>
                                </div>
                            </FormSection>
                        ) : (
                            <StandardArtifactsGrid artifacts={standardArtifacts} />
                        )}
                    </div>
                )}

                {step === 'features' && (
                    <div className="space-y-4">
                        <ChosenPill label="Vehicle" value={vehicle!.name} onEdit={() => goToStep('vehicle')} />
                        <ChosenPill label="Version" value={version!.name} onEdit={() => goToStep('version')} />
                        <ChosenPill label="Board" value={board!.name} onEdit={() => goToStep('board')} />

                        {autoAddedFeatures.length > 0 && !dismissedAutoAdded && (
                            <CollapsibleBanner
                                color="blue"
                                message={`${autoAddedFeatures.length} feature${autoAddedFeatures.length > 1 ? 's were' : ' was'} auto-selected to satisfy dependencies not listed in your config:`}
                                items={autoAddedFeatures}
                                onDismiss={() => setDismissedAutoAdded(true)}
                            />
                        )}

                        {unavailableFeatures.length > 0 && !dismissedUnavailable && (
                            <CollapsibleBanner
                                color="yellow"
                                message={`${unavailableFeatures.length} feature${unavailableFeatures.length > 1 ? 's' : ''} from your config ${unavailableFeatures.length > 1 ? 'are' : 'is'} unavailable for this board/version combination and ${unavailableFeatures.length > 1 ? 'have' : 'has'} been skipped:`}
                                items={unavailableFeatures}
                                onDismiss={() => setDismissedUnavailable(true)}
                            />
                        )}

                        <FormSection label="Feature selection">
                            {featuresLoading ? (
                                <div className="rounded-xl border border-surface-4 bg-skeleton/60 p-5 flex items-center justify-between animate-pulse">
                                    <div className="space-y-2">
                                        <div className="h-4 w-40 bg-skeleton rounded" />
                                        <div className="h-3 w-56 bg-skeleton rounded" />
                                    </div>
                                    <div className="h-8 w-28 bg-skeleton rounded-lg" />
                                </div>
                            ) : (
                                <div className="rounded-xl border border-surface-4 bg-surface-3 p-5 flex items-center justify-between">
                                    <div>
                                        <div className="text-sm font-medium text-gray-200">
                                            {selected.size} / {features.length} features selected
                                        </div>
                                        <p className="text-xs text-gray-500 mt-0.5">
                                            {unavailableFeatures.length > 0
                                                ? 'Config applied with adjustments — review below'
                                                : 'Defaults pre-applied based on your board'}
                                        </p>
                                    </div>
                                    <button
                                        onClick={() => setShowFeatsModal(true)}
                                        className="btn-secondary text-sm py-2"
                                    >
                                        <Sliders className="w-3.5 h-3.5" />
                                        Select Features
                                    </button>
                                </div>
                            )}
                        </FormSection>

                        <div className="flex items-center gap-3">
                            <div className="flex-1 h-px bg-surface-4" />
                            <span className="text-xs text-gray-500 font-mono uppercase tracking-wider">
                                or load feature selection from config
                            </span>
                            <div className="flex-1 h-px bg-surface-4" />
                        </div>

                        {featuresLoading ? (
                            <div className="rounded-xl border-2 border-dashed border-surface-4 bg-skeleton/40 px-4 py-6 flex flex-col items-center justify-center gap-2 animate-pulse">
                                <div className="w-7 h-7 rounded-full bg-skeleton" />
                                <div className="h-3 w-32 bg-skeleton rounded" />
                                <div className="h-2.5 w-48 bg-skeleton rounded" />
                            </div>
                        ) : (
                            <ConfigDropZone
                                onLoad={handleFeatureConfigDrop}
                                title="Load feature selection"
                                hint={
                                    <>
                                        Applies feature list only · vehicle/version/board in the file are ignored ·{' '}
                                        <span className="font-mono">.yaml</span> /{' '}
                                        <span className="font-mono">.yml</span>
                                    </>
                                }
                            />
                        )}

                        <ErrorBanner message={featureConfigParseError} />
                        <ErrorBanner message={error} />

                        {featuresLoading ? (
                            <>
                                <div className="h-12 bg-skeleton rounded-xl animate-pulse" />
                                <LoadingFiller kind="features" loading={featuresLoading} />
                            </>
                        ) : (
                            <button
                                onClick={startBuild}
                                disabled={features.length === 0 || submitting}
                                className="btn-primary w-full justify-center py-3"
                            >
                                <ChevronRight className="w-4 h-4" />
                                {submitting ? 'Submitting…' : 'Build Firmware'}
                            </button>
                        )}
                    </div>
                )}

                {step === 'building' && (
                    <div className="space-y-6">
                        <div>
                            <ChosenPill label="Vehicle" value={vehicle!.name} />
                            <ChosenPill label="Version" value={version!.name} />
                            <ChosenPill label="Board" value={board!.name} />
                            <ChosenPill label="Build ID" value={buildId ?? '…'} />
                        </div>

                        <FormSection label="Build progress">
                            <div className="space-y-3">
                                <div className="flex items-center justify-between text-xs font-mono">
                                    <span className="text-gray-400">{buildState}</span>
                                    <span className={clsx('transition-colors duration-700', {
                                        'text-red-400': failedBuild,
                                        'text-emerald-400': buildState === 'SUCCESS',
                                        'text-yellow-400': !failedBuild && buildState !== 'SUCCESS',
                                    })}>
                                        {buildProgress}%
                                    </span>
                                </div>
                                <div className="w-full h-2 bg-surface-4 rounded-full overflow-hidden">
                                    <div
                                        className={clsx('h-full rounded-full progress-bar-fill transition-all duration-700', {
                                            'bg-gradient-to-r from-red-600 to-red-400': failedBuild,
                                            'bg-gradient-to-r from-green-500 to-green-400 progress-bar-complete': buildState === 'SUCCESS',
                                            'bg-gradient-to-r from-yellow-500 to-yellow-300': !failedBuild && buildState !== 'SUCCESS',
                                        })}
                                        style={{ width: `${buildProgress}%` }}
                                    />
                                </div>
                                {buildProgress === 0 ? (
                                    <p className="text-xs font-mono mt-1 text-gray-500">
                                        <span className="inline-block w-1.5 h-1.5 rounded-full bg-gray-500 mr-2 animate-ping" style={{ verticalAlign: 'middle' }} />
                                        {buildState === 'PENDING'
                                            ? 'Your build is in the queue and will start soon…'
                                            : 'Setting up the build environment…'}
                                    </p>
                                ) : (
                                    <p className={clsx('text-xs font-mono', {
                                        'text-red-400': failedBuild,
                                        'text-gray-500': !failedBuild,
                                    })}>
                                        Compiling {vehicle?.name} with {selected.size} feature overrides for {board?.name}…
                                    </p>
                                )}
                            </div>
                        </FormSection>

                        <button onClick={() => setShowBuildModal(true)} className="btn-ghost text-sm w-full justify-center py-2.5">
                            <Terminal className="w-4 h-4" />
                            View Build Logs
                        </button>
                    </div>
                )}

                {step === 'done' && (
                    <div className="animate-in">
                        <DoneStep
                            buildState={buildState}
                            buildId={buildId}
                            vehicle={vehicle}
                            version={version}
                            board={board}
                            selected={selected}
                            onViewLogs={() => setShowBuildModal(true)}
                            onRebuild={startConfigLoad}
                        />
                    </div>
                )}
            </div>

            {configPhase.phase === 'conflict' && (
                <ConfigConflictModal
                    kind={configPhase.kind}
                    requested={
                        configPhase.kind === 'vehicle'
                            ? configPhase.config.vehicle
                            : configPhase.kind === 'version'
                                ? {
                                    id: configPhase.config.version?.id ?? '',
                                    name: configPhase.config.version?.name ?? configPhase.config.version?.id ?? '',
                                  }
                                : (configPhase.config.board ?? { id: '', name: '' })
                    }
                    available={configPhase.available}
                    onSelect={id => handleConflictSelect(id, configPhase)}
                    onCancel={handleConflictCancel}
                />
            )}

            {showFeatsModal && (
                <FeaturesModal
                    features={features}
                    selected={selected}
                    onDone={sel => { setSelected(sel); setShowFeatsModal(false); }}
                    onClose={() => setShowFeatsModal(false)}
                />
            )}

            {showBuildModal && buildId && (
                <BuildInfoModal
                    buildId={buildId}
                    initialTab="logs"
                    onClose={() => setShowBuildModal(false)}
                />
            )}
        </>
    );
}
