"""Loads the synthetic sales_fact table into real PostgreSQL, then runs the
350-question execution-match eval, the 60-question out-of-model refusal
eval, and the transcript-judge comparison on the same 350 runs.

    python scripts/run_analytics_eval.py

Requires PostgreSQL reachable at the connection parameters in
analytics_agent/db.py (see README "Building and running" for how this
machine stands it up inside WSL2). Exits with a clear message, no
traceback, if it is not reachable.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analytics_agent import db, grader
from analytics_agent.eval_dataset import build_in_model_questions, build_out_of_model_questions
from analytics_agent.judge import TranscriptJudge
from analytics_agent.semantic_model import field_count


def main():
    if not db.is_reachable():
        print("PostgreSQL is not reachable at the configured DSN; see README for stand-up commands. Skipping.")
        return

    con = db.connect()
    n_loaded = db.load_sales_fact(con)
    print(f"loaded {n_loaded} synthetic sales_fact rows")
    print(f"governed semantic model: {field_count()} metrics and dimensions")

    in_model_questions = build_in_model_questions()
    out_of_model_questions = build_out_of_model_questions()
    judge = TranscriptJudge()

    results = []
    for q in in_model_questions:
        result = grader.grade_question(con, q.question_id, q.text, q.verified_spec, judge, q.use_word_numbers)
        results.append(result)

    exec_matches = sum(1 for r in results if r.exec_match)
    judge_passes = sum(1 for r in results if r.judge_pass)
    n = len(results)

    oom_refused = sum(1 for text in out_of_model_questions if grader.grade_out_of_model_question(text))
    n_oom = len(out_of_model_questions)

    exec_pct = 100.0 * exec_matches / n
    judge_pct = 100.0 * judge_passes / n
    gap_points = exec_pct - judge_pct

    print()
    print(f"in-model questions: {n}")
    print(f"execution match: {exec_matches}/{n} ({exec_pct:.1f}%)")
    print(f"transcript-judge pass: {judge_passes}/{n} ({judge_pct:.1f}%)")
    print(f"gap: {gap_points:.1f} points under the transcript-reading judge" if gap_points >= 0 else f"gap: judge scored {-gap_points:.1f} points higher than execution")
    print()
    print(f"out-of-model questions: {n_oom}")
    print(f"correctly refused: {oom_refused}/{n_oom}")

    disagreements = [r for r in results if r.exec_match != r.judge_pass]
    print()
    print(f"oracle/judge disagreements: {len(disagreements)}")
    for r in disagreements[:5]:
        print(f"  q{r.question_id}: exec_match={r.exec_match} judge_pass={r.judge_pass} transcript={r.agent_transcript!r}")

    con.close()


if __name__ == "__main__":
    main()
