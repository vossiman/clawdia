# Clawdia: Build vs. Buy — Honest Assessment

**Date:** 2026-03-28
**Status:** Decided — building custom stack (Option A with MCP-readiness for v2)

Should we build Clawdia's agent core from scratch, adopt an existing framework, or assemble from proven components?

---

## The Contenders

These are the frameworks that actually matter for Clawdia. Everything else researched (AutoGPT, CrewAI, Semantic Kernel, LangGraph, Haystack, Node-RED, n8n, ROS2) was either too heavy, wrong paradigm, or irrelevant for a Pi-based voice + hardware agent.

---

### OpenClaw — 339k★, MIT, TypeScript

**What it is:** Personal AI assistant platform. Cross-platform, own-your-data philosophy. Created Nov 2025, grew explosively. Plugin system via ClawHub. MCP support.

**For Clawdia:**
- Massive ecosystem and community — more plugins/integrations than anything else
- MCP support means our hardware tools could plug in
- Pi deployment documented (official docs + Adafruit guide)

**Against Clawdia:**
- **The security disaster.** 135K+ instances exposed to internet, RCE, credential theft, prompt injection. Defaults were insecure. This is not theoretical — it happened at scale.
- 1GB+ RAM on Pi — that's tight alongside voice pipeline
- TypeScript / Node.js — our stack is Python
- No voice input on Pi, no GPIO/hardware control built-in
- It's a cloud gateway, not an embodied agent framework — Pi just runs orchestration

**Verdict:** Big community, but wrong language, wrong paradigm, and a proven security track record we don't want to inherit. We'd still build all voice + hardware ourselves on top of it.

---

### NanoClaw — ~24k★, MIT, TypeScript

**What it is:** Security-first alternative to OpenClaw. Built on Anthropic's Claude Agent SDK. ~500 lines of core code. Agents run in isolated Docker/Apple containers. Connects to WhatsApp, Telegram, Slack, Discord, Gmail. Memory, scheduled jobs, web access. Created Jan 2026. Covered by Forbes, VentureBeat, ZDNet.

**For Clawdia:**
- Security-first design with container isolation — exactly the right mindset for always-on home device
- Tiny codebase (~500 lines) — auditable, understandable
- Telegram integration already built
- MIT license, good press coverage, growing fast

**Against Clawdia:**
- TypeScript — our stack is Python
- Built on Claude Agent SDK — locks us to Anthropic
- No voice input, no hardware/GPIO control
- Docker container overhead per agent on Pi
- Still young (2 months old), API could change rapidly

**Verdict:** The security model is genuinely interesting. The container isolation pattern is worth stealing for our own design. But TypeScript + Anthropic lock-in + no voice/hardware means it doesn't save us much work.

---

### Hermes Agent — ~14.5k★, MIT, Python

**What it is:** Self-improving AI agent framework by NousResearch. CLI + plugin architecture + learning loop that creates skills from experience. Supports any LLM via OpenRouter, OpenAI, Nous Portal, custom endpoints. v0.4.0 released March 2026. Has a companion self-evolution repo using DSPy.

**For Clawdia:**
- **Python** — same language as our stack
- **OpenRouter support** — same LLM backend we're already planning
- **Plugin/skill system** — could wrap our IR, Telegram, voice as Hermes skills
- **Self-improving** — the learning loop (creates skills from experience) is unique and could make Clawdia genuinely smarter over time
- Active development, NousResearch is a credible org
- Multiple terminal backends (Docker, SSH, Singularity) for sandboxing

**Against Clawdia:**
- Designed for cloud VPS deployment, not embedded/Pi
- No voice input built-in, no GPIO/hardware control
- 40+ built-in tools but none for hardware
- No MCP support documented
- Resource usage on Pi unclear — needs testing
- The self-improvement loop could burn tokens unpredictably

**Verdict:** Most interesting of the three for Clawdia. Same language, same LLM backend, plugin system we could use. The learning loop is compelling. Main risk: it's designed for cloud servers, not Pi. Needs a spike to test resource usage and see how well it adapts to embedded use.

---

### PydanticAI — Current Plan

**What it is:** Lightweight Python agent framework by the Pydantic team. Structured output via Pydantic models. Tool calling with type safety. Async-first.

**For Clawdia:**
- Python-native, async-first — perfect fit
- Structured output validation — LLM responses are typed and validated, great for intent routing (IR action vs text response)
- Clean, well-designed API
- Pydantic team won't disappear
- MCP client support built in

**Against Clawdia:**
- No plugin ecosystem
- No learning loop / self-improvement
- We build everything ourselves on top
- Smaller community than the big frameworks

**Verdict:** Solid, boring, reliable. Does exactly what we need for the brain layer. No surprises.

---

### SmolAgents (HuggingFace) — 26.3k★, Apache 2.0, Python

**What it is:** Ultra-lightweight agent framework. ~1000 lines core. Native MCP support. @tool decorator for custom tools. CodeAgent (generates Python) and ToolCallingAgent (JSON) modes. LiteLLM backend supports 100+ providers.

**For Clawdia:**
- ~1000 lines — we can read ALL of it
- Native MCP (`ToolCollection.from_mcp`) — future-proof plugin architecture
- @tool decorator makes wrapping hardware trivial
- LiteLLM = any LLM provider, not locked in
- Apache 2.0, HuggingFace backing
- CodeAgent benchmarks 30% better than JSON tool-calling

**Against Clawdia:**
- CodeAgent executes arbitrary generated Python — security risk on always-on device
- ToolCallingAgent is safer but less capable
- No structured output validation (no Pydantic integration)
- No voice, no hardware built-in

