"""tools/tokens.py
Token counting for history budget enforcement.

Uses a character-based heuristic (~4 chars per token) rather than a real tokenizer.
Good enough for nomadbaker — on pearlybaker/server this will be replaced with a call
to Ollama's /api/tokenize endpoint for exact counts.
"""

_CHARS_PER_TOKEN = 4


def count_tokens(text: str) -> int:
    """Estimate the number of tokens in a string."""
    return max(1, len(text) // _CHARS_PER_TOKEN)


def count_messages(messages: list[dict]) -> int:
    """Estimate the total tokens across a list of {"role": ..., "content": ...} dicts."""
    return sum(count_tokens(m.get("role", "") + m.get("content", "")) for m in messages)
