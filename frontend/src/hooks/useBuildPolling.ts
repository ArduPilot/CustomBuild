import { useCallback, useEffect, useRef } from 'react';
import type { BuildState, FormStep } from '../types';
import { fetchBuild } from '../api';
import { isTerminal } from '../components/buildStatus';

interface UseBuildPollingOptions {
    setBuildProgress: (n: number) => void;
    setBuildState: (s: BuildState) => void;
    setStep: (s: FormStep) => void;
}

export function useBuildPolling({
    setBuildProgress,
    setBuildState,
    setStep,
}: UseBuildPollingOptions) {
    const pollRef = useRef<ReturnType<typeof setTimeout>>();
    const doneTimeoutRef = useRef<ReturnType<typeof setTimeout>>();
    const pollingBuildIdRef = useRef<string | null>(null);
    const pendingDoneBuildIdRef = useRef<string | null>(null);
    const settersRef = useRef({ setBuildProgress, setBuildState, setStep });
    settersRef.current = { setBuildProgress, setBuildState, setStep };

    const clearBuildTimers = useCallback(() => {
        clearTimeout(pollRef.current);
        clearTimeout(doneTimeoutRef.current);
        pollRef.current = undefined;
        doneTimeoutRef.current = undefined;
    }, []);

    const stopBuildPolling = useCallback(() => {
        clearBuildTimers();
        pollingBuildIdRef.current = null;
        pendingDoneBuildIdRef.current = null;
    }, [clearBuildTimers]);

    const startPolling = useCallback((id: string) => {
        clearBuildTimers();
        pendingDoneBuildIdRef.current = null;
        pollingBuildIdRef.current = id;

        const tick = async () => {
            if (pollingBuildIdRef.current !== id) return;
            try {
                const b = await fetchBuild(id);
                if (pollingBuildIdRef.current !== id) return;
                const { setBuildProgress: setProg, setBuildState: setState } = settersRef.current;
                setProg(b.progress.percent);
                setState(b.progress.state);
                if (isTerminal(b.progress.state)) {
                    pollingBuildIdRef.current = null;
                    pendingDoneBuildIdRef.current = id;
                    doneTimeoutRef.current = setTimeout(() => {
                        if (pendingDoneBuildIdRef.current !== id) return;
                        pendingDoneBuildIdRef.current = null;
                        settersRef.current.setStep('done');
                    }, 1800);
                    return;
                }
            } catch { /* stay on building */ }
            if (pollingBuildIdRef.current !== id) return;
            pollRef.current = setTimeout(tick, 2000);
        };

        pollRef.current = setTimeout(tick, 0);
    }, [clearBuildTimers]);

    useEffect(() => () => stopBuildPolling(), [stopBuildPolling]);

    return { startPolling, stopBuildPolling };
}
