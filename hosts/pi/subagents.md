## Optional Pi delegation

Requires operator-installed pi-subagents 0.79.1. Delegate only when the request
or applicable project instructions authorize it. If exposed,
`subagents_enable({})` enables `subagent` on the next model request without
launching work. Missing tools block delegation; continue permitted local work.

Read `subagent({action: "guide", options: {topic: "tool-reference"}})` and discover
agents with `subagent({action: "list"})`. A bounded scout request is
`subagent({agent: "scout", task: "<complete scoped brief>", async: false,
options: {timeoutMs: 120000, context: "fresh", share: false}})`.

Use a discovered worker for implementation, passing the full rendered included
lead instructions plus the explicit objective when delegating an outcome. Read the
installed lead prompt body; omit its metadata and replace its trailing argument
placeholder with the task when constructing the child brief. Prompt templates aren't registered
child agents. Keep one writer per file set and a finite fanout (default one).
Use writer deadlines with time to checkpoint; hard tool/usage budgets don't
guarantee a safe mutation boundary. Foreground children lack ambient extensions;
research requiring web tools needs separately configured child tools.

Check output, errors and artifacts. An async receipt confirms launch only.
Record the exact returned run id; inspect `subagent({action: "status", id: "<id>"})`
and steer a live child with `action: "steer"` and `message`. Resume only an eligible
retained child with `action: "resume"`, exact `id` and `message`; it creates a new
child from persisted context and may refuse. Stopped runs aren't resumable.
Capture partial changes on failure; don't switch execution protocols without
approval. Keep sharing disabled. Timeout, concurrency, depth and cumulative spawn
limits are distinct; the default run-tree spawn cap is 64. For authorized workflow
scripts, use awaited `runs.run` / `runs.all`; read the installed workflow guide.
This kit configures none of those runtime limits and adds no remote transport.
