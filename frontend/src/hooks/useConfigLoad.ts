import { useCallback, useRef, type Dispatch, type MutableRefObject, type SetStateAction } from 'react';
import type { Vehicle, Version, Board, Feature, FormStep } from '../types';
import {
    fetchVehicles, fetchVersions, fetchBoards, fetchFeatures,
} from '../api';
import type { BuildConfig } from '../buildConfig';
import { resolveDefaultSelection, applyFeatureSelection } from '../featureDeps';
import type { ConflictKind } from '../components/ConfigConflictModal';

export type ConfigPhase =
    | { phase: 'idle' }
    | { phase: 'loading'; config: BuildConfig }
    | { phase: 'conflict'; kind: ConflictKind; config: BuildConfig; available: { id: string; name: string; badge?: string }[] };

interface UseConfigLoadParams {
    loadGenRef: MutableRefObject<number>;
    bumpLoadGen: () => number;
    reset: () => void;

    vehiclesRef: MutableRefObject<Vehicle[]>;
    versionsRef: MutableRefObject<Version[]>;
    boardsRef: MutableRefObject<Board[]>;

    vehicle: Vehicle | null;
    version: Version | null;

    setConfigPhase: Dispatch<SetStateAction<ConfigPhase>>;
    setError: Dispatch<SetStateAction<string | null>>;
    setVehicles: Dispatch<SetStateAction<Vehicle[]>>;
    setVersions: Dispatch<SetStateAction<Version[]>>;
    setBoards: Dispatch<SetStateAction<Board[]>>;
    setFeatures: Dispatch<SetStateAction<Feature[]>>;
    setVehicle: Dispatch<SetStateAction<Vehicle | null>>;
    setVersion: Dispatch<SetStateAction<Version | null>>;
    setBoard: Dispatch<SetStateAction<Board | null>>;
    setSelected: Dispatch<SetStateAction<Set<string>>>;
    setStep: Dispatch<SetStateAction<FormStep>>;
    setVersionsLoading: Dispatch<SetStateAction<boolean>>;
    setBoardsLoading: Dispatch<SetStateAction<boolean>>;
    setFeaturesLoading: Dispatch<SetStateAction<boolean>>;
    setUnavailableFeatures: Dispatch<SetStateAction<string[]>>;
    setDismissedUnavailable: Dispatch<SetStateAction<boolean>>;
    setAutoAddedFeatures: Dispatch<SetStateAction<string[]>>;
    setDismissedAutoAdded: Dispatch<SetStateAction<boolean>>;
}

