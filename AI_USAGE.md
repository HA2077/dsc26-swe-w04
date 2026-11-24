# AI usage

Keep all three headings exactly as they are. If this file is missing or any heading is
missing, the grader stops and gives 0 ("AI_USAGE.md missing or incomplete"). The content
is not scored, but your Track Mentor reads it and the W8 defence can ask about it.

## Tools

- opencode CLI assistant (model deepseek-v4.1-flash-free) for planning the suite, writing the unit/API/contract tests.

## What AI got wrong

- It claimed a CORS mutant that allows every origin would make the allowed-origin preflight answer `Access-Control-Allow-Origin: *`. Reading `starlette/middleware/cors.py` and running the mutant showed it echoes the request origin instead, so the kill had to come from the disallowed-origin tests.

- It wrote the reserve-boundary case `can_transfer(5, 1, 5)` expecting `True`; 5 − 1 = 4 is below the reserve 5. The test failed on the first run and I corrected the case to `(6, 1, 5)`.

## In my own words

<!-- Answer without AI, one or two sentences each. -->

1. Pick one mutant your first draft of tests did not kill. Why not, and what did you add?

My first M09 draft only checked allowed origins so it passed on the mutant because Starlette echoes the origin when credentials are on. I added tests for a disallowed origin the preflight must return 400 with no ACAO and a simple request must have no ACAO header.

2. Why is a test that only asserts `status_code == 409` weaker than one that asserts the problem `type`?

Because a test with only `status_code == 409` could pass with any 409 response, even if it is not the error we are trying to catch. On the other hand, asserting the problem `type` ensures that we are specifically checking for the expected error type making the test more precise.