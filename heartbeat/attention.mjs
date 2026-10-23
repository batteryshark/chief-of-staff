// Future genuine requests only. No callback, effect execution, chief prompt or goal control.
import { state } from './bus.mjs';

export function attentionDelivery(options, { run } = {}) {
  return async ({ bus, event, text }) => {
    const original = state(await bus.rows()).events.find(e => e.id === event);
    if (!original || original.closed) throw Error('Original attention event missing/closed');
    if (original.urgency === 'fyi') return { status: 'quiet-fyi' };
    // The durable event is already visible in the chief inbox. Never create a
    // principal card from origin/dispatcher prose, including urgent requests.
    // Historical cards and uncertain attempts remain untouched for reconciliation.
    return { status: 'chief-judgment-pending', event: original.id };
  };
}
