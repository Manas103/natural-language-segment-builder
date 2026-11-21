"""A transcript-reading judge: it never executes SQL and never sees a result
set, only the rendered natural-language answer string a conversational agent
would actually show a user. It extracts the first number-looking token from
that string and compares it to the expected value. This is deliberately
weaker than the execution oracle in grader.py: a correct answer rendered in
word form ("three returns" instead of "3 returns") has no digit token for
the judge's regex to find, so the judge marks it wrong even though the
underlying execution was exactly correct. That gap is the honest point of
this module, mirroring why Snowflake's own write-ups on LLM-as-judge
benchmarking do not trust a judge's impression over actually executing the
query (see README).
"""
import re

_NUMBER_RE = re.compile(r"[-+]?\$?[0-9][0-9,]*\.?[0-9]*%?")

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten",
         "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen",
         "eighteen", "nineteen"]


def _spell_small_int(n: int) -> str:
    if 0 <= n < len(_ONES):
        return _ONES[n]
    return str(n)


def extract_number(text: str):
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    raw = match.group(0).replace("$", "").replace(",", "").replace("%", "")
    try:
        return float(raw)
    except ValueError:
        return None


class TranscriptJudge:
    def __init__(self, tolerance: float = 0.01):
        self.tolerance = tolerance

    def score(self, rendered_transcript: str, expected_value) -> bool:
        if expected_value is None:
            return "can't answer" in rendered_transcript or "cannot answer" in rendered_transcript
        found = extract_number(rendered_transcript)
        if found is None:
            return False
        return abs(found - float(expected_value)) <= self.tolerance * max(1.0, abs(float(expected_value)))
