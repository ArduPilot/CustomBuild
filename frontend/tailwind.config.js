/** @type {import('tailwindcss').Config} */
export default {
    content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
    theme: {
        extend: {
            colors: {
                yellow: {
                    400: '#FACC15',
                    500: '#EAB308',
                },
                surface: {
                    DEFAULT: 'rgb(var(--s) / <alpha-value>)',
                    1: 'rgb(var(--s1) / <alpha-value>)',
                    2: 'rgb(var(--s2) / <alpha-value>)',
                    3: 'rgb(var(--s3) / <alpha-value>)',
                    4: 'rgb(var(--s4) / <alpha-value>)',
                },
                hover: 'var(--hover-fill)',
                skeleton: 'rgb(var(--skeleton) / <alpha-value>)',
                gray: {
                    100: 'rgb(var(--g100) / <alpha-value>)',
                    200: 'rgb(var(--g200) / <alpha-value>)',
                    300: 'rgb(var(--g300) / <alpha-value>)',
                    400: 'rgb(var(--g400) / <alpha-value>)',
                    500: 'rgb(var(--g500) / <alpha-value>)',
                    600: 'rgb(var(--g600) / <alpha-value>)',
                    700: 'rgb(var(--g700) / <alpha-value>)',
                    800: 'rgb(var(--g800) / <alpha-value>)',
                    900: 'rgb(var(--g900) / <alpha-value>)',
                },
            },
            fontFamily: {
                sans: ['Space Grotesk', 'system-ui', 'sans-serif'],
                mono: ['JetBrains Mono', 'monospace'],
            },
            boxShadow: {
                'yellow-lg': '0 0 28px rgba(250, 204, 21, 0.10)',
                'inner-top': 'inset 0 1px 0 rgba(255,255,255,0.06)',
            },
        },
    },
}
