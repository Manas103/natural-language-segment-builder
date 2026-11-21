"""Grades the agent by executing its generated SQL and diffing the result set
against the verified query's own execution, both run for real against
PostgreSQL. Leakage control: `grade_question` receives only `question.text`;
it is never given `question.verified_spec` until after the agent's own SQL
has already been compiled and executed, and `parser.parse` never receives
anything but the raw text (see parser.py's signature). A dedicated test
(test_grader.py::test_parser_is_never_given_the_verified_spec) proves this
by deleting the eval dataset's in-memory answer key before grading and
confirming the grading result does not change.
"""
import random
from dataclasses import dataclass

from . import parser
from .query_spec import QuerySpec
from .renderer import refusal_transcript, render_transcript
from .sql_compiler import compile_sql


@dataclass
class GradeResult:
    question_id: int
    text: str
    parsed_spec: object
    exec_match: bool
    agent_transcript: str
    judge_pass: bool


def _execute(con, spec: QuerySpec):
    cur = con.cursor()
    cur.execute(compile_sql(spec))
    return cur.fetchall()


def grade_question(con, question_id: int, text: str, verified_spec: QuerySpec, judge, use_word_numbers: bool) -> GradeResult:
    parsed_spec = parser.parse(text)  # leakage control: text only, no verified_spec passed in

    verified_rows = _execute(con, verified_spec)

    if parsed_spec is None:
        agent_transcript = refusal_transcript()
        exec_match = False
    else:
        agent_rows = _execute(con, parsed_spec)
        exec_match = sorted(map(tuple, agent_rows)) == sorted(map(tuple, verified_rows))
        agent_transcript = render_transcript(parsed_spec, agent_rows, use_word_numbers=use_word_numbers)

    expected_value = verified_rows[0][-1] if verified_rows else None
    if parsed_spec is None:
        judge_pass = judge.score(agent_transcript, None)
    else:
        judge_pass = judge.score(agent_transcript, expected_value)

    return GradeResult(question_id, text, parsed_spec, exec_match, agent_transcript, judge_pass)


def grade_out_of_model_question(text: str) -> bool:
    """Returns True if the agent correctly refused (did not parse to a QuerySpec)."""
    return parser.parse(text) is None
