import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import fs from 'fs'

const buildTime = new Date().toISOString().replace('T', ' ').slice(0, 19)

export default defineConfig({
    plugins: [
        vue(),
        {
            name: 'write-version',
            closeBundle() {
                // Called after bundle is written to disk
                const outDir = 'dist'
                if (!fs.existsSync(outDir)) fs.mkdirSync(outDir, { recursive: true })
                const ver = JSON.stringify({ build_time: buildTime, version: buildTime.slice(0, 10) + '-' + buildTime.slice(11, 16).replace(':', '') }, null, 2)
                fs.writeFileSync(outDir + '/version.json', ver)
                console.log('📦 Build version written:', buildTime)
            }
        }
    ],
    define: {
        __BUILD_TIME__: JSON.stringify(buildTime),
    },
    server: {
        port: 5173,
        proxy: {
            '/api': {
                target: 'http://localhost:8080',
                changeOrigin: true,
            }
        }
    },
    build: {
        outDir: 'dist',
    }
})
