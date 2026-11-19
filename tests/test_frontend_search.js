const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');

const source = fs.readFileSync('static/app.js', 'utf8');
const start = source.indexOf('function shareHealthcareSearch(');
const end = source.indexOf('\nfunction searchHealthcare(', start);
assert.notEqual(start, -1, 'deduplication helper is present in app.js');
assert.notEqual(end, -1, 'deduplication helper ends before the search handler');
const helper = source.slice(start, end);

test('identical in-flight finder searches share one request', async () => {
  const requests = new Map();
  const run = new Function('inFlightHealthcareSearches', `${helper}; return shareHealthcareSearch;`)(requests);
  let starts = 0;
  let finish;
  const first = run('23.8,90.4,3000,all', () => {
    starts += 1;
    return new Promise(resolve => { finish = resolve; });
  });
  const duplicate = run('23.8,90.4,3000,all', () => {
    starts += 1;
    return Promise.resolve('unexpected');
  });
  assert.equal(first, duplicate);
  await Promise.resolve();
  assert.equal(starts, 1);
  finish('done');
  assert.equal(await first, 'done');
  await Promise.resolve();
  assert.equal(requests.size, 0);
});

test('failed search is removed so only a user initiated search can retry', async () => {
  const requests = new Map();
  const run = new Function('inFlightHealthcareSearches', `${helper}; return shareHealthcareSearch;`)(requests);
  let starts = 0;
  await assert.rejects(run('same-key', async () => {
    starts += 1;
    throw new Error('unavailable');
  }), /unavailable/);
  await run('same-key', async () => {
    starts += 1;
    return 'manual retry';
  });
  assert.equal(starts, 2);
});
