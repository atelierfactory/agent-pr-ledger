# Security

agent-pr-ledger runs with `contents: read` and `pull-requests: read`, has no dependencies outside the Python standard library, and by default contacts nothing but `api.github.com`. Redirects away from expected hosts are refused before they are followed.

If you find a way for this tool to read, write or transmit more than the README's "What leaves your repository" table says, that is a security issue in this project's own terms, even if it is not exploitable.

Report by opening a GitHub issue if the matter is not sensitive, or by e-mail to the address in `CITATION.cff` if it is. We will acknowledge within seven days and publish the fix and the report together.
