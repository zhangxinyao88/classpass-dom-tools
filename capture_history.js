// Run in the supported browser REPL, with the authorized history tab bound to tab.
{
const source = await tab.url();
if (source !== 'https://classpass.com/profile/past') throw new Error('Select the normal ClassPass past-history page.');
const countText = await tab.playwright.getByRole('link', {name:/^Past \(\d+\)$/}).innerText();
const match = /^Past \((\d+)\)$/.exec(countText);
if (!match) throw new Error('Unsupported history count.');
const rows = await tab.playwright.locator('[data-testid="ProfileBookingCard.reservation"], [data-testid="ProfileBookingCard.order"]').evaluateAll(cards => {
  if (!cards.length || cards.length > 1000) throw new Error('Unsupported history row count.');
  return cards.map(card => {
    const text = field => card.querySelector('[data-testid="ProfileBookingCard.'+field+'"]')?.textContent?.trim() || null;
    return {
      kind:card.getAttribute('data-testid') === 'ProfileBookingCard.order' ? 'order' : 'reservation',
      name:card.querySelector('h3')?.textContent?.trim() || null,
      date_text:text('date-time'), studio:text('studio-name'), credits_text:text('credits'),
      instructor:text('instructor-name'),
      rating_text:card.querySelector('[data-testid="ProfileBookingCard.star-rating"]')?.getAttribute('aria-label') || null
    };
  });
});
if (await tab.url() !== source || await tab.playwright.getByRole('link', {name:/^Past \(\d+\)$/}).innerText() !== countText)
  throw new Error('History changed during capture.');
nodeRepl.write(JSON.stringify({schema_version:1,source_url:source,captured_at:new Date().toISOString(),displayed_total:Number(match[1]),rows}));
}
