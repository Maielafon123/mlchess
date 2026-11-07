import createClient from "openapi-fetch";
import type { paths } from "./generated/api.js";

/** Same-origin cookies by default. Mutations require explicit CSRF headers. */
export function createChessClient(baseUrl = "", fetchImpl: typeof fetch = fetch) {
  return createClient<paths>({ baseUrl, credentials: "same-origin", fetch: fetchImpl });
}
