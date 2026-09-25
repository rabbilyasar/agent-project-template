import { TtlCache } from "./cache.js";

export interface Widget {
  id: string;
  name: string;
}

const WIDGET_CACHE_TTL_MS = 1000;
const widgetCache = new TtlCache<Widget[]>();

const ALL_WIDGETS: Widget[] = [
  { id: "w1", name: "Alpha" },
  { id: "w2", name: "Beta" },
];

// REQ-010 (docs/requirements.md): rate limiting is accepted but not yet
// implemented here.
export function listWidgets(clientId: string): Widget[] {
  const cached = widgetCache.get(clientId);
  if (cached) return cached;

  const result = ALL_WIDGETS;
  widgetCache.set(clientId, result, WIDGET_CACHE_TTL_MS);
  return result;
}
