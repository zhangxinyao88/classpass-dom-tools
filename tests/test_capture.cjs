// Offline harness only. Does not connect to a browser or ClassPass.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const script = fs.readFileSync(path.join(__dirname, '..', 'capture_search.js'), 'utf8');

async function capture(options = {}) {
  const output = [];
  let headings = 0, urlReads = 0, domReads = 0;
  const row = {querySelector(selector) {
    const qa = selector.match(/data-qa="([^"]+)"/)[1];
    const values = {
      'ScheduleItem.class.name': ['Example Yin Session', options.classPath || '/classes/example-studio/yin/123'],
      'ScheduleItem.venue-name': ['Example Yoga Studio', '/studios/example-studio'],
      'ScheduleItem.teacher-name': ['Example Teacher'],
      'ScheduleItem.time': ['4:30 PM60 min'],
      'Schedule.cta': [null, null, 'Reserve Example Yin Session for 5 credits']
    };
    const value = values[qa];
    return value ? {textContent: value[0], getAttribute: name =>
      name === 'href' ? value[1] : name === 'aria-label' ? value[2] : null} : null;
  }};
  const url = 'https://classpass.com/search/example-city/yoga-classes/example';
  const context = {
    URL, Date,
    tab: {
      url: async () => ++urlReads > 1 && options.changedUrl ? url + '/changed' : options.url || url,
      playwright: {
        getByRole: () => ({innerText: async () => {
          domReads++;
          return ++headings > 1 && options.changedHeading ? 'Live sessions for Sat, Nov 14' : 'Live sessions for Fri, Nov 13';
        }}),
        getByTestId: () => ({evaluateAll: async fn => {
          domReads++;
          return fn(options.emptyRows ? [] : [row]);
        }})
      }
    },
    nodeRepl: {write: value => output.push(value)}
  };
  try {
    await vm.runInNewContext('(async () => {\n' + script + '\n})()', context);
  } catch (error) {
    return {error, output, domReads};
  }
  return {output, domReads};
}

test('captures only observed card fields', async () => {
  const result = await capture();
  assert.equal(result.error, undefined);
  assert.equal(result.output.length, 1);
  const data = JSON.parse(result.output[0]);
  assert.equal(data.rows.length, 1);
  assert.equal(data.rows[0].displayed_action, 'Reserve Example Yin Session for 5 credits');
  assert.deepEqual(Object.keys(data), ['schema_version', 'source_url', 'captured_at', 'heading', 'rows']);
});

test('rejects sensitive or unsupported source URLs before DOM reads', async () => {
  for (const url of ['https://classpass.com/search/x?token=SECRET',
    'https://classpass.com/search/x#SECRET', 'https://evil.test/search/x',
    'https://user:SECRET@classpass.com/search/x']) {
    const result = await capture({url});
    assert.ok(result.error);
    assert.equal(result.domReads, 0);
    assert.equal(result.output.length, 0);
    assert.doesNotMatch(result.error.message, /SECRET/);
  }
});

test('rejects query-bearing class links without emitting capture data', async () => {
  const result = await capture({classPath: '/classes/example-studio/yin/123?token=SECRET'});
  assert.ok(result.error);
  assert.equal(result.output.length, 0);
  assert.doesNotMatch(result.error.message, /SECRET/);
});

test('rejects navigation or day change during capture', async () => {
  for (const option of [{changedUrl: true}, {changedHeading: true}]) {
    const result = await capture(option);
    assert.ok(result.error);
    assert.equal(result.output.length, 0);
  }
});

test('empty rendered rows do not become an availability claim', async () => {
  const result = await capture({emptyRows: true});
  assert.ok(result.error);
  assert.equal(result.output.length, 0);
});
