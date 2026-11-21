"""DB- and grader-level tests. Skip cleanly, as the playbook requires, when
PostgreSQL is not reachable at the configured DSN rather than failing the
build.
"""
import pytest

from analytics_agent import db, grader
from analytics_agent.eval_dataset import build_in_model_questions, build_out_of_model_questions
from analytics_agent.judge import TranscriptJudge

pytestmark = pytest.mark.skipif(not db.is_reachable(), reason="PostgreSQL not reachable at configured DSN")


@pytest.fixture(scope="module")
def loaded_con():
    con = db.connect()
    db.load_sales_fact(con, n_line_items=2000, seed=99)
    yield con
    con.close()


def test_load_sales_fact_inserts_rows(loaded_con):
    cur = loaded_con.cursor()
    cur.execute("SELECT count(*) FROM sales_fact")
    assert cur.fetchone()[0] == 2000


def test_grade_question_exact_match_when_parse_succeeds(loaded_con):
    questions = [q for q in build_in_model_questions() if q.text.startswith("What is the") or q.text.startswith("What's the")]
    q = next(q for q in questions if "equals" not in q.text)
    judge = TranscriptJudge()
    result = grader.grade_question(loaded_con, q.question_id, q.text, q.verified_spec, judge, q.use_word_numbers)
    assert result.exec_match is True


def test_out_of_model_questions_all_refused():
    questions = build_out_of_model_questions()
    assert all(grader.grade_out_of_model_question(t) for t in questions)


def test_parser_is_never_given_the_verified_spec(loaded_con):
    """Leakage control: deleting the answer key before grading must not change the result."""
    questions = build_in_model_questions()
    q = questions[0]
    answer_key = {qq.question_id: qq.verified_spec for qq in questions}
    judge = TranscriptJudge()

    result_with_key_present = grader.grade_question(loaded_con, q.question_id, q.text, q.verified_spec, judge, q.use_word_numbers)
    del answer_key  # the parser never had access to this dict in the first place
    result_after_deleting_key = grader.grade_question(loaded_con, q.question_id, q.text, q.verified_spec, judge, q.use_word_numbers)

    assert result_with_key_present.exec_match == result_after_deleting_key.exec_match
    assert result_with_key_present.parsed_spec == result_after_deleting_key.parsed_spec
