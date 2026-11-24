// Run with: node backend/tests/report_query_browser.cjs <rendered-query-page.html>
// Uses the frontend's existing jsdom dependency; all requests are intercepted.
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const { createRequire } = require('node:module');
const { test } = require('node:test');
const frontendRequire = createRequire(path.resolve(__dirname, '../../frontend/package.json'));
const { JSDOM } = frontendRequire('jsdom');
const html = fs.readFileSync(process.argv[2], 'utf8');
const origin = 'https://lab.example.com.cn';
const hex = 'ab'.repeat(32);
const legacy = Buffer.from(hex, 'hex').toString('base64url');
const random32 = 'cd'.repeat(16);

for (const [name, url, token] of [
  ['32-character path QR', `${origin}/s/v1/${random32}`, random32],
  ['previous 64-character path QR', `${origin}/s/v1/${hex}`, hex],
  ['previous fragment QR', `${origin}/api/report-publication/query#${legacy}`, legacy],
]) {
  test(name + ' shows the same facts and formal status without enabling downloads', async () => {
    let calls = 0;
    const dom = new JSDOM(html, {
      url, runScripts: 'dangerously',
      beforeParse(window) {
        window.fetch = async (endpoint, options) => {
          calls++;
          assert.equal(endpoint, '/api/report-publication/lookup');
          assert.equal(options.method, 'POST');
          assert.equal(options.credentials, 'omit');
          assert.deepEqual(JSON.parse(options.body), { token });
          return { status: 200, ok: true, json: async () => ({ code: 0, data: {
            reportNo: 'TEST-QR-001', validity: '正式报告', downloadAllowed: false,
            facts: { reportKind: 'inspection', reportTitle: '检测报告', client: '<b>虚拟客户</b>',
              projectName: '虚拟工程', sampleName: '虚拟样品', model: 'MODEL-1',
              quantity: '2', testItems: '虚拟项目', issueDate: '2026年10月16日' },
          } }) };
        };
      },
    });
    await new Promise(resolve => setImmediate(resolve));
    const document = dom.window.document;
    assert.equal(calls, 1);
    assert.equal(document.querySelector('#result').textContent, '正式报告');
    assert.equal(document.querySelector('#details').hidden, false);
    assert.equal(document.querySelectorAll('#details dt').length, 9);
    assert.equal(document.querySelector('#details b'), null);
    assert.match(document.querySelector('#details').textContent, /<b>虚拟客户<\/b>/);
    assert.equal(document.querySelector('#download').hidden, true);
    if (name === 'previous fragment QR') assert.equal(dom.window.location.hash, '');
    dom.window.close();
  });
}

test('revoked or unknown short QR presents no report details', async () => {
  const dom = new JSDOM(html, {
    url: `${origin}/s/v1/${random32}`, runScripts: 'dangerously',
    beforeParse(window) { window.fetch = async () => ({ status: 404, ok: false }); },
  });
  await new Promise(resolve => setImmediate(resolve));
  assert.match(dom.window.document.querySelector('#result').textContent, /未查询到/);
  assert.equal(dom.window.document.querySelector('#details').hidden, true);
  dom.window.close();
});
