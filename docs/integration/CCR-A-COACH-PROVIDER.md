# Optional coach provider status

Existing coach request, result and event schemas remain unchanged. The new
public, read-only `GET /api/v1/coach/provider` returns
`{"schema_version":1,"external":false}` by default. It carries no model
key or account information. Clients can show what data leaves the application
before a request. Unknown or unavailable status keeps the notice generic.

The default remains verified Stockfish and local rules. An installation
owner may explicitly set `MLCHESS_COACH_OPENAI_MODEL` and
`MLCHESS_COACH_OPENAI_API_KEY` in the private server Compose settings.
Only the coach worker receives the key. The configured model must support
Structured Outputs. This optional egress is supported by the server host
overlay; the default private Docker bridge deliberately isolates the worker
from the internet.

The request sends only verified check/capture booleans, the quality label and
hint level. The model selects an allowed teaching focus and question. Local
templates render the explanation and the existing grounding validator checks
it; model-written factual claims never reach the browser. Requests use
`store: false`, fixed HTTPS endpoint, no redirects and bounded output/time.
There are hourly per-player and installation-wide limits. Failure or an
unsupported answer returns a verified local explanation. No credentials or
live external request are needed to run the transport and fallback tests.

Source: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
