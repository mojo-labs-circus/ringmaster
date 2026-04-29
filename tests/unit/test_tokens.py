from config import CHARS_PER_TOKEN
from tools.tokens import count_messages, count_tokens


def test_count_tokens_empty():
    assert count_tokens("") == 1


def test_count_tokens_exactly_one_bucket():
    assert count_tokens("a" * CHARS_PER_TOKEN) == 1


def test_count_tokens_one_over_bucket():
    assert count_tokens("a" * (CHARS_PER_TOKEN + 1)) == 1


def test_count_tokens_scales_linearly():
    assert count_tokens("a" * (CHARS_PER_TOKEN * 100)) == 100
    assert count_tokens("a" * (CHARS_PER_TOKEN * 200)) == 200


def test_count_messages_sums():
    messages = [
        {"role": "user", "content": "hello"},      # "userhello" = 9 chars
        {"role": "assistant", "content": "hi"},     # "assistanthi" = 11 chars
    ]
    expected = (9 // CHARS_PER_TOKEN) + (11 // CHARS_PER_TOKEN)
    assert count_messages(messages) == expected


def test_count_messages_empty():
    assert count_messages([]) == 0
