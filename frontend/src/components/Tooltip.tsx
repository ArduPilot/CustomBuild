import { useState, useRef, useEffect, useId, cloneElement, type ReactElement } from 'react';
import { createPortal } from 'react-dom';

interface TooltipProps {
    text: string;
    children: ReactElement;
}

export function Tooltip({ text, children }: TooltipProps) {
    const [pos, setPos] = useState<{ top: number; left: number } | null>(null);
    const wrapperRef = useRef<HTMLSpanElement | null>(null);
    const tooltipId = useId();

    function updatePos() {
        if (!wrapperRef.current) return;
        const r = wrapperRef.current.getBoundingClientRect();
        const left = Math.min(
            Math.max(r.left + r.width / 2, 48),
            window.innerWidth - 48,
        );
        setPos({ top: r.top - 8, left });
    }

    useEffect(() => {
        if (!pos) return;
        const onReposition = () => updatePos();
        window.addEventListener('scroll', onReposition, true);
        window.addEventListener('resize', onReposition);
        return () => {
            window.removeEventListener('scroll', onReposition, true);
            window.removeEventListener('resize', onReposition);
        };
    }, [pos]);

    const child = cloneElement(children, {
        'aria-describedby': pos ? tooltipId : undefined,
    } as Record<string, unknown>);

    return (
        <>
            <span
                ref={wrapperRef}
                className="inline-block"
                onMouseEnter={updatePos}
                onMouseLeave={() => setPos(null)}
                onFocus={e => {
                    if ((e.target as HTMLElement).matches(':focus-visible')) updatePos();
                }}
                onBlur={() => setPos(null)}
                onPointerDown={() => setPos(null)}
                onClick={() => setPos(null)}
            >
                {child}
            </span>
            {pos && createPortal(
                <div
                    id={tooltipId}
                    role="tooltip"
                    style={{ top: pos.top, left: pos.left }}
                    className="pointer-events-none fixed z-[9999] -translate-x-1/2 -translate-y-full"
                >
                    <div className="bg-surface-1 border border-surface-4 text-gray-200 text-xs font-medium px-2.5 py-1.5 rounded-lg shadow-lg whitespace-nowrap mb-1.5">
                        {text}
                    </div>
                    <div
                        className="absolute left-1/2 -translate-x-1/2 top-full w-0 h-0"
                        style={{ borderLeft: '5px solid transparent', borderRight: '5px solid transparent', borderTop: `5px solid rgb(var(--s4))` }}
                    />
                </div>,
                document.body
            )}
        </>
    );
}
