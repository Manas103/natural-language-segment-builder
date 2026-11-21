from analytics_agent.semantic_model import DIMENSIONS, METRICS, field_count


def test_governed_model_has_thirty_eight_fields():
    assert field_count() == 38
    assert len(DIMENSIONS) + len(METRICS) == 38


def test_no_duplicate_metric_names():
    names = [m.name for m in METRICS]
    assert len(names) == len(set(names))


def test_no_duplicate_dimension_names():
    names = [d.name for d in DIMENSIONS]
    assert len(names) == len(set(names))


def test_every_metric_has_at_least_one_synonym():
    for m in METRICS:
        assert len(m.synonyms) >= 1


def test_every_dimension_has_at_least_one_synonym():
    for d in DIMENSIONS:
        assert len(d.synonyms) >= 1
