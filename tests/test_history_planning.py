import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from credit_planner import plan
from history_adapter import parse_history
from history_bridge import planning_history

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = json.loads((ROOT / 'examples/synthetic-history.json').read_text())
CONFIG = json.loads((ROOT / 'examples/synthetic-plan.json').read_text())


class HistoryPlanningTests(unittest.TestCase):
    def test_unknown_dates_categories_statuses_and_prices_are_preserved(self):
        records, coverage = planning_history(parse_history(CAPTURE))
        self.assertEqual([r['card_variant'] for r in records], ['reservation', 'order'])
        self.assertTrue(all(r['kind'] == 'unknown' for r in records))
        self.assertTrue(all(r['status'] == 'past_listed' for r in records))
        self.assertTrue(all(r['year'] is None and r['timezone'] is None and r['credits'] is None for r in records))
        self.assertEqual(records[0]['date_displayed'], 'Feb 29, 1:00 PM')
        self.assertEqual(records[0]['displayed_credits'], 4)
        self.assertEqual(coverage['captured_count'], 2)
        self.assertEqual(coverage['displayed_total'], 3)
        self.assertFalse(coverage['complete_history'])

    def test_rating_matches_item_without_inventing_attendance_or_paid_price(self):
        config = copy.deepcopy(CONFIG)
        config['history'] = []
        result = plan(config, parse_history(CAPTURE))
        item = next(r for r in result['items'] if r['id'] == 'class-a')
        self.assertEqual(item['credits'], 5)
        self.assertEqual(item['explicit_history_rating_bonus'], 20)
        self.assertEqual(item['completed_visits_in_supplied_history'], 0)
        self.assertEqual(item['matching_past_cards'], 1)
        self.assertIsNone(item['past_paid_credits_median'])
        self.assertEqual(item['past_displayed_credits_median'], 4)
        self.assertEqual(result['history_completeness'], 'partial_rendered_history')

    def test_one_hundred_synthetic_cards_keep_126_total_and_99_1_variants(self):
        capture = copy.deepcopy(CAPTURE)
        capture['displayed_total'] = 126
        capture['rows'] = [copy.deepcopy(CAPTURE['rows'][0]) for _ in range(99)] + [copy.deepcopy(CAPTURE['rows'][1])]
        config = copy.deepcopy(CONFIG)
        config['history'] = []
        result = plan(config, parse_history(capture))
        coverage = result['history_coverage']
        self.assertEqual((coverage['captured_count'], coverage['displayed_total']), (100, 126))
        self.assertEqual((coverage['reservation_card_count'], coverage['order_card_count']), (99, 1))
        self.assertEqual(coverage['missing_year_count'], 100)
        self.assertEqual(coverage['attendance_unverified_count'], 100)
        self.assertFalse(coverage['complete_history'])

    def test_unrated_listed_cards_do_not_imply_liking(self):
        capture = copy.deepcopy(CAPTURE)
        capture['rows'][0]['rating_text'] = None
        config = copy.deepcopy(CONFIG)
        config['history'] = []
        config['spend_target'] = 0
        config['preferences']['keyword_weights'] = {}
        self.assertEqual(plan(config, parse_history(capture))['items'], [])

    def test_partial_counts_and_unknowns_cannot_be_overwritten(self):
        normalized = parse_history(CAPTURE)
        for field, value in [('complete_history', True), ('captured_count', 1)]:
            bad = copy.deepcopy(normalized)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                planning_history(bad)
        bad = copy.deepcopy(normalized)
        bad['items'][0]['year'] = 2026
        with self.assertRaises(ValueError):
            planning_history(bad)

    def test_cli_capture_normalize_search_and_plan_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            cli = [sys.executable, str(ROOT / 'classpass_cli.py')]
            h = subprocess.run(cli + ['parse-history', str(ROOT / 'examples/synthetic-history.json')], capture_output=True, text=True, check=True)
            s = subprocess.run(cli + ['parse-search', str(ROOT / 'examples/synthetic-search.json'), '--date', '2026-11-13', '--timezone', 'America/New_York'], capture_output=True, text=True, check=True)
            history = directory / 'history.json'; history.write_text(h.stdout)
            search = directory / 'search.json'; search.write_text(s.stdout)
            config = copy.deepcopy(CONFIG)
            config['opportunities'] = []
            config['history'] = []
            input_file = directory / 'plan.json'; input_file.write_text(json.dumps(config))
            p = subprocess.run([sys.executable, str(ROOT / 'credit_planner.py'), str(input_file),
                '--search-snapshot', str(search), '--kind', 'class', '--history-snapshot', str(history)], capture_output=True, text=True, check=True)
            result = json.loads(p.stdout)
            self.assertEqual(result['planned_credits'], 7)
            self.assertEqual(result['uncovered_spend_target'], 1)
            self.assertEqual(result['items'][0]['past_displayed_credits_median'], 4)
            self.assertEqual(result['history_coverage']['displayed_total'], 3)
            self.assertEqual(result['actions_executed'], 0)


if __name__ == '__main__':
    unittest.main()
