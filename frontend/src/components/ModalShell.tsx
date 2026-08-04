import { useEffect, useRef, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import clsx from 'clsx';

const FOCUSABLE =
    'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

interface ModalShellProps {
    children: ReactNode;
    panelClassName?: string;
    backdropStyle?: CSSProperties;
    onClose?: () => void;
    /** Separate absolute backdrop layer (conflict modal layout). */
    separateBackdrop?: boolean;
    ariaLabelledBy?: string;
}

export function ModalShell({
    children,
    panelClassName,
    backdropStyle = { background: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)' },
    onClose,
    separateBackdrop = false,
    ariaLabelledBy,
}: ModalShellProps) {
    const closeRef = useRef(onClose);
    closeRef.current = onClose;
    const panelRef = useRef<HTMLDivElement>(null);
    const previousFocusRef = useRef<HTMLElement | null>(null);

    useEffect(() => {
        const prev = document.body.style.overflow;
        document.body.style.overflow = 'hidden';
        return () => { document.body.style.overflow = prev; };
    }, []);

    useEffect(() => {
        previousFocusRef.current = document.activeElement as HTMLElement | null;
        const panel = panelRef.current;
        if (!panel) return;

        const focusables = () =>
            Array.from(panel.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
                el => !el.hasAttribute('disabled') && el.offsetParent !== null,
            );

        const initial = focusables();
        (initial[0] ?? panel).focus();

        function onKeyDown(e: KeyboardEvent) {
            if (e.key === 'Escape') {
                e.stopPropagation();
                closeRef.current?.();
                return;
            }
            if (e.key !== 'Tab' || !panelRef.current) return;

            const nodes = focusables();
            if (nodes.length === 0) {
                e.preventDefault();
                panelRef.current.focus();
                return;
            }
            const first = nodes[0];
            const last = nodes[nodes.length - 1];
            if (e.shiftKey && document.activeElement === first) {
                e.preventDefault();
                last.focus();
            } else if (!e.shiftKey && document.activeElement === last) {
                e.preventDefault();
                first.focus();
            }
        }

        document.addEventListener('keydown', onKeyDown);
        return () => {
            document.removeEventListener('keydown', onKeyDown);
            previousFocusRef.current?.focus?.();
        };
    }, []);

    function handleBackdropClick() {
        closeRef.current?.();
    }

    return createPortal(
        <div
            className="fixed inset-0 z-50 flex items-center justify-center p-4"
            style={separateBackdrop ? undefined : backdropStyle}
            onClick={separateBackdrop ? undefined : handleBackdropClick}
        >
            {separateBackdrop && (
                <div
                    className="absolute inset-0 bg-black/60 backdrop-blur-sm"
                    onClick={handleBackdropClick}
                />
            )}
            <div
                ref={panelRef}
                role="dialog"
                aria-modal="true"
                aria-labelledby={ariaLabelledBy}
                tabIndex={-1}
                className={clsx(
                    'relative flex flex-col overflow-hidden animate-in outline-none',
                    panelClassName,
                )}
                onClick={e => e.stopPropagation()}
            >
                {children}
            </div>
        </div>,
        document.body,
    );
}
