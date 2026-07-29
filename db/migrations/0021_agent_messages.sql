-- ADR-0038: the agent's raw session trace, persisted.
--
-- pipeline/agent/loop.py's own docstring claimed "the full message trace preserved -- the raw,
-- unedited log the brief demands is a database export, not a narrative." It was not preserved.
-- The `messages` list lived in a local variable and died when run_goal returned. ops.run_events
-- recorded that a tool was CALLED, with its arguments and a record COUNT -- but never what came
-- back, never the model's intermediate reasoning, and never the repair turn.
--
-- The brief asks for "the action sequence, every retrieval and tool call, intermediate decisions,
-- any retries, rejected paths, uncertainty checks, escalations, or refusals, and final output
-- generation," and says plainly that "a written summary of a run is not a run log." A trace that
-- omits tool results cannot show a rejected path, because the rejection is a reaction to a result.

create table if not exists ops.agent_messages (
    id         bigserial primary key,
    run_id     bigint not null references ops.runs(run_id) on delete cascade,
    seq        int    not null,          -- position in the conversation, 0-based
    role       text   not null,          -- system | user | assistant | tool
    content    text,                     -- message text, or the tool's returned payload
    tool_calls jsonb,                    -- the calls an assistant turn requested, verbatim
    phase      text,                     -- 'session' | 'repair': which pass produced this turn
    created_at timestamptz not null default now(),
    unique (run_id, seq)
);

create index if not exists agent_messages_run_idx on ops.agent_messages (run_id, seq);

comment on table ops.agent_messages is
    'Raw, unedited agent session trace (ADR-0038): every message in order, including tool results '
    'and the repair turn. This is the run log the Stage 2 brief requires -- not a summary of one.';

comment on column ops.agent_messages.phase is
    'session = the main tool-calling loop. repair = the turn taken after the deterministic release '
    'gate rejected an answer, which is the retry the brief asks to see.';
