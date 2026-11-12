// Read-only, one selected food item. No guessed site-specific selectors.
// Bind tab normally. Bind foodSelectors from observed current DOM; see FOOD_ADAPTER.md.
{
const source = new URL(await tab.url());
if (source.origin !== 'https://classpass.com' || source.username || source.password ||
    source.search || source.hash || !/^\/studios\/[a-zA-Z0-9/_-]+$/.test(source.pathname))
  throw Error('Select a normal food studio page without query data.');
const venue = await tab.playwright.locator('h1').innerText();
const notices = await tab.playwright.locator('body').evaluate(body => {
  const text = body.innerText || '';
  return {
    challenge: /enable javascript and cookies|just a moment\.\.\./i.test(text),
    appOnly: /ordering is only available on our (?:iOS|Android|iOS\/Android) app/i.test(text)
  };
});
if (notices.challenge) throw Error('Access challenge; no food capture emitted.');
let item = null, dateHeading = null, rows = [], policy = null;
if (!notices.appOnly) {
  if (typeof foodSelectors !== 'object' || !foodSelectors || foodSelectors.confirm_food_context !== true)
    throw Error('Supply foodSelectors from the inspected food page first.');
  const fields = ['scope', 'item_name', 'date', 'slot_rows', 'slot_time', 'slot_credits'];
  for (const field of fields)
    if (typeof foodSelectors[field] !== 'string' || !foodSelectors[field] || foodSelectors[field].length > 500)
      throw Error('Incomplete observed food DOM mapping.');
  const mapping = {};
  for (const field of [...fields, 'slot_action', 'policy']) {
    const value = foodSelectors[field];
    if (value !== undefined && value !== null && (typeof value !== 'string' || value.length > 500))
      throw Error('Unsupported food selector.');
    mapping[field] = value || null;
  }
  if (foodSelectors.credits_attribute && foodSelectors.credits_attribute !== 'aria-label')
    throw Error('Only visible credit text or an aria-label is supported.');
  mapping.credits_attribute = foodSelectors.credits_attribute || null;
  mapping.layout = foodSelectors.layout || 'selected_item';
  if (!['selected_item', 'schedule_rows'].includes(mapping.layout))
    throw Error('Unsupported food layout.');
  mapping.item_exact_name = foodSelectors.item_exact_name || null;
  if (mapping.layout === 'schedule_rows' && (typeof mapping.item_exact_name !== 'string' ||
      !mapping.item_exact_name || mapping.item_exact_name.length > 500))
    throw Error('Supply the exact observed item name for schedule rows.');
  dateHeading = await tab.playwright.locator(mapping.date).innerText();
  const captured = await tab.playwright.locator(mapping.scope).evaluate((root, selectors) => {
    const clean = element => typeof element?.innerText === 'string' ? element.innerText.trim() : null;
    let slots = Array.from(root.querySelectorAll(selectors.slot_rows));
    if (selectors.layout === 'schedule_rows')
      slots = slots.filter(slot => clean(slot.querySelector(selectors.item_name)) === selectors.item_exact_name);
    if (!slots.length || slots.length > 500) throw Error('Unsupported selected-item slot count.');
    return {
      name: selectors.layout === 'schedule_rows' ? selectors.item_exact_name : clean(root.querySelector(selectors.item_name)),
      policy: selectors.policy ? clean(root.querySelector(selectors.policy)) : null,
      rows: slots.map(slot => {
        const credit = slot.querySelector(selectors.slot_credits);
        const action = selectors.slot_action ? slot.querySelector(selectors.slot_action) : null;
        return {
          time_text: clean(slot.querySelector(selectors.slot_time)),
          credits_text: selectors.credits_attribute === 'aria-label' ? credit?.getAttribute('aria-label') || null : clean(credit),
          action_disabled: action ? action.disabled === true || action.getAttribute('aria-disabled') === 'true' : null
        };
      })
    };
  }, mapping);
  item = captured.name; rows = captured.rows; policy = captured.policy;
  if (await tab.playwright.locator(mapping.date).innerText() !== dateHeading)
    throw Error('Selected food date changed; recapture.');
}
if (await tab.url() !== source.href) throw Error('Food page changed; no capture emitted.');
nodeRepl.write(JSON.stringify({schema_version: 1, capture_type: 'food_item_schedule',
  source_url: source.href, captured_at: new Date().toISOString(), venue,
  availability: notices.appOnly ? 'app_only' : 'web_schedule', item_name: item,
  date_heading: dateHeading, policy_text: policy, rows}));
}
