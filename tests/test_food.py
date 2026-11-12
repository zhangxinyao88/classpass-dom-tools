import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from food_adapter import parse_food, planning_food
from credit_planner import plan

ROOT = Path(__file__).resolve().parents[1]
CAP = json.loads((ROOT / 'examples/synthetic-food.json').read_text())
CONFIG = json.loads((ROOT / 'examples/synthetic-plan.json').read_text())


def parsed(capture=CAP):
    return parse_food(capture, '2026-11-13', 'America/New_York', 15)


def config():
    data = copy.deepcopy(CONFIG)
    data['opportunities'] = []
    data['history'] = []
    data['spend_target'] = 12
    data['preferences'].update(available_windows=[{
        'starts_at': '2026-11-13T11:00:00-05:00', 'ends_at': '2026-11-13T14:00:00-05:00'}],
        keyword_weights={'bowl': 10}, minimum_gap_minutes=0, max_events=3)
    return data


class FoodTests(unittest.TestCase):
    def test_slot_quotes_policy_and_explicit_planning_duration(self):
        result = parsed()
        self.assertEqual(len(result['opportunities']), 3)
        row = result['opportunities'][0]
        self.assertEqual(row['credits'], 6)
        self.assertEqual(row['starts_at'], '2026-11-13T12:00:00-05:00')
        self.assertEqual(row['ends_at'], '2026-11-13T12:15:00-05:00')
        self.assertEqual(row['displayed_duration_minutes'], 60)
        self.assertIsNone(row['pickup_window_ends_at'])
        self.assertIsNone(row['bookable'])
        self.assertTrue(row['noncancelable'])
        self.assertTrue(row['no_credit_refund_after_order'])
        self.assertFalse(result['complete_results'])
        self.assertEqual(row['id'], parsed()['opportunities'][0]['id'])

    def test_app_only_is_not_zero_inventory(self):
        capture = copy.deepcopy(CAP)
        capture.update(availability='app_only', item_name=None, date_heading=None, rows=[])
        result = parse_food(capture)
        self.assertEqual(result['opportunities'], [])
        self.assertIn('not_no_food_inventory', result['unavailable_reason'])
        planned = plan(config(), food_snapshot=result)
        self.assertEqual(planned['food_coverage']['availability'], 'app_only')
        self.assertEqual(planned['uncovered_spend_target'], 12)

    def test_no_cancellation_or_price_claim_without_labels(self):
        capture = copy.deepcopy(CAP)
        capture['policy_text'] = None
        for row in capture['rows']:
            row['credits_text'] = 'See pricing'
        result = parsed(capture)
        self.assertTrue(all(r['credits'] is None and r['noncancelable'] is None
            and r['no_credit_refund_after_order'] is None for r in result['opportunities']))
        planned = plan(config(), food_snapshot=result)
        self.assertEqual(planned['planned_credits'], 0)
        self.assertTrue(all(r['reason'] == 'unknown_current_credit_quote' for r in planned['skipped']))

    def test_exact_item_label_and_ambiguous_price(self):
        capture = copy.deepcopy(CAP)
        capture['rows'][0]['credits_text'] = 'Order Example Lunch Bowl for 7 credits'
        capture['rows'][1]['credits_text'] = '6 credits 8 credits'
        result = parsed(capture)
        self.assertEqual(result['opportunities'][0]['credits'], 7)
        self.assertIsNone(result['opportunities'][1]['credits'])

    def test_alternative_slots_do_not_become_repeated_orders(self):
        result = plan(config(), food_snapshot=parsed())
        self.assertEqual(result['planned_credits'], 6)
        self.assertEqual(result['uncovered_spend_target'], 6)
        self.assertEqual(len(result['items']), 1)
        self.assertEqual(result['items'][0]['kind'], 'food')
        self.assertEqual(result['actions_executed'], 0)

    def test_food_acknowledgement_and_disabled_action(self):
        data = config()
        data['preferences']['allow_nonrefundable_food'] = False
        self.assertEqual(plan(data, food_snapshot=parsed())['items'], [])
        capture = copy.deepcopy(CAP)
        for row in capture['rows']:
            row['action_disabled'] = True
        result = plan(config(), food_snapshot=parsed(capture))
        self.assertEqual(result['items'], [])
        self.assertTrue(all(r['reason'] == 'confirmed_unavailable' for r in result['skipped']))

    def test_higher_same_item_quote_is_not_favored_to_burn_credits(self):
        capture = copy.deepcopy(CAP)
        capture['rows'][2]['credits_text'] = '4 credits'
        result = plan(config(), food_snapshot=parsed(capture))
        self.assertEqual(result['planned_credits'], 4)
        self.assertEqual(result['reference_credit_coverage'], 4)
        self.assertEqual(len(result['items']), 1)

    def test_costlier_time_can_still_fit_a_preferred_class(self):
        capture = copy.deepcopy(CAP)
        capture['rows'][2]['credits_text'] = '4 credits'
        data = config()
        data['preferences']['keyword_weights']['class'] = 30
        data['opportunities'] = [{'id': 'class-compatible', 'kind': 'class', 'name': 'Example class',
            'venue': 'Example Studio', 'starts_at': '2026-11-13T12:45:00-05:00',
            'ends_at': '2026-11-13T13:45:00-05:00', 'credits': 5}]
        result = plan(data, food_snapshot=parsed(capture))
        self.assertEqual(result['planned_credits'], 11)
        self.assertEqual(result['reference_credit_coverage'], 9)
        self.assertEqual(len(result['items']), 2)

    def test_invalid_date_timezone_duplicate_and_private_url_fail(self):
        for field, value in [('date_heading', 'Sat, Nov 14'), ('rows', []),
                ('source_url', CAP['source_url'] + '?token=PRIVATE'), ('schema_version', True)]:
            bad = copy.deepcopy(CAP)
            bad[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                parsed(bad)
        bad = copy.deepcopy(CAP)
        bad['rows'][0]['time_text'] = '12:00 PM EDT 60 min'
        with self.assertRaises(ValueError):
            parsed(bad)
        bad = copy.deepcopy(CAP)
        bad['rows'].append(copy.deepcopy(bad['rows'][0]))
        with self.assertRaises(ValueError):
            parsed(bad)

    def test_dst_ambiguity_and_missing_block_fail(self):
        bad = copy.deepcopy(CAP)
        bad['date_heading'] = 'Sun, Nov 1'
        bad['rows'] = [dict(bad['rows'][0], time_text='1:30 AM EDT')]
        with self.assertRaises(ValueError):
            parse_food(bad, '2026-11-01', 'America/New_York', 15)
        for block in (None, 0, 181, True):
            with self.subTest(block=block), self.assertRaises(ValueError):
                parse_food(CAP, '2026-11-13', 'America/New_York', block)

    def test_inconsistent_food_snapshot_rejected(self):
        bad = parsed()
        bad['opportunities'][0]['choice_group'] = 'invented-other-group'
        with self.assertRaises(ValueError):
            planning_food(bad)

    def test_cli_private_ingest_and_planning_end_to_end(self):
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            output = directory / 'food.json'
            ingest = subprocess.run([sys.executable, str(ROOT / 'ingest_capture.py'), 'food',
                '--output', str(output), '--date', '2026-11-13', '--timezone', 'America/New_York',
                '--block-minutes', '15'], input=json.dumps(CAP), capture_output=True, text=True, check=True)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            self.assertEqual(json.loads(ingest.stdout)['count'], 3)
            self.assertNotIn('Example Lunch Bowl', ingest.stdout)
            file = directory / 'config.json'
            file.write_text(json.dumps(config()))
            result = subprocess.run([sys.executable, str(ROOT / 'credit_planner.py'), str(file),
                '--food-snapshot', str(output)], capture_output=True, text=True, check=True)
            self.assertEqual(json.loads(result.stdout)['planned_credits'], 6)
            direct = subprocess.run([sys.executable, str(ROOT / 'classpass_cli.py'), 'parse-food',
                str(ROOT / 'examples/synthetic-food.json'), '--date', '2026-11-13', '--timezone',
                'America/New_York', '--block-minutes', '15'], capture_output=True, text=True, check=True)
            self.assertEqual(len(json.loads(direct.stdout)['opportunities']), 3)


if __name__ == '__main__':
    unittest.main()
