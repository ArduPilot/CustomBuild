import { ArrowDownToLine, Cpu, FileText } from 'lucide-react';
import clsx from 'clsx';
import type { StandardArtifact } from '../types';
import { FormSection } from './StepComponents';

const FIRMWARE_FORMATS = new Set(['bin', 'apj', 'elf', 'hex', '']);

const FORMAT_BADGE: Record<string, string> = {
    bin: 'bg-orange-500/20 text-orange-300 border border-orange-500/30',
    apj: 'bg-sky-500/20 text-sky-300 border border-sky-500/30',
    elf: 'bg-violet-500/20 text-violet-300 border border-violet-500/30',
    hex: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30',
    '': 'bg-orange-500/20 text-orange-300 border border-orange-500/30',
};
const DEFAULT_BADGE = 'bg-gray-500/20 text-gray-400 border border-gray-500/30';

function getBaseName(name: string) {
    const dot = name.lastIndexOf('.');
    return dot === -1 ? name : name.slice(0, dot);
}

function ArtifactCard({ artifact }: { artifact: StandardArtifact }) {
    const format = artifact.format.toLowerCase();
    const isFirmware = FIRMWARE_FORMATS.has(format);
    const formatLabel = format.toUpperCase() || 'BIN';
    const badgeCls = FORMAT_BADGE[format] ?? DEFAULT_BADGE;
    return (
        <a
            href={artifact.url}
            target="_blank"
            rel="noopener noreferrer"
            className={clsx(
                'relative flex flex-col items-center justify-center gap-2 p-3 rounded-xl border border-surface-4 bg-surface-3',
                'hover:border-yellow-400/50 hover:bg-hover transition-all duration-150 group cursor-pointer',
            )}
        >
            <span className={clsx('absolute top-2 right-2 text-[9px] font-bold font-mono px-1.5 py-0.5 rounded-md', badgeCls)}>
                {formatLabel}
            </span>
            <div className="text-gray-500 group-hover:text-yellow-400 transition-colors">
                {isFirmware
                    ? <Cpu className="w-7 h-7" />
                    : <FileText className="w-7 h-7" />}
            </div>
            <span className="font-mono text-[10px] text-gray-300 text-center leading-tight break-all line-clamp-2 w-full">
                {getBaseName(artifact.name)}
            </span>
            <ArrowDownToLine className="w-3.5 h-3.5 text-gray-600 group-hover:text-yellow-400 transition-colors shrink-0" />
        </a>
    );
}

export function StandardArtifactsGrid({ artifacts }: { artifacts: StandardArtifact[] }) {
    const firmwareArtifacts = artifacts.filter(a =>
        FIRMWARE_FORMATS.has(a.format.toLowerCase()),
    );
    const otherArtifacts = artifacts.filter(a =>
        !FIRMWARE_FORMATS.has(a.format.toLowerCase()),
    );

    return (
        <FormSection label="Standard build files">
            <div className="grid grid-cols-4 gap-2">
                {firmwareArtifacts.map(a => <ArtifactCard key={a.name} artifact={a} />)}
                {otherArtifacts.map(a => <ArtifactCard key={a.name} artifact={a} />)}
            </div>
        </FormSection>
    );
}
