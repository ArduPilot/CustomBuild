import { useState, useRef, useCallback, useId, type ReactNode } from 'react';
import { UploadCloud, FileText, AlertTriangle } from 'lucide-react';
import clsx from 'clsx';

interface ConfigDropZoneProps {
    onLoad: (yamlText: string, fileName: string) => void;
    title?: string;
    hint?: ReactNode;
}

export function ConfigDropZone({
    onLoad,
    title = 'Load config file',
    hint,
}: ConfigDropZoneProps) {
    const secondaryHint = hint ?? (
        <>
            Drag & drop or click · <span className="font-mono">.yaml</span> /{' '}
            <span className="font-mono">.yml</span>
        </>
    );
    const [dragging, setDragging] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const onLoadRef = useRef(onLoad);
    onLoadRef.current = onLoad;
    const inputId = useId();

    const readFile = useCallback((file: File) => {
        if (!file.name.match(/\.(yaml|yml)$/i)) {
            setError('Only .yaml or .yml files are supported');
            return;
        }
        setError(null);
        const reader = new FileReader();
        reader.onload = e => onLoadRef.current((e.target?.result as string) ?? '', file.name);
        reader.onerror = () => setError('Failed to read file');
        reader.readAsText(file);
    }, []);

    const onDrop = useCallback((e: React.DragEvent<HTMLLabelElement>) => {
        e.preventDefault();
        setDragging(false);
        const file = e.dataTransfer.files[0];
        if (file) readFile(file);
    }, [readFile]);

    const onDragOver = (e: React.DragEvent<HTMLLabelElement>) => {
        e.preventDefault();
        setDragging(true);
    };
    const onDragLeave = () => setDragging(false);

    const onInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const file = e.target.files?.[0];
        if (file) readFile(file);
        e.target.value = '';
    };

    return (
        <div className="space-y-2">
            <label
                htmlFor={inputId}
                onDrop={onDrop}
                onDragOver={onDragOver}
                onDragLeave={onDragLeave}
                className={clsx(
                    'relative flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-6 cursor-pointer transition-all duration-200',
                    'focus-within:ring-2 focus-within:ring-yellow-400/50 focus-within:border-yellow-400',
                    dragging
                        ? 'border-yellow-400 bg-yellow-400/10 scale-[1.01]'
                        : 'border-surface-4 bg-surface-3 hover:border-yellow-400/50 hover:bg-hover',
                )}
            >
                <input
                    id={inputId}
                    type="file"
                    accept=".yaml,.yml"
                    className="sr-only"
                    onChange={onInputChange}
                />
                {dragging ? (
                    <FileText className="w-7 h-7 text-yellow-400" aria-hidden />
                ) : (
                    <UploadCloud className="w-7 h-7 text-gray-500" aria-hidden />
                )}
                <div className="text-center">
                    <p className="text-sm font-medium text-gray-300">
                        {dragging ? 'Drop config here' : title}
                    </p>
                    <p className="text-xs text-gray-500 mt-0.5">{secondaryHint}</p>
                </div>
            </label>
            {error && (
                <p className="flex items-center gap-1.5 text-xs text-red-400 px-1" role="alert">
                    <AlertTriangle className="w-3 h-3 shrink-0" />
                    {error}
                </p>
            )}
        </div>
    );
}
