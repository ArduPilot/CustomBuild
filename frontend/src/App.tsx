import { useState, useRef, useEffect } from 'react';
import { Menu, X } from 'lucide-react';
import { BuildForm } from './components/BuildForm';
import { BuildsTable } from './components/BuildsTable';
import { HeroPanel } from './components/HeroPanel';
import { ThemeToggle } from './components/ThemeToggle';
import { type BuildConfig, configFromQueryParams } from './buildConfig';

const THEME_KEY = 'custombuild-theme';

const NAV_LINKS = [
    { href: 'https://ardupilot.org', label: 'ardupilot.org', external: true },
    { href: 'https://github.com/ArduPilot/CustomBuild', label: 'GitHub', external: true },
    { href: 'https://ardupilot.org/copter/docs/common-custom-firmware.html', label: 'Help', external: true },
    { href: '/api/docs', label: 'API Docs', external: false },
] as const;

function readInitialDark(): boolean {
    try {
        const stored = localStorage.getItem(THEME_KEY);
        if (stored === 'dark') return true;
        if (stored === 'light') return false;
    } catch { /* ignore */ }
    return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

function prefersReducedMotion(): boolean {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export default function App() {
    const [pendingConfig, setPendingConfig] = useState<BuildConfig | null>(null);
    const [isDark, setIsDark] = useState(readInitialDark);
    const [themeUserSet, setThemeUserSet] = useState(() => {
        try { return localStorage.getItem(THEME_KEY) !== null; }
        catch { return false; }
    });
    const [menuOpen, setMenuOpen] = useState(false);
    const formRef = useRef<HTMLDivElement>(null);

    useEffect(() => {
        const root = document.documentElement;
        if (isDark) {
            root.classList.remove('light');
        } else {
            root.classList.add('light');
        }
    }, [isDark]);

    useEffect(() => {
        if (themeUserSet) return;
        const mq = window.matchMedia('(prefers-color-scheme: dark)');
        const onChange = (e: MediaQueryListEvent) => setIsDark(e.matches);
        mq.addEventListener('change', onChange);
        return () => mq.removeEventListener('change', onChange);
    }, [themeUserSet]);

    useEffect(() => {
        const params = new URLSearchParams(window.location.search);
        const config = configFromQueryParams(params);
        if (config) {
            setPendingConfig(config);
            window.history.replaceState({}, '', window.location.pathname);
        }
    }, []);

    function toggleTheme() {
        setIsDark(d => {
            const next = !d;
            try { localStorage.setItem(THEME_KEY, next ? 'dark' : 'light'); }
            catch { /* ignore */ }
            return next;
        });
        setThemeUserSet(true);
    }

    function handleRebuild(config: BuildConfig) {
        setPendingConfig(config);
        formRef.current?.scrollIntoView({
            behavior: prefersReducedMotion() ? 'auto' : 'smooth',
            block: 'center',
        });
    }

    const linkClass = 'text-sm text-gray-500 hover:text-gray-300 transition-colors';

    return (
        <div className="min-h-screen bg-surface grid-bg relative overflow-x-hidden">
            <div className="absolute inset-x-0 top-0 h-64 pointer-events-none"
                style={{ background: 'radial-gradient(ellipse 70% 40% at 50% 0%, rgba(250,204,21,0.07), transparent 70%)' }}
            />

            <header className="relative z-10 border-b border-surface-4 bg-surface-1/80 backdrop-blur-md">
                <div className="max-w-7xl mx-auto px-6 md:px-10 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <img src="/ardupilot_logo.png" alt="ArduPilot" className="h-8 w-auto" />
                    </div>
                    <div className="flex items-center gap-3 md:gap-6">
                        <nav className="hidden md:flex items-center gap-6">
                            {NAV_LINKS.map(link => (
                                <a
                                    key={link.href}
                                    href={link.href}
                                    target={link.external ? '_blank' : undefined}
                                    rel={link.external ? 'noopener noreferrer' : undefined}
                                    className={linkClass}
                                >
                                    {link.label}
                                </a>
                            ))}
                        </nav>
                        <ThemeToggle isDark={isDark} onToggle={toggleTheme} />
                        <button
                            type="button"
                            className="md:hidden btn-ghost p-2"
                            aria-label={menuOpen ? 'Close menu' : 'Open menu'}
                            aria-expanded={menuOpen}
                            onClick={() => setMenuOpen(o => !o)}
                        >
                            {menuOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                        </button>
                    </div>
                </div>
                {menuOpen && (
                    <nav className="md:hidden border-t border-surface-4 px-6 py-3 flex flex-col gap-3 bg-surface-1">
                        {NAV_LINKS.map(link => (
                            <a
                                key={link.href}
                                href={link.href}
                                target={link.external ? '_blank' : undefined}
                                rel={link.external ? 'noopener noreferrer' : undefined}
                                className={linkClass}
                                onClick={() => setMenuOpen(false)}
                            >
                                {link.label}
                            </a>
                        ))}
                    </nav>
                )}
            </header>

            <main className="relative z-10 max-w-7xl mx-auto px-6 md:px-10">
                <div className="min-h-[calc(100vh-64px)] grid lg:grid-cols-2 gap-10 items-center py-14 lg:py-0">
                    <div className="hidden lg:block">
                        <HeroPanel />
                    </div>

                    <div className="lg:hidden text-center mb-2">
                        <h1 className="text-3xl font-bold text-white">
                            ArduPilot
                        </h1>
                        <p className="text-2xl font-bold text-logo-gradient mt-1">
                            CustomBuild
                        </p>
                        <p className="text-gray-500 text-sm mt-3 leading-relaxed">
                            Build exactly the firmware you need. Choose your vehicle, board, and feature set,
                            and we'll compile it for you.
                        </p>
                        <p className="text-logo-gradient text-base font-mono uppercase tracking-wider mt-4">
                            Versatile · Trusted · Open
                        </p>
                    </div>

                    <div className="lg:py-12" ref={formRef}>
                        <BuildForm
                            initialConfig={pendingConfig}
                            onConsumeInitialConfig={() => setPendingConfig(null)}
                        />
                    </div>
                </div>

                <div className="flex items-center gap-4 mt-4 mb-0">
                    <div className="flex-1 h-px bg-surface-4" />
                    <span className="text-xs text-gray-600 font-mono uppercase tracking-wider">All Builds</span>
                    <div className="flex-1 h-px bg-surface-4" />
                </div>
            </main>

            <div className="relative z-10">
                <BuildsTable onRebuild={handleRebuild} />
            </div>

            <footer className="relative z-10 border-t border-surface-4 py-8">
                <div className="max-w-7xl mx-auto px-6 md:px-10 flex items-center justify-between">
                    <span className="text-sm text-gray-600 font-mono">
                        ArduPilot Custom Firmware Builder
                    </span>
                    <div className="flex items-center gap-4">
                        <a
                            href="https://custom-beta.ardupilot.org"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                        >
                            Beta Site
                        </a>
                        <a
                            href="https://github.com/ArduPilot/CustomBuild/graphs/contributors"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-xs text-gray-500 hover:text-gray-300 transition-colors"
                        >
                            Contributors
                        </a>
                        <a
                            href="https://ardupilot.org/donate"
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-full border border-yellow-400/40 text-yellow-400 hover:bg-yellow-400/10 hover:border-yellow-400/70 transition-colors"
                        >
                            ♥ Donate
                        </a>
                        <span className="text-sm text-gray-700">GPL-3.0</span>
                    </div>
                </div>
            </footer>
        </div>
    );
}
