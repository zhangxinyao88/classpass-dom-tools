import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credit_planner import PlanError, plan

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = json.loads((ROOT / 'examples/synthetic-plan.json').read_text())


class PlannerTests(unittest.TestCase):
    def test_class_food_plan_budget_and_history(self):
        result = plan(EXAMPLE)
        self.assertEqual([row['id'] for row in result['items']], ['class-a', 'food-a'])
        self.assertEqual(result['planned_credits'], 8)
        self.assertEqual(result['projected_credits_remaining'], 4)
        self.assertEqual(result['uncovered_spend_target'], 0)
        self.assertEqual(result['items'][0]['past_paid_credits_median'], 4)
        self.assertEqual(result['items'][0]['credits'], 5)
        self.assertEqual(result['actions_executed'], 0)
        self.assertEqual(result, plan(EXAMPLE))

    def test_food_requires_explicit_acknowledgement(self):
        data = copy.deepcopy(EXAMPLE)
        data['preferences']['allow_nonrefundable_food'] = False
        result = plan(data)
        self.assertNotIn('food-a', [r['id'] for r in result['items']])
        self.assertIn({'id': 'food-a', 'reason': 'nonrefundable_food_not_acknowledged'}, result['skipped'])

    def test_travel_gap_and_busy_calendar_constraints(self):
        data = copy.deepcopy(EXAMPLE)
        data['preferences']['minimum_gap_minutes'] = 20
        result = plan(data)
        self.assertEqual(len(result['items']), 1)
        data['preferences']['busy_windows'] = [{'starts_at': '2026-11-13T17:00:00-05:00', 'ends_at': '2026-11-13T18:15:00-05:00'}]
        self.assertEqual(plan(data)['items'], [])

    def test_unknown_price_skipped_not_inferred_from_history(self):
        data = copy.deepcopy(EXAMPLE)
        data['opportunities'][0]['credits'] = None
        result = plan(data)
        self.assertIn({'id': 'class-a', 'reason': 'unknown_current_credit_quote'}, result['skipped'])
        self.assertNotIn('class-a', [r['id'] for r in result['items']])

    def test_attendance_and_cancellation_do_not_imply_liking(self):
        data = copy.deepcopy(EXAMPLE)
        data['history'][0].pop('rating')
        result = plan(data)
        first = next(r for r in result['items'] if r['id'] == 'class-a')
        self.assertEqual(first['explicit_history_rating_bonus'], 0)
        data['history'][0]['rating'] = 5
        data['history'][0]['status'] = 'cancelled'
        first = next(r for r in plan(data)['items'] if r['id'] == 'class-a')
        self.assertEqual(first['completed_visits_in_supplied_history'], 0)
        self.assertEqual(first['explicit_history_rating_bonus'], 0)

    def test_zero_target_does_not_force_spend_without_preferences(self):
        data = copy.deepcopy(EXAMPLE)
        data['spend_target'] = 0
        data['history'] = []
        data['preferences']['keyword_weights'] = {}
        result = plan(data)
        self.assertEqual(result['items'], [])
        self.assertEqual(result['projected_credits_remaining'], 12)

    def test_negative_preference_does_not_burn_credits(self):
        data = copy.deepcopy(EXAMPLE)
        data['preferences']['keyword_weights'] = {'yin': -100, 'coffee': -100, 'strength': -100}
        self.assertEqual(plan(data)['items'], [])
        self.assertEqual(plan(data)['uncovered_spend_target'], 8)

    def test_input_bounds_and_timezone(self):
        data = copy.deepcopy(EXAMPLE)
        data['as_of'] = '2026-11-12T12:00:00'
        with self.assertRaises(PlanError):
            plan(data)
        data = copy.deepcopy(EXAMPLE)
        data['opportunities'] += [dict(data['opportunities'][0])]
        with self.assertRaises(PlanError):
            plan(data)
        data = copy.deepcopy(EXAMPLE)
        data['spend_target'] = 13
        with self.assertRaises(PlanError):
            plan(data)

    def test_explicit_unavailability_is_respected(self):
        data = copy.deepcopy(EXAMPLE)
        for row in data['opportunities']:
            row['bookable'] = False
        result = plan(data)
        self.assertEqual(result['items'], [])
        self.assertTrue(all(r['reason'] == 'confirmed_unavailable' for r in result['skipped']))

    def test_next_cycle_offerings_do_not_reduce_current_credit_risk(self):
        data = copy.deepcopy(EXAMPLE)
        data['credit_cycle_ends_at'] = '2026-11-13T16:30:00-05:00'
        result = plan(data)
        self.assertEqual(result['planned_credits'], 0)
        self.assertEqual(result['uncovered_spend_target'], 8)
        self.assertTrue(all(row['reason'] == 'outside_current_credit_cycle' for row in result['skipped']))

    def test_existing_search_output_can_be_used_without_browser(self):
        with tempfile.TemporaryDirectory() as directory:
            args = [sys.executable, str(ROOT / 'classpass_cli.py')]
            parsed = subprocess.run(args + ['parse-search', str(ROOT / 'examples/synthetic-search.json'),
                '--date', '2026-11-13', '--timezone', 'America/New_York'], capture_output=True, text=True, check=True)
            snapshot = Path(directory) / 'snapshot.json'
            snapshot.write_text(parsed.stdout)
            data = copy.deepcopy(EXAMPLE)
            data['opportunities'] = []
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps(data))
            result = subprocess.run([sys.executable, str(ROOT / 'credit_planner.py'), str(config),
                '--search-snapshot', str(snapshot), '--kind', 'class'], capture_output=True, text=True, check=True)
            value = json.loads(result.stdout)
            self.assertEqual(value['planned_credits'], 7)
            self.assertEqual(value['uncovered_spend_target'], 1)
            self.assertEqual(value['actions_executed'], 0)
    def test_cli_error_does_not_echo_account_input(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / 'input.json'
            file.write_text('{"PRIVATE_ACCOUNT_MARKER":true}')
            run = subprocess.run([sys.executable, str(ROOT / 'credit_planner.py'), str(file)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertNotIn('PRIVATE_ACCOUNT_MARKER', run.stdout + run.stderr)
            self.assertEqual(run.stdout, '')
            self.assertNotIn('Traceback', run.stderr)


if __name__ == '__main__':
    unittest.main()
