// Offline DOM contract harness. These selectors are synthetic, not ClassPass selectors.
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const code = fs.readFileSync(path.join(__dirname, '..', 'capture_food.js'), 'utf8');

async function capture(options = {}) {
  const output = [];
  let reads = 0, dates = 0, urls = 0;
  const selectors = {confirm_food_context: true, scope: '.example-item', item_name: '.name',
    date: '.date', slot_rows: '.slot', slot_time: '.time', slot_credits: '.credits',
    slot_action: '.action', policy: '.policy'};
  if (options.scheduleRows) Object.assign(selectors, {layout: 'schedule_rows', item_exact_name: 'Example Lunch Bowl'});
  const source = 'https://classpass.com/studios/example-food-venue';
  const text = value => ({innerText: value});
  const slot = {querySelector(selector) {
    if (selector === '.time') return text('12:00 PM EST 60 min');
    if (selector === '.name') return text('Example Lunch Bowl');
    if (selector === '.credits') return options.missingPrice ? null : text('6 credits');
    if (selector === '.action') return {disabled: false, getAttribute: () => null};
    return null;
  }};
  const item = {
    querySelector: selector => selector === '.name' ? text('Example Lunch Bowl') :
      selector === '.policy' ? text('Orders cannot be cancelled. Credits will not be refunded.') : null,
    querySelectorAll: () => options.empty ? [] : options.scheduleRows ? [slot, {
      querySelector: selector => selector === '.name' ? text('Other Menu Item') :
        selector === '.credits' ? text('1 credit') : text('12:00 PM EST 60 min')
    }] : [slot]
  };
  const context = {URL, Date, nodeRepl: {write: value => output.push(value)},
    tab: {url: async () => ++urls > 1 && options.navigate ? source + '/changed' : options.url || source,
      playwright: {locator: selector => ({
        innerText: async () => {
          reads++;
          if (selector === 'h1') return 'Example Cafe';
          if (selector === '.date') return ++dates > 1 && options.changeDate ? 'Sat, Nov 14' : 'Fri, Nov 13';
          throw Error('Unexpected synthetic locator');
        },
        evaluate: async (fn, arg) => {
          reads++;
          if (selector === 'body') return fn(text(options.appOnly ?
            'Ordering is only available on our iOS app. PRIVATE_BODY_MARKER' : 'Food menu PRIVATE_BODY_MARKER'));
          if (selector === '.example-item') return fn(item, arg);
          throw Error('Unexpected synthetic selector');
        }
      })}}};
  if (!options.noMapping) context.foodSelectors = selectors;
  try {await vm.runInNewContext('(async () => {\n' + code + '\n})()', context);}
  catch (error) {return {error, output, reads};}
  return {output, reads};
}

test('captures one selected item and its per-slot quote only', async () => {
  const result = await capture();
  assert.equal(result.error, undefined);
  const data = JSON.parse(result.output[0]);
  assert.equal(data.capture_type, 'food_item_schedule');
  assert.equal(data.item_name, 'Example Lunch Bowl');
  assert.equal(data.rows[0].credits_text, '6 credits');
  assert.doesNotMatch(result.output[0], /PRIVATE_BODY_MARKER/);
});

test('requires observed food selectors rather than guessing ScheduleItem', async () => {
  const result = await capture({noMapping: true});
  assert.ok(result.error);
  assert.equal(result.output.length, 0);
});

test('studio schedule layout matches the exact item before reading its quote', async () => {
  const result = await capture({scheduleRows: true});
  assert.equal(result.error, undefined);
  const data = JSON.parse(result.output[0]);
  assert.equal(data.rows.length, 1);
  assert.equal(data.rows[0].credits_text, '6 credits');
  assert.equal(data.item_name, 'Example Lunch Bowl');
});

test('app-only notice is exported without fabricated slots or item context', async () => {
  const result = await capture({appOnly: true, noMapping: true});
  assert.equal(result.error, undefined);
  const data = JSON.parse(result.output[0]);
  assert.equal(data.availability, 'app_only');
  assert.deepEqual(data.rows, []);
  assert.equal(data.item_name, null);
});

test('unsupported or sensitive source URL fails before DOM reads', async () => {
  for (const url of ['https://evil.test/studios/a', 'https://classpass.com/studios/a?token=PRIVATE',
    'https://classpass.com/search/a', 'https://classpass.com/studios/a#PRIVATE']) {
    const result = await capture({url});
    assert.ok(result.error);
    assert.equal(result.reads, 0);
    assert.equal(result.output.length, 0);
    assert.doesNotMatch(result.error.message, /PRIVATE/);
  }
});

test('date change, navigation and zero slots stop without output', async () => {
  for (const option of [{changeDate: true}, {navigate: true}, {empty: true}]) {
    const result = await capture(option);
    assert.ok(result.error);
    assert.equal(result.output.length, 0);
  }
});

test('missing current quote stays null rather than copying another item price', async () => {
  const result = await capture({missingPrice: true});
  assert.equal(result.error, undefined);
  assert.equal(JSON.parse(result.output[0]).rows[0].credits_text, null);
});
