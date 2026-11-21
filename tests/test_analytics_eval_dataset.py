from analytics_agent.eval_dataset import (
    N_IN_MODEL, N_OUT_OF_MODEL, build_in_model_questions, build_out_of_model_questions,
)


def test_builds_350_in_model_questions():
    questions = build_in_model_questions()
    assert len(questions) == N_IN_MODEL == 350


def test_builds_60_out_of_model_questions():
    questions = build_out_of_model_questions()
    assert len(questions) == N_OUT_OF_MODEL == 60


def test_deterministic_for_same_seed():
    a = build_in_model_questions(seed=1)
    b = build_in_model_questions(seed=1)
    assert [q.text for q in a] == [q.text for q in b]


def test_out_of_model_questions_are_unique():
    questions = build_out_of_model_questions()
    assert len(set(questions)) == len(questions)


def test_every_in_model_question_has_a_valid_verified_spec():
    for q in build_in_model_questions():
        assert q.verified_spec.metric
