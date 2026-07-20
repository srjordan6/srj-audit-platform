"""Canonical AI-tool catalog for the T1-A-000 tool inventory question.

Grouped by category for visual rendering. Order within each category
follows the numeric rank Stephen provided in the source list.

Total: 88 tools across 11 categories (2026-07-19 expansion: +16 Western
tools including GitHub Copilot, Claude Code, Sora, Firefly, plus a new
Chinese Foundation Models category with Qwen, GLM/Z.AI, Doubao, MiniMax,
Hunyuan, ERNIE, MiMo — DeepSeek and Kimi were already listed). Any tool
the respondent uses that isn't listed here goes into the free-form
"other" text field on the inventory question.

CATEGORIES is the primary data structure the partial iterates over.
TOOLS_FLAT is a convenience flat list of the same tool names (useful
for downstream question wiring, e.g. T1-B-017 row prefill).
"""

from __future__ import annotations

from typing import List, Tuple


CATEGORIES: List[Tuple[str, List[str]]] = [
    ("Chat & General LLMs", [
        "ChatGPT",
        "Gemini",
        "Claude",
        "Microsoft Copilot",
        "Perplexity AI",
        "Grok",
        "DeepSeek",
        "Poe",
        "Pi",
        "HyperWrite",
        "Kimi",
        "You.com",
        "Character.ai",
        "Janitor AI",
        "Llama (Meta)",
        "Mistral / Le Chat",
        "Notion AI",
        "Slack AI",
        "Zoom AI Companion",
    ]),
    ("Chinese Foundation Models", [
        "Qwen / Tongyi Qianwen (Alibaba)",
        "GLM / Z.AI (Zhipu AI)",
        "Doubao / Seed (ByteDance)",
        "MiniMax",
        "Hunyuan (Tencent)",
        "ERNIE (Baidu)",
        "MiMo (Xiaomi)",
    ]),
    ("Writing & Editing", [
        "Grammarly",
        "QuillBot",
        "Wordtune",
        "Rytr",
        "WriteSonic",
        "Copy.ai",
        "Jasper",
    ]),
    ("Notes, Knowledge & Meetings", [
        "NotebookLM",
        "Otter.ai",
        "Mem",
        "Fireflies.ai",
    ]),
    ("Image & Graphic Design", [
        "Canva AI",
        "Midjourney",
        "Leonardo.ai",
        "Stable Diffusion",
        "DeepAI",
        "Microsoft Designer",
        "Remove.bg",
        "DALL-E (OpenAI)",
        "Adobe Firefly",
    ]),
    ("Video Generation & Editing", [
        "Runway",
        "HeyGen",
        "Synthesia",
        "Descript",
        "CapCut",
        "InVideo",
        "OpusClip",
        "Filmora AI",
        "Pictory",
        "Fliki",
        "Lumen5",
        "Luma AI",
        "Sora (OpenAI)",
    ]),
    ("Voice & Audio", [
        "ElevenLabs",
        "Suno",
        "Murf.ai",
        "Play.ht",
        "Resemble AI",
        "Krisp",
    ]),
    ("Slides & Presentations", [
        "Gamma",
        "SlidesAI",
        "Beautiful.ai",
    ]),
    ("Coding & Developer Tools", [
        "Cursor",
        "Replit Agent",
        "Tabnine",
        "Lovable",
        "Google AI Studio",
        "Hugging Face",
        "GitHub Copilot",
        "Claude Code",
        "Windsurf",
        "Bolt.new",
        "v0 (Vercel)",
        "OpenAI API / GPT models",
    ]),
    ("Automation & Agents", [
        "n8n",
        "Zapier Central",
        "Manus",
    ]),
    ("Search, Research, Translation & Other", [
        "Consensus",
        "DeepL",
        "Wayground",
        "Groq",
        "Salesforce Einstein / Agentforce",
    ]),
]


TOOLS_FLAT: List[str] = [tool for _, tools in CATEGORIES for tool in tools]
