"""Offline evaluation on synthetic data with planted taste groups.

Each user mostly views items from one group. We hide each user's last 20% of views and ask:
does the recommender put the hidden items in the top 10? Compared with plain popularity.
"""
import random
import sys
from collections import defaultdict

sys.path.insert(0, ".")
from personalization import scoring  # noqa: E402


def make_data(users=1500, items=240, groups=6, per_user=14, seed=7):
    rng = random.Random(seed)
    size = items // groups
    data = {}
    for u in range(users):
        g = rng.randrange(groups)
        seq = []
        while len(seq) < per_user:
            gg = g if rng.random() < 0.85 else rng.randrange(groups)
            it = f"item{gg * size + rng.randrange(size)}"
            if it not in seq:
                seq.append(it)
        data[f"u{u}"] = seq
    return data


def build_model(train):
    pop, cooc = defaultdict(float), defaultdict(lambda: defaultdict(float))
    for seq in train.values():
        for it in seq:
            pop[it] += 1
        for i, a in enumerate(seq):
            for b in seq[i + 1:]:
                cooc[a][b] += 1
                cooc[b][a] += 1
    return pop, cooc


def evaluate(k=10, seed=7):
    data = make_data(seed=seed)
    users = sorted(data)
    test_users = users[: len(users) // 5]
    train = {u: data[u] for u in users[len(users) // 5:]}
    train.update({u: data[u][: int(len(data[u]) * 0.8)] for u in test_users})
    pop, cooc = build_model(train)
    hits_cf = hits_pop = total = 0
    for u in test_users:
        hist = data[u][: int(len(data[u]) * 0.8)]
        hidden = set(data[u][int(len(data[u]) * 0.8):])
        rec = [i for i, _, _ in scoring.recommend(hist, cooc, pop, set(), k)]
        base = scoring.popularity_only(hist, pop, set(), k)
        hits_cf += len(hidden & set(rec))
        hits_pop += len(hidden & set(base))
        total += len(hidden)
    return {"recall_item_item": hits_cf / total, "recall_popularity": hits_pop / total}


if __name__ == "__main__":
    res = evaluate()
    print(f"recall@10  item-item {res['recall_item_item']:.3f}  popularity {res['recall_popularity']:.3f}  "
          f"lift {res['recall_item_item'] / res['recall_popularity']:.1f}x")
