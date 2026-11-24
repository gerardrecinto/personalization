from eval.offline_eval import evaluate
from personalization import scoring
from personalization.abtest import z_test
from personalization.privacy import user_key

POP = {"a": 10, "b": 8, "c": 6, "d": 5, "e": 1}
COOC = {"a": {"b": 6, "c": 1}, "b": {"a": 6, "d": 3}}


def test_cosine_basics():
    assert scoring.cosine(0, 5, 5) == 0
    assert round(scoring.cosine(5, 5, 5), 3) == 1.0


def test_recommends_related_item_with_reason():
    out = scoring.recommend(["a"], COOC, POP, set(), k=1)
    assert out[0][0] == "b" and out[0][2] == "because you viewed a"


def test_never_recommends_seen_or_restricted():
    out = scoring.recommend(["a"], COOC, POP, {"b"}, k=5)
    items = [i for i, _, _ in out]
    assert "a" not in items and "b" not in items


def test_cold_start_falls_back_to_popularity():
    out = scoring.recommend([], {}, POP, {"a"}, k=2)
    assert [i for i, _, _ in out] == ["b", "c"]
    assert all(reason == "popular right now" for _, _, reason in out)


def test_user_key_is_stable_keyed_and_not_the_raw_id():
    assert user_key("alice", "s1") == user_key("alice", "s1")
    assert user_key("alice", "s1") != user_key("alice", "s2")
    assert "alice" not in user_key("alice", "s1")


def test_ab_test_detects_a_real_lift_and_ignores_noise():
    assert z_test(100, 1000, 140, 1000)["significant"] is True
    assert z_test(100, 1000, 104, 1000)["significant"] is False


def test_item_item_beats_popularity_offline():
    res = evaluate()
    print(res)
    assert res["recall_item_item"] > 2 * res["recall_popularity"]
