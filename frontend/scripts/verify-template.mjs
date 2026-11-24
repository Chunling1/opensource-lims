import { readFile, readdir } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const root = fileURLToPath(new URL('../', import.meta.url))
const forbidden = [
  { name: 'commercial template asset path', regex: /\/template\// },
  { name: 'commercial SimpleBar reference', regex: /\bSimpleBar\b/ },
  { name: 'commercial Waves reference', regex: /\bWaves\b/ },
  { name: 'non-Tabler icon class', regex: /\b(?:ri-[a-z0-9-]+|bx-[a-z0-9-]+|mdi-[a-z0-9-]+)\b/ },
]

const failures = []
const indexHtml = await readFile(path.join(root, 'index.html'), 'utf8')
for (const rule of forbidden) {
  if (rule.regex.test(indexHtml)) failures.push(`index.html contains ${rule.name}`)
}

async function scan(dir) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name)
    if (entry.isDirectory()) await scan(full)
    else if (/\.(vue|ts|css)$/.test(entry.name) && !entry.name.endsWith('.test.ts')) {
      const content = await readFile(full, 'utf8')
      const rel = path.relative(root, full).replaceAll('\\', '/')
      for (const rule of forbidden) {
        if (rule.regex.test(content)) failures.push(`${rel} contains ${rule.name}`)
      }
    }
  }
}

await scan(path.join(root, 'src'))
if (failures.length) {
  throw new Error(`Tabler open-source hygiene check failed:\n${failures.join('\n')}`)
}
console.log('PASS: Tabler migration hygiene check passed (zero commercial template, SimpleBar, Waves, or non-Tabler icon references).')
