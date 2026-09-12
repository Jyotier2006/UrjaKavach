from dataclasses import replace
from itertools import combinations
import math
import pytest
from services.api.app.domain.loss import Assumptions, expected_daily_energy_kwh, probability_of_failure, estimate_loss
from services.api.app.domain.downsample import lttb
from services.optimizer.scheduler import demo_jobs, PROFILES, optimize, access_open
from services.ml.criticality import criticality_counter


def test_energy_dimensions_and_conditional_hazard():
    a = Assumptions(capacity_mw=2, capacity_factor=.5)
    assert expected_daily_energy_kwh(a) == 24000
    probabilities = [probability_of_failure(d, a) for d in range(15)]
    assert probabilities[0] == 0
    assert probabilities == sorted(probabilities)
    assert all(0 <= p <= 1 for p in probabilities)


def test_loss_reproducible_ordered_uncertainty_and_delay():
    a = Assumptions()
    first = estimate_loss(a)
    assert first == estimate_loss(a)
    for point in first['curve']:
        assert point['p10'] <= point['p50'] <= point['p90']
    assert first['curve'][-1]['p50'] > first['curve'][0]['p50']
    assert first['repair_now']['p50'] == first['curve'][0]['p50']


def test_criticality_status_rules_and_recrossing():
    predicted = [True, True, True, False, False, True, True]
    status = [0, 1, 0, 1, 0, 0, 0]
    a = criticality_counter(predicted, status, farm='A', threshold=2)
    b = criticality_counter(predicted, status, farm='B', threshold=2)
    assert a['criticality'] == [1, 2, 3, 2, 1, 2, 3]
    assert a['crossings'] == [1, 5]
    assert b['criticality'] == [1, 1, 2, 2, 1, 2, 3]
    assert b['crossings'] == [2, 5]


@pytest.mark.parametrize('patch', [{'capacity_factor': 1.1}, {'tariff_inr_kwh': -1}, {'daily_hazard': math.nan}, {'capacity_mw': math.inf}])
def test_invalid_assumptions(patch):
    with pytest.raises(ValueError): estimate_loss(replace(Assumptions(), **patch))


def test_zero_uncertainty_has_zero_width_bands():
    result = estimate_loss(Assumptions(uncertainty_fraction=0))
    assert all(p['p10'] == p['p90'] for p in result['curve'])


@pytest.mark.parametrize('crew_count', [1, 2, 4])
def test_solver_hard_constraints_and_baselines(crew_count):
    jobs = demo_jobs(); crews = PROFILES['balanced'][:crew_count]
    plan = optimize(jobs, crews, 7)
    by_id = {j.id: j for j in jobs}
    assert plan['solver_status'] in {'OPTIMAL', 'FEASIBLE'}
    for policy in [plan, plan['baselines']['risk_first'], plan['baselines']['calendar']]:
        assert len({i['job_id'] for i in policy['items']}) == len(policy['items'])
        for item in policy['items']:
            job = by_id[item['job_id']]
            assert job.skill in crews[item['crew']]
            assert access_open(job, item['start_hour'])
            assert item['end_hour'] <= 7 * 24
            assert item['end_hour'] - item['start_hour'] == job.duration_hours
        for a, b in combinations(policy['items'], 2):
            if a['crew'] == b['crew']:
                travel = int(a['group'] != b['group'])
                assert a['end_hour'] + travel <= b['start_hour'] or b['end_hour'] + travel <= a['start_hour']


def test_missing_skills_parts_and_conflicting_lock_are_explained():
    plan = optimize(demo_jobs(delay=2, lock=True), PROFILES['electrical'][:1], 3)
    missing = {x['job_id']: x['reason'] for x in plan['unscheduled']}
    assert 'skill' in missing['J-101']
    assert 'Parts' in missing['J-106']
    locked = optimize(demo_jobs(delay=2, lock=True), PROFILES['balanced'][:2], 7)
    assert any(i['job_id'] == 'J-101' and 'conflicts' in i['reason'] for i in locked['unscheduled'])


def test_weather_missing_hours_fail_closed():
    plan = optimize(demo_jobs(), PROFILES['balanced'][:2], 3, weather=[])
    assert not plan['items']
    assert all('access' in i['reason'] or 'Parts' in i['reason'] for i in plan['unscheduled'])


def test_lttb_keeps_endpoints_and_large_spike():
    rows = [{'step': i, 'value': 100 if i == 49 else 0} for i in range(100)]
    sampled = lttb(rows, 10, 'value')
    assert len(sampled) == 10
    assert sampled[0] == rows[0] and sampled[-1] == rows[-1]
    assert any(p['step'] == 49 for p in sampled)
