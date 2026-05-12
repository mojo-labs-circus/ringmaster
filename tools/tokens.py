"""tools/tokens.py
Token counting for history budget enforcement.

Uses a character-based heuristic (~4 chars per token) rather than a real tokenizer.
Good enough for nomadbaker — on pearlybaker/server this will be replaced with a call
to Ollama's /api/tokenize endpoint for exact counts.
"""

from config import CHARS_PER_TOKEN


def count_tokens(text: str) -> int:
    """Estimate the number of tokens in a string."""
    return max(1, len(text) // CHARS_PER_TOKEN)


def count_messages(messages: list[dict]) -> int:
    """Estimate the total tokens across a list of {"role": ..., "content": ...} dicts.

    TODO: role is metadata in the Ollama API and shouldn't contribute to the token count.
    Revisit when implementing context window management.
    """
    return sum(count_tokens(m.get("role", "") + m.get("content", "")) for m in messages)
