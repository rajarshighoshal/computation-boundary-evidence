import hashlib

import pytest

from scicontext.sampling import select_tasks


def population():
    return [{"task_id": f"{i:03d}", "restricted_license": "False", "license_gate": "none"}
            for i in range(1, 12)]


def test_draw_is_reproducible_uniform_hash_ranking_and_balanced():
    rows = population()
    rows[3]["restricted_license"] = "True"
    rows[4]["license_gate"] = "restricted"
    draw = select_tasks(rows, "fixed-public-seed")
    assert draw == select_tasks(list(reversed(rows)), "fixed-public-seed")
    assert not {"002", "004", "005"} & set(draw["task_ids"])
    expected = sorted(draw["eligible_task_ids"], key=lambda t: hashlib.sha256(("fixed-public-seed:" + t).encode()).hexdigest())[:5]
    assert draw["task_ids"] == expected
    orders = list(draw["condition_order"].values())
    assert all(sorted(order) == ["baseline", "science"] for order in orders)
    assert sum(order[0] == "baseline" for order in orders) in {2, 3}


@pytest.mark.parametrize("count", [0, 6, -1, True])
def test_sample_size_is_bounded(count):
    with pytest.raises(ValueError):
        select_tasks(population(), "seed", count)


def test_duplicate_ids_and_small_population_are_rejected():
    rows = population()
    with pytest.raises(ValueError, match="Duplicate"):
        select_tasks(rows + [rows[0]], "seed")
    with pytest.raises(ValueError, match="enough"):
        select_tasks(rows[:2], "seed")