export function useConfigLoad(p: UseConfigLoadParams) {
    const paramsRef = useRef(p);
    paramsRef.current = p;

    const applyConfigFeatures = useCallback((config: BuildConfig, allFeatures: Feature[]) => {
        const {
            setSelected, setUnavailableFeatures, setDismissedUnavailable,
            setAutoAddedFeatures, setDismissedAutoAdded,
        } = paramsRef.current;

        if (config.use_default_features) {
            setSelected(resolveDefaultSelection(allFeatures));
            setUnavailableFeatures([]);
            setAutoAddedFeatures([]);
            return;
        }

        const { selected, missing, autoAdded } =
            applyFeatureSelection(config.selected_features, allFeatures);

        setSelected(selected);

        if (missing.length > 0) {
            setUnavailableFeatures(missing);
            setDismissedUnavailable(false);
        } else {
            setUnavailableFeatures([]);
        }
        if (autoAdded.length > 0) {
            setAutoAddedFeatures(autoAdded);
            setDismissedAutoAdded(false);
        } else {
            setAutoAddedFeatures([]);
        }
    }, []);

    /** Fetch versions for a vehicle. Returns data if this gen is still current. */
    const loadVersions = useCallback(async (vehicle: Vehicle): Promise<Version[] | null> => {
        const {
            bumpLoadGen, loadGenRef, setVehicle, setVersion, setBoard,
            setVersions, setBoards, setVersionsLoading, setError,
        } = paramsRef.current;
        const gen = bumpLoadGen();
        setVehicle(vehicle);
        setVersion(null); setBoard(null);
        setVersions([]); setBoards([]);
        setVersionsLoading(true);
        setError(null);

        try {
            const allVersions = await fetchVersions(vehicle.id);
            if (gen !== loadGenRef.current) return null;
            setVersions(allVersions);
            return allVersions;
        } catch {
            if (gen !== loadGenRef.current) return null;
            setError('Failed to fetch firmware versions');
            return null;
        } finally {
            if (gen === loadGenRef.current) setVersionsLoading(false);
        }
    }, []);

    /** Fetch boards for a vehicle+version. Returns data if this gen is still current. */
    const loadBoards = useCallback(async (
        vehicle: Vehicle,
        version: Version,
    ): Promise<Board[] | null> => {
        const {
            bumpLoadGen, loadGenRef, setVersion, setBoard, setBoards,
            setBoardsLoading, setError,
        } = paramsRef.current;
        const gen = bumpLoadGen();
        setVersion(version);
        setBoard(null); setBoards([]);
        setBoardsLoading(true);
        setError(null);

        try {
            const allBoards = await fetchBoards(vehicle.id, version.id);
            if (gen !== loadGenRef.current) return null;
            setBoards(allBoards);
            return allBoards;
        } catch {
            if (gen !== loadGenRef.current) return null;
            setError('Failed to fetch boards');
            return null;
        } finally {
            if (gen === loadGenRef.current) setBoardsLoading(false);
        }
    }, []);

    /** Fetch features and apply board defaults. */
    const loadDefaultFeatures = useCallback(async (
        vehicle: Vehicle,
        version: Version,
        board: Board,
    ): Promise<boolean> => {
        const {
            bumpLoadGen, loadGenRef, setBoard, setFeatures, setSelected,
            setFeaturesLoading, setError, setStep,
        } = paramsRef.current;
        const gen = bumpLoadGen();
        setBoard(board);
        setFeatures([]);
        setSelected(new Set());
        setFeaturesLoading(true);
        setError(null);
        setStep('features');

        try {
            const allFeatures = await fetchFeatures(vehicle.id, version.id, board.id);
            if (gen !== loadGenRef.current) return false;
            setFeatures(allFeatures);
            setSelected(resolveDefaultSelection(allFeatures));
            return true;
        } catch {
            if (gen !== loadGenRef.current) return false;
            setError('Failed to fetch features');
            return false;
        } finally {
            if (gen === loadGenRef.current) setFeaturesLoading(false);
        }
    }, []);

    const proceedAfterBoard = useCallback(async (
        config: BuildConfig,
        resolvedVehicle: Vehicle,
        resolvedVersion: Version,
        resolvedBoard: Board,
    ) => {
        const {
            bumpLoadGen, loadGenRef, setConfigPhase, setBoard, setFeatures,
            setSelected, setFeaturesLoading, setStep, setError,
        } = paramsRef.current;
        const gen = bumpLoadGen();
        setConfigPhase({ phase: 'loading', config });
        setBoard(resolvedBoard);
        setFeatures([]);
        setSelected(new Set());
        setFeaturesLoading(true);
        setError(null);
        setStep('features');

        let allFeatures: Feature[];
        try {
            allFeatures = await fetchFeatures(resolvedVehicle.id, resolvedVersion.id, resolvedBoard.id);
            if (gen !== loadGenRef.current) return;
            setFeatures(allFeatures);
        } catch {
            if (gen !== loadGenRef.current) return;
            setError('Failed to fetch features');
            setConfigPhase({ phase: 'idle' });
            return;
        } finally {
            if (gen === loadGenRef.current) setFeaturesLoading(false);
        }

        if (gen !== loadGenRef.current) return;
        applyConfigFeatures(config, allFeatures);
        setConfigPhase({ phase: 'idle' });
    }, [applyConfigFeatures]);

    const resolveBoard = useCallback((
        config: BuildConfig,
        resolvedVehicle: Vehicle,
        resolvedVersion: Version,
        allBoards: Board[],
    ) => {
        const { setConfigPhase, setStep } = paramsRef.current;
        if (!config.board?.id) {
            setConfigPhase({ phase: 'idle' });
            setStep('board');
            return;
        }
        const match = allBoards.find(b => b.id === config.board!.id);
        if (match) {
            proceedAfterBoard(config, resolvedVehicle, resolvedVersion, match);
        } else {
            setConfigPhase({
                phase: 'conflict',
                kind: 'board',
                config,
                available: allBoards.map(b => ({ id: b.id, name: b.name })),
            });
            setStep('vehicle');
        }
    }, [proceedAfterBoard]);

    const proceedAfterVersion = useCallback(async (
        config: BuildConfig,
        resolvedVehicle: Vehicle,
        resolvedVersion: Version,
    ) => {
        const { setConfigPhase } = paramsRef.current;
        setConfigPhase({ phase: 'loading', config });
        const allBoards = await loadBoards(resolvedVehicle, resolvedVersion);
        if (!allBoards) {
            setConfigPhase({ phase: 'idle' });
            return;
        }
        resolveBoard(config, resolvedVehicle, resolvedVersion, allBoards);
    }, [loadBoards, resolveBoard]);

    const resolveVersion = useCallback((
        config: BuildConfig,
        resolvedVehicle: Vehicle,
        allVersions: Version[],
    ) => {
        const { setConfigPhase, setStep } = paramsRef.current;
        if (!config.version?.id) {
            setConfigPhase({ phase: 'idle' });
            setStep('version');
            return;
        }
        const match = allVersions.find(v => v.id === config.version!.id);
        if (match) {
            proceedAfterVersion(config, resolvedVehicle, match);
        } else {
            setConfigPhase({
                phase: 'conflict',
                kind: 'version',
                config,
                available: allVersions.map(v => ({ id: v.id, name: v.name, badge: v.type })),
            });
            setStep('vehicle');
        }
    }, [proceedAfterVersion]);

    const proceedAfterVehicle = useCallback(async (
        config: BuildConfig,
        resolvedVehicle: Vehicle,
    ) => {
        const { setConfigPhase } = paramsRef.current;
        setConfigPhase({ phase: 'loading', config });
        const allVersions = await loadVersions(resolvedVehicle);
        if (!allVersions) {
            setConfigPhase({ phase: 'idle' });
            return;
        }
        resolveVersion(config, resolvedVehicle, allVersions);
    }, [loadVersions, resolveVersion]);

    const resolveVehicle = useCallback((config: BuildConfig, allVehicles: Vehicle[]) => {
        const { setConfigPhase } = paramsRef.current;
        const match = allVehicles.find(v => v.id === config.vehicle.id);
        if (match) {
            proceedAfterVehicle(config, match);
        } else {
            setConfigPhase({
                phase: 'conflict',
                kind: 'vehicle',
                config,
                available: allVehicles.map(v => ({ id: v.id, name: v.name })),
            });
        }
    }, [proceedAfterVehicle]);

    const startConfigLoad = useCallback(async (config: BuildConfig) => {
        const {
            reset, bumpLoadGen, loadGenRef, vehiclesRef, setConfigPhase, setVehicles, setError,
        } = paramsRef.current;
        reset();
        const gen = bumpLoadGen();

        let allVehicles = vehiclesRef.current;
        if (allVehicles.length === 0) {
            setConfigPhase({ phase: 'loading', config });
            try {
                allVehicles = await fetchVehicles();
                if (gen !== loadGenRef.current) return;
                setVehicles(allVehicles);
            } catch {
                if (gen !== loadGenRef.current) return;
                setError('Failed to fetch vehicles from server');
                setConfigPhase({ phase: 'idle' });
                return;
            }
        }

        if (gen !== loadGenRef.current) return;
        resolveVehicle(config, allVehicles);
    }, [resolveVehicle]);

    const handleConflictSelect = useCallback((id: string, configPhase: ConfigPhase) => {
        if (configPhase.phase !== 'conflict') return;
        const { kind, config } = configPhase;
        const {
            setConfigPhase, vehiclesRef, versionsRef, boardsRef, vehicle, version,
        } = paramsRef.current;
        setConfigPhase({ phase: 'loading', config });
        if (kind === 'vehicle') {
            const v = vehiclesRef.current.find(x => x.id === id)!;
            proceedAfterVehicle(config, v);
        } else if (kind === 'version') {
            const v = versionsRef.current.find(x => x.id === id)!;
            proceedAfterVersion(config, vehicle!, v);
        } else if (kind === 'board') {
            const b = boardsRef.current.find(x => x.id === id)!;
            proceedAfterBoard(config, vehicle!, version!, b);
        }
    }, [proceedAfterVehicle, proceedAfterVersion, proceedAfterBoard]);

    const handleConflictCancel = useCallback(() => {
        const { bumpLoadGen, setConfigPhase } = paramsRef.current;
        bumpLoadGen();
        setConfigPhase({ phase: 'idle' });
    }, []);

    return {
        startConfigLoad,
        applyConfigFeatures,
        handleConflictSelect,
        handleConflictCancel,
        loadVersions,
        loadBoards,
        loadDefaultFeatures,
    };
}
