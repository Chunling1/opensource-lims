import { readFile, readdir } from 'node:fs/promises'
import { createHash } from 'node:crypto'
import path from 'node:path'
import * as sass from 'sass'
import postcss from 'postcss'
import { adaptTemplateCss } from './template-css.mjs'
const hash = data => createHash('sha256').update(data).digest('hex')
async function walk(dir) {
  return (await Promise.all((await readdir(dir, { withFileTypes: true })).map(e => e.isDirectory() ? walk(path.join(dir, e.name)) : path.join(dir, e.name)))).flat()
}
for (const file of await walk('src')) {
  const content = await readFile(file, 'utf8')
  if (/\.(css|scss|sass|less)$/.test(file) || /<style\b|\s(?::|v-bind:)?style\s*=|\.style\s*[.[]|setAttribute\(['"]style/.test(content)) throw new Error(`Business CSS is forbidden: ${file}`)
}
const manifest = JSON.parse(await readFile('public/template/manifest.json', 'utf8'))
const previews = JSON.parse(await readFile('src/assets/theme/preview-sources.json', 'utf8'))
for (const preview of previews.images) {
  if (hash(await readFile(path.join('public/theme-previews', preview.file))) !== preview.sha256) throw new Error(`Theme preview mismatch: ${preview.file}`)
}
for (const [file, expected] of Object.entries(manifest.sources)) {
  if (hash(await readFile(path.join('docs/HTML/Master', file))) !== expected) throw new Error(`Template source changed: ${file}`)
}
for (const [file, expected] of Object.entries(manifest.copied)) {
  for (const base of ['docs/HTML/Master/dist/assets', 'public/template/assets']) {
    if (hash(await readFile(path.join(base, file))) !== expected) throw new Error(`Asset mismatch: ${file}`)
  }
}
for (const [file, resource] of Object.entries(manifest.npm || {})) {
  const packageRoot = path.join('node_modules', resource.package)
  const installed = JSON.parse(await readFile(path.join(packageRoot, 'package.json'), 'utf8'))
  if (installed.version !== resource.version) throw new Error(`Vendor version mismatch: ${resource.package}`)
  for (const source of [path.join(packageRoot, resource.source), path.join('public/template/assets', file)]) {
    if (hash(await readFile(source)) !== resource.sha256) throw new Error(`Vendor asset mismatch: ${source}`)
  }
}
for (const [file, expected] of Object.entries(manifest.generated)) {
  if (hash(await readFile(path.join('public/template/assets', file))) !== expected) throw new Error(`Generated CSS changed: ${file}`)
  const name = path.basename(file).replace('.min.css', '')
  const rebuilt = sass.compile(path.resolve(`docs/HTML/Master/src/assets/scss/${name}.scss`), {
    style: 'compressed', loadPaths: [process.cwd()], quietDeps: true, logger: { warn() {}, debug() {} }
  })
  if (hash(adaptTemplateCss(rebuilt.css)) !== expected) throw new Error(`Non-reproducible stylesheet: ${file}`)
}
for (const css of ['bootstrap', 'icons', 'app', 'custom']) {
  const file = path.resolve(`public/template/assets/css/${css}.min.css`)
  const references = []
  postcss.parse(await readFile(file, 'utf8')).walkDecls(declaration => {
    // Modern browsers use the last src descriptor; the template's earlier EOT
    // declarations are superseded by its WOFF declarations. Do not mutate CSS.
    if (declaration.prop === 'src' && declaration.parent.type === 'atrule' && declaration.parent.name === 'font-face') {
      const sources = declaration.parent.nodes.filter(node => node.type === 'decl' && node.prop === 'src')
      if (sources.at(-1) !== declaration) return
    }
    for (const match of declaration.value.matchAll(/url\(\s*(?:"([^"]*)"|'([^']*)'|([^\s)]+))\s*\)/g)) {
      const url = match[1] ?? match[2] ?? match[3]
      if (!/^(data:|https?:|\/\/|#)/.test(url)) references.push(path.resolve(path.dirname(file), decodeURIComponent(url.split(/[?#]/)[0])))
    }
  })
  for (const reference of references) {
    await readFile(reference)
  }
}
console.log('PASS: no business CSS; template sources, copied resources, CSS reproducibility and local CSS asset references verified.')
