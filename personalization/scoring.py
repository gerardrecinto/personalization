"""Item-item recommendations from co-occurrence counts. Pure functions, no I/O, so they are easy to test."""
import math
from typing import Dict, Iterable, List, Set, Tuple


def cosine(co: float, pop_a: float, pop_b: float) -> float:
    """Cosine similarity of two items from binary interactions: co / sqrt(pop_a * pop_b)."""
    if co <= 0 or pop_a <= 0 or pop_b <= 0:
        return 0.0
    return co / math.sqrt(pop_a * pop_b)


def recommend(history: List[str], cooc: Dict[str, Dict[str, float]], pop: Dict[str, float],
              restricted: Set[str], k: int = 10) -> List[Tuple[str, float, str]]:
    """Return up to k (item, score, reason). Falls back to popularity when there is no history signal."""
    seen = set(history)
    scores: Dict[str, float] = {}
    best: Dict[str, Tuple[float, str]] = {}  # candidate -> (strongest single signal, the item it came from)
    for src in history:
        for cand, co in cooc.get(src, {}).items():
            if cand in seen or cand in restricted:
                continue
            s = cosine(co, pop.get(src, 0), pop.get(cand, 0))
            if s <= 0:
                continue
            scores[cand] = scores.get(cand, 0.0) + s
            if cand not in best or s > best[cand][0]:
                best[cand] = (s, src)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:k]
    out = [(item, round(score, 6), f"because you viewed {best[item][1]}") for item, score in ranked]
    if len(out) < k:  # cold start or thin history: fill with popular items
        have = {i for i, _, _ in out}
        for item, p in sorted(pop.items(), key=lambda kv: (-kv[1], kv[0])):
            if len(out) >= k:
                break
            if item in seen or item in restricted or item in have:
                continue
            out.append((item, 0.0, "popular right now"))
    return out


def popularity_only(history: Iterable[str], pop: Dict[str, float], restricted: Set[str], k: int = 10) -> List[str]:
    seen = set(history)
    return [i for i, _ in sorted(pop.items(), key=lambda kv: (-kv[1], kv[0])) if i not in seen and i not in restricted][:k]
