# Aegis Mind (Phase 13: The Resonance Workspace)

A local, dependency-light cognitive architecture: senses feed an attention and
memory system, an interpretable online model learns what matters, a typed
knowledge graph reasons with multi-hop inference, drives and goals give it a
deliberative tier, and a pre-learned conversational voice lets you talk to it --
all offline, all inspectable, all persisted as plain JSON/SQLite. The mind now
runs a global-workspace brain: specialist thoughts compete, one is broadcast
into a visible train of thought, activation spreads across its knowledge, and it
forms expectations it later confirms or is surprised by. The web UI also shows a
living particle face -- a "presence" panel driven by the mind's affect and
workspace state (built in parallel) -- so you can watch its mood and focus move
in real time.

## Quick Start
```bash
python run_mind.py            # REPL: talk to it; type /help for commands
python web_server.py          # dashboard + JSON API at http://127.0.0.1:8770
```
`run_mind.py` is now a thin launcher; `aegis_mind/core/mind.py` is the full
orchestrator. `web_server.py` is a stdlib-only backend (no external deps) that
serves `webui/index.html` and a small JSON API over one live Mind.

## What Phase 13 adds

Phase 13 introduces the **Resonance Workspace** (`aegis_mind/core/brain.py`) --
the integrative layer that makes the separate specialists feel like one mind. It
fuses three ideas from cognitive science into one small, fully interpretable
engine:

1. **A spreading-activation field.** Every concept the mind knows can hold an
   activation in `[0..1]`. Stimuli inject activation into their concepts;
   activation leaks one hop along typed knowledge-graph edges (so hearing
   "smoke" warms up "fire"); time pulls everything back toward zero via a lazy
   exponential half-life decay (no background thread). The current shape of the
   field *is* the mind's mental context -- "what is on its mind" is literal
   state, and `/mind` shows it.

2. **Global-workspace competition** (Baars). Each cognitive cycle, specialist
   proposers submit candidate thoughts -- the percept itself, a resonant recall,
   a derived inference, a drive's want, a felt state -- each with an explicit
   salience. They compete under a continuity bonus (keep the thread going),
   an anti-monotony penalty (don't drone on the same kind or thought), and a
   slight inference bias. Exactly **one** winner is broadcast per cycle: appended
   to a persistent stream of thought, its concepts boosted in the field, and fed
   back to bias the next competition toward continuity.

3. **Prospection** (a predictive brain). The inference specialist chains forward
   along causal / evidential edges (`causes`, `indicates`) from the hottest
   concepts and registers **expectations** about what may show up next. When
   later input matches one, the confirmation is counted, rewarded in the
   attention model at a low weight, and voiced ("I anticipated 'fire'").
   High-novelty input arriving unanticipated registers as **surprise**.

Honesty framing: this is not consciousness. It is a decaying dictionary of
concept weights plus a readable argmax over hand-written proposals -- but it
produces the functional signature of "smart": context carries across turns,
implications are drawn before being asked, and the whole train of thought is
inspectable and persists across restarts. Chat hooks expose it directly: ask
**"what's on your mind"** or **"what do you expect"**, and every REPL reply now
carries a `~ [thought]` line showing the moment that was just broadcast.

## What Phase 12 adds

Phase 12 adds **typed relational knowledge** with multi-hop inference
(`aegis_mind/core/knowledge.py`): facts are stored as typed relations, and the
mind can chain them to derive new conclusions with confidence and a proof trail.
Ask **"why?"** after an answer, or use `/kb <entity>` to see what it knows and
can infer about something.

## Earlier phases (cumulative)

- **Phase 11 -- deliberation.** Drives create goal pressure; goals decompose into
  a closed, cognitive-only step vocabulary; consolidation turns recurring
  episodes into beliefs (`/goal`, `/goals`, `/pursue`, `/drives`, `/sleep`).
- **Phase 10 -- domain knowledge.** Task-oriented data (restaurants, hotels,
  trains...) fused in by plain dict filtering (`/domain`).
- **Phase 9 -- affect + voice.** A four-dimensional mood every perception nudges,
  an offline conversational engine grounded in real state, and an inner
  monologue that surfaces spontaneous thoughts while `/watch` runs.
- **Phase 8 -- learning + senses.** An interpretable online logistic-regression
  attention model, a background sense-only perception loop, and the OODA
  reaction cycle.

## Commands

```
Core:      /status /memory /recall <q> /stats /save /introspect
Voice:     /mood /profile /teach <phrase> => <reply>
Brain:     /mind          The workspace: train of thought, activation field,
                          expectations (Phase 13)
Knowledge: /kb [entity]   Typed facts + inference; ask "why?" after answers
Learning:  /learn /feedback <id> good|bad /why <id> /important <id> /forget <id>
Goals:     /goal <text> | /goal drop <id> | /goals /pursue /drives /sleep
Domain:    /domain        Fused Cambridge data (restaurants, hotels, trains...)
Autonomy:  /watch start|stop|status   Background perception loop (sense-only)
```

## Layout

```
aegis_mind/
  core/
    mind.py            The orchestrator: assembles every subsystem and runs the
                       perceive -> cognition pipeline (run_mind.py is a thin launcher)
    brain.py           Phase 13 resonance workspace: activation field + thought
                       competition + prospection
    knowledge.py       Phase 12 typed relational knowledge + multi-hop inference
    goals.py drives.py consolidation.py   Phase 11 deliberative tier
    domain_knowledge.py                   Phase 10 fused task-oriented data
    affect.py chat.py  Phase 9 mood + offline conversational voice
    learning.py attention.py memory.py    Phase 8 learning, attention, memory
    instinct.py ooda.py perception_loop.py state.py
  senses/              vision, audio, screen, system, text input
  motor/               action dispatch (cognitive-only reactions)
  utils/               config loader
  memory_store/        persisted JSON/SQLite state (mind_memory, *_state.json)
web_server.py          stdlib-only HTTP + JSON backend for the dashboard
webui/index.html       the dashboard (chat, presence panel, live state)
config.yaml            per-subsystem config (mind, brain, affect, chat, learning,
                       memory, drives, goals, consolidation, knowledge, ...)
run_mind.py            thin REPL launcher over core/mind.py
```

## Safety

The safety posture is unchanged and cumulative across every phase.

- **The mind can only think, sense, and remember -- never act on the world.** The
  reaction repertoire and the background `/watch` loop are cognitive-only, with
  no motor or hardware access.
- **The workspace only thinks.** It proposes and broadcasts internal thoughts and
  expectations, never actions; everything it does is visible in `/mind` and
  persists as plain JSON.
- **The web backend only drives cognition.** There is no hardware endpoint, and
  the server binds `localhost` by default, so nothing is exposed off the machine.
- **Everything is inspectable and offline.** No LLM is required; state persists as
  plain JSON / SQLite you can read.
