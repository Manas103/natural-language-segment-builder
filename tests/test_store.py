from segment_builder.store import ProfileStore, generate_synthetic_profiles
from segment_builder.validator import SegmentValidator


def test_generation_is_seeded_and_reproducible():
    a = generate_synthetic_profiles(n=50, seed=1)
    b = generate_synthetic_profiles(n=50, seed=1)
    assert [(p.profile_id, p.attributes, [(e.name, e.days_ago) for e in p.events]) for p in a] == \
           [(p.profile_id, p.attributes, [(e.name, e.days_ago) for e in p.events]) for p in b]


def test_different_seeds_produce_different_data():
    a = generate_synthetic_profiles(n=50, seed=1)
    b = generate_synthetic_profiles(n=50, seed=2)
    assert [p.attributes for p in a] != [p.attributes for p in b]


def test_and_composite_is_intersection_not_union():
    store = ProfileStore.synthetic(n=1000, seed=5)
    trial = SegmentValidator.validate({"version": "1.0", "root": {"type": "attribute", "field": "is_trial", "operator": "eq", "value": True}})
    pro = SegmentValidator.validate({"version": "1.0", "root": {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "pro"}})
    both = SegmentValidator.validate(
        {
            "version": "1.0",
            "root": {
                "type": "and",
                "children": [
                    {"type": "attribute", "field": "is_trial", "operator": "eq", "value": True},
                    {"type": "attribute", "field": "plan_tier", "operator": "eq", "value": "pro"},
                ],
            },
        }
    )
    n_trial = store.execute_segment(trial)
    n_pro = store.execute_segment(pro)
    n_both = store.execute_segment(both)
    assert n_both <= min(n_trial, n_pro)


def test_not_is_the_complement():
    store = ProfileStore.synthetic(n=1000, seed=5)
    trial = SegmentValidator.validate({"version": "1.0", "root": {"type": "attribute", "field": "is_trial", "operator": "eq", "value": True}})
    not_trial = SegmentValidator.validate({"version": "1.0", "root": {"type": "not", "children": [{"type": "attribute", "field": "is_trial", "operator": "eq", "value": True}]}})
    assert store.execute_segment(trial) + store.execute_segment(not_trial) == len(store.profiles)


def test_event_within_days_narrows_or_equals_unbounded_count():
    store = ProfileStore.synthetic(n=1000, seed=7)
    unbounded = SegmentValidator.validate({"version": "1.0", "root": {"type": "event", "event_name": "login", "operator": "count_gte", "count": 1}})
    windowed = SegmentValidator.validate({"version": "1.0", "root": {"type": "event", "event_name": "login", "operator": "count_gte", "count": 1, "within_days": 30}})
    assert store.execute_segment(windowed) <= store.execute_segment(unbounded)


def test_or_composite_is_union_not_intersection():
    store = ProfileStore.synthetic(n=1000, seed=9)
    a = SegmentValidator.validate({"version": "1.0", "root": {"type": "attribute", "field": "country", "operator": "eq", "value": "US"}})
    b = SegmentValidator.validate({"version": "1.0", "root": {"type": "attribute", "field": "country", "operator": "eq", "value": "CA"}})
    either = SegmentValidator.validate(
        {
            "version": "1.0",
            "root": {
                "type": "or",
                "children": [
                    {"type": "attribute", "field": "country", "operator": "eq", "value": "US"},
                    {"type": "attribute", "field": "country", "operator": "eq", "value": "CA"},
                ],
            },
        }
    )
    assert store.execute_segment(either) >= max(store.execute_segment(a), store.execute_segment(b))
