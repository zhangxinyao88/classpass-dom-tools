// Run through the documented cloud browser REPL, with an authorized tab bound.
// Reject sensitive/unsupported URLs before emitting any capture data.
{
const searchSource = new URL(await tab.url());
if (searchSource.origin !== 'https://classpass.com' || searchSource.username ||
    searchSource.password || searchSource.search || searchSource.hash ||
    !/^\/search\/[a-zA-Z0-9/_-]+$/.test(searchSource.pathname)) {
  throw new Error('Select a ClassPass search page without query parameters or fragments.');
}
const searchHeading = await tab.playwright.getByRole('heading', {name: /^Live sessions for /}).innerText();
const searchRows = await tab.playwright.getByTestId('ScheduleItem').evaluateAll(rows => {
  if (!rows.length || rows.length > 1000) throw new Error('Unsupported search row count.');
  return rows.map(row => {
    const text = qa => row.querySelector('[data-qa="' + qa + '"]')?.textContent?.trim() || null;
    const link = (qa, prefix) => {
      const path = row.querySelector('[data-qa="' + qa + '"]')?.getAttribute('href') || null;
      if (path !== null && !new RegExp('^/' + prefix + '/[a-zA-Z0-9/_-]+$').test(path)) {
        throw new Error('Unsupported card link; no capture data was emitted.');
      }
      return path;
    };
    return {
      name: text('ScheduleItem.class.name'),
      class_path: link('ScheduleItem.class.name', 'classes'),
      studio: text('ScheduleItem.venue-name'),
      studio_path: link('ScheduleItem.venue-name', 'studios'),
      instructor: text('ScheduleItem.teacher-name'),
      time_text: text('ScheduleItem.time'),
      displayed_action: row.querySelector('[data-qa="Schedule.cta"]')?.getAttribute('aria-label') || null
    };
  });
});
const searchHeadingAfter = await tab.playwright.getByRole('heading', {name: /^Live sessions for /}).innerText();
if (searchHeadingAfter !== searchHeading || await tab.url() !== searchSource.href) {
  throw new Error('Search page changed during capture; wait for a stable page and recapture.');
}
const searchCapture = {
  schema_version: 1,
  source_url: searchSource.href,
  captured_at: new Date().toISOString(),
  heading: searchHeading,
  rows: searchRows
};
nodeRepl.write(JSON.stringify(searchCapture));
}
