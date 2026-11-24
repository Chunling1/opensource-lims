import {defineConfig} from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import {fileURLToPath} from 'node:url'
export default defineConfig({plugins:[vue()],resolve:{alias:{'@':fileURLToPath(new URL('./src/modules',import.meta.url)),'element-plus':fileURLToPath(new URL('./src/platformUi/controls.ts',import.meta.url)),'@element-plus/icons-vue':fileURLToPath(new URL('./src/platformUi/icons.ts',import.meta.url))}},test:{include:['src/platformUi/**/*.test.ts'],environment:'jsdom'}})