**Verdict:** The MCP-native design and @tool decorator are genuinely elegant. Worth serious consideration as alternative to PydanticAI, especially if we go MCP-first.

---

### MCP-First Architecture — Not a framework, a pattern

**What it is:** Expose every Clawdia capability as an MCP server. Thin Python orchestrator connects to MCP servers for IR, Telegram, voice, sensors. Any MCP-compatible LLM client can use the tools.

```
+---------------------------------------------+
|  Clawdia Core (thin orchestrator)            |
|  - Wake word -> STT -> LLM -> action routing |
|  - Personality / conversation memory         |
+---------------------------------------------+
|  MCP Servers (each independent):             |
|  +- mcp-ir-control (ir-ctl wrapper)          |
|  +- mcp-telegram (bot interface)             |
|  +- mcp-voice (wake word + STT + TTS)        |
|  +- mcp-display (future)                     |
|  +- mcp-camera (future)                      |
|  +- mcp-servos (future)                      |
+---------------------------------------------+
|  LLM Backend (pluggable):                    |
|  +- OpenRouter / Ollama / future Hailo HAT   |
+---------------------------------------------+
```

**For Clawdia:**
- MCP is THE universal standard — Anthropic, OpenAI, Google, Linux Foundation
- Each capability is independent — test, replace, upgrade separately
- Any AI agent can control Clawdia's hardware (Claude, GPT, local)
- ARM published official MCP-on-Pi-5 tutorial
- The "Casper" project (best documented Pi agent) uses this exact pattern
- PydanticAI and SmolAgents both have MCP client support

**Against Clawdia:**
- More upfront design work
- Inter-process communication overhead (small but nonzero)
- MCP hardware server ecosystem on Pi is young
- Might be over-engineering for MVP

**Verdict:** The right long-term architecture. Question is whether to build it from day one or retrofit after MVP.

---

## Security

**The OpenClaw disaster is the cautionary tale.** 135K+ exposed instances, RCE, credential theft — defaults were insecure and users didn't know better.

Clawdia's current design is already better (no inbound ports, single chat_id auth, cloud-first). Regardless of framework choice, add:
- Hardware mic mute switch (GPIO physical toggle)
- OpenRouter spending caps
- SSH hardening (ed25519 keys only, no password auth)
- `.env` permissions (`chmod 600`)
- `unattended-upgrades`
- `pip-audit` for dependency scanning

NanoClaw's container isolation pattern is worth borrowing even if we don't use NanoClaw itself.

---

## Local LLM Reality on Pi

| Model | Speed on Pi 5 8GB | Good for |
|-------|-------------------|----------|
| gemma3:1b | ~13.5 tok/s | Command classification |
| qwen2.5:1.5b | ~9.5 tok/s | Short answers |
| qwen2.5:3b | ~5 tok/s | Best local quality, slow |
| 7B+ | Impractical | Swapping, instability |

Cloud via OpenRouter is the right call for real conversations. Local is fallback only.

The Pi AI HAT+ 2 ($70, 40 TOPS, 8GB AI RAM) could change this but software is immature.

---

## Real-World Reference Projects

**Casper (~$200):** Pi 5, voice + Telegram + webhook. Gemini APIs, MCP middleware for tool discovery, ChromaDB memory. $1-3/day. Wake word ~500ms, first response ~800ms. Most complete documented Pi agent.

**Voice stack consensus:** openWakeWord (wake) + Whisper (STT) + LLM + Piper TTS. Cloud hybrid gets 1-2s latency. Fully local 3-8s.

**Personality research:** Vulcan project's 6-state emotional state machine works well — state machine handles consistency, LLM handles linguistic variation. Non-humanoid companions (cats) avoid uncanny valley.

---

## Open Questions

1. **Agent brain: PydanticAI vs SmolAgents vs Hermes Agent?**
   - PydanticAI: best structured output, simplest
   - SmolAgents: MCP-native, lightest
   - Hermes: self-improving skills, same LLM backend, but untested on Pi

2. **MCP from day one or retrofit later?**

3. **Personality system scope for MVP?**

4. **Pi 4B vs Pi 5?** Current hardware list says 4B. Pi 5 is 2-3x faster, supports AI HAT+ 2.

---

## Sources

- [OpenClaw](https://github.com/openclaw/openclaw) (339k★) | [Security incident](https://www.theregister.com/2026/02/03/openclaw_security_problems/)
- [NanoClaw](https://github.com/qwibitai/nanoclaw) (~24k★) | [nanoclaw.dev](https://nanoclaw.dev)
- [Hermes Agent](https://github.com/NousResearch/hermes-agent) (~14.5k★) | v0.4.0 March 2026
- [SmolAgents](https://github.com/huggingface/smolagents) (26.3k★)
- [PydanticAI](https://github.com/pydantic/pydantic-ai)
- [MCP Specification](https://modelcontextprotocol.io/specification/2025-11-25) — Linux Foundation
- [ARM MCP on Pi 5](https://learn.arm.com/learning-paths/cross-platform/mcp-ai-agent/)
- [Pi 5 LLM benchmarks](https://www.stratosphereips.org/blog/2025/6/5/how-well-do-llms-perform-on-a-raspberry-pi-5)
- [Casper Pi Agent](https://medium.com/@ostapagon/raspberry-ai-agent-that-wont-ghost-you-for-200-0c25475c95dd)
- [Vulcan emotional state machine](https://github.com/DecafSunrise/Vulcan)
- [Pi AI HAT+ 2](https://www.raspberrypi.com/news/introducing-the-raspberry-pi-ai-hat-plus-2-generative-ai-on-raspberry-pi-5/)
