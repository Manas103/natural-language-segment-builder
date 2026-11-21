from analytics_agent.judge import TranscriptJudge, extract_number


def test_extract_number_from_currency():
    assert extract_number("The total revenue is $1,234.56.") == 1234.56


def test_extract_number_from_percent():
    assert extract_number("The return rate is 16.8%.") == 16.8


def test_extract_number_returns_none_for_word_form():
    assert extract_number("The return count is three.") is None


def test_judge_scores_matching_value_correct():
    judge = TranscriptJudge()
    assert judge.score("The total revenue is $1,000.00.", 1000.0) is True


def test_judge_scores_mismatching_value_incorrect():
    judge = TranscriptJudge()
    assert judge.score("The total revenue is $1,000.00.", 50.0) is False


def test_judge_fails_on_unparseable_transcript():
    judge = TranscriptJudge()
    assert judge.score("The return count is three.", 3.0) is False


def test_judge_accepts_refusal_transcript_when_no_answer_expected():
    judge = TranscriptJudge()
    assert judge.score("I can't answer that; it isn't part of the governed semantic model.", None) is True


def test_judge_grabs_the_first_number_even_if_it_is_the_wrong_one():
    judge = TranscriptJudge()
    # the group label "2024" appears before the real value "400" in the sentence;
    # this is the exact failure mode documented in the README findings.
    transcript = "Broken down by year, the top entry (2024) has distinct products sold 400."
    assert judge.score(transcript, 400.0) is False
