import { cpSync, mkdirSync } from 'fs'
import { dirname, resolve } from 'path'
import { fileURLToPath } from 'url'
import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'

const rootDir = dirname(fileURLToPath(import.meta.url))

/** Copy shared schemas/config into public so /schemas/config/*.json is served. */
function copySharedSchemas(): Plugin {
    const src = resolve(rootDir, '../schemas/config')
    const dest = resolve(rootDir, 'public/schemas/config')
    const copy = () => {
        mkdirSync(dest, { recursive: true })
        cpSync(src, dest, { recursive: true })
    }
    return {
        name: 'copy-shared-schemas',
        buildStart() {
            copy()
        },
        configureServer() {
            copy()
        },
    }
}

export default defineConfig({
    plugins: [react(), copySharedSchemas()],
    server: {
        proxy: {
            '/api': {
                target: 'http://localhost:8080',
                changeOrigin: true,
            },
        },
    },
})
