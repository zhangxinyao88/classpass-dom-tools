#!/usr/bin/env python3
"""Offline credit-use planning over supplied class/food snapshots; no network."""
import argparse
from datetime import datetime, timedelta
import json
from pathlib import Path
from statistics import mean, median
import sys
from history_bridge import planning_history
from food_adapter import planning_food


class PlanError(ValueError):
    pass


def timestamp(value):
    if not isinstance(value, str):
        raise PlanError('Expected an ISO 8601 timestamp.')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.utcoffset() is None:
        raise PlanError('All timestamps must include UTC offsets.')
    return result


def integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise PlanError('Invalid integer or value outside supported bounds.')
    return value


def windows(values):
    if not isinstance(values, list):
        raise PlanError('Time windows must be an array.')
    result = []
    for row in values:
        start, end = timestamp(row['starts_at']), timestamp(row['ends_at'])
        if end <= start:
            raise PlanError('Time windows must have positive duration.')
        result.append((start, end))
    return result


def history_profile(rows):
    """Use explicit ratings; retain the distinction between listed cards and visits."""
    if not isinstance(rows, list) or len(rows) > 1000:
        raise PlanError('History must be an array of at most 1000 records.')
    groups = {}
    for row in rows:
        status = row.get('status')
        if status not in ('attended', 'completed', 'past_listed'):
            continue
        if row.get('kind') not in ('class', 'food', 'unknown'):
            raise PlanError('Unsupported history offering category.')
        key = (row['kind'], row['venue'].casefold(), row['name'].casefold())
        group = groups.setdefault(key, {'ratings': [], 'credits': [], 'displayed_credits': [], 'visits': 0, 'past_cards': 0})
        if status == 'past_listed':
            group['past_cards'] += 1
        else:
            group['visits'] += 1
        if row.get('rating') is not None:
            group['ratings'].append(integer(row['rating'], 1, 5))
        if status != 'past_listed' and row.get('credits') is not None:
            group['credits'].append(integer(row['credits'], 0, 1000))
        if status == 'past_listed' and row.get('displayed_credits') is not None:
            group['displayed_credits'].append(integer(row['displayed_credits'], 0, 1000))
    return groups


def plan(data, history_snapshot=None, food_snapshot=None):
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise PlanError('Unsupported planning input schema.')
    now = timestamp(data['as_of'])
    cycle_end = timestamp(data['credit_cycle_ends_at'])
    if cycle_end <= now:
        raise PlanError('Credit cycle must end after the planning timestamp.')
    budget = integer(data['available_credits'], 0, 1000)
    target = integer(data['spend_target'], 0, budget)
    prefs = data['preferences']
    available = windows(prefs['available_windows'])
    busy = windows(prefs.get('busy_windows', []))
    max_events = integer(prefs.get('max_events', 4), 0, 8)
    gap = timedelta(minutes=integer(prefs.get('minimum_gap_minutes', 0), 0, 180))
    max_cost = integer(prefs.get('max_credits_per_item', budget), 0, 1000)
    allow_food = prefs.get('allow_nonrefundable_food', False)
    if type(allow_food) is not bool:
        raise PlanError('Food acknowledgement must be a boolean.')
    excluded = prefs.get('exclude_keywords', [])
    if not isinstance(excluded, list) or not all(isinstance(x, str) and x for x in excluded):
        raise PlanError('Excluded keywords must be nonempty strings.')
    keyword_weights = prefs.get('keyword_weights', {})
    venue_weights = prefs.get('venue_weights', {})
    for mapping in (keyword_weights, venue_weights):
        if not isinstance(mapping, dict):
            raise PlanError('Preference weights must be objects.')
        for key, weight in mapping.items():
            if not isinstance(key, str) or not key:
                raise PlanError('Preference names must be nonempty strings.')
            integer(weight, -100, 100)
    history_rows = data.get('history', [])
    if not isinstance(history_rows, list):
        raise PlanError('History must be an array.')
    history_coverage = None
    if history_snapshot is not None:
        imported, history_coverage = planning_history(history_snapshot)
        history_rows = history_rows + imported
    profile = history_profile(history_rows)
    food_coverage = None
    raw = data.get('opportunities', []) if food_snapshot is not None else data['opportunities']
    if food_snapshot is not None:
        imported_food, food_coverage = planning_food(food_snapshot)
        if not isinstance(raw, list):
            raise PlanError('Opportunities must be an array.')
        raw = raw + imported_food
    if not isinstance(raw, list) or len(raw) > 500:
        raise PlanError('At most 500 supplied opportunities are supported.')
    eligible, skipped, seen = [], [], set()
    for row in raw:
        if not isinstance(row, dict):
            raise PlanError('Opportunities must be objects.')
        for key in ('id', 'name', 'venue', 'kind'):
            if not isinstance(row.get(key), str) or not row[key]:
                raise PlanError('Incomplete opportunity.')
        if row['id'] in seen or row['kind'] not in ('class', 'food'):
            raise PlanError('Duplicate ID or unsupported opportunity kind.')
        seen.add(row['id'])
        choice_group = row.get('choice_group')
        if choice_group is not None and (not isinstance(choice_group, str) or not choice_group or len(choice_group) > 200):
            raise PlanError('Invalid mutually exclusive choice group.')
        start, end = timestamp(row['starts_at']), timestamp(row['ends_at'])
        if end <= start:
            raise PlanError('Opportunity duration must be positive.')
        text = (row['name'] + ' ' + row['venue']).casefold()
        reason = None
        if row.get('credits') is None:
            reason = 'unknown_current_credit_quote'
        else:
            integer(row['credits'], 1, 1000)
            if row['credits'] > min(budget, max_cost):
                reason = 'over_budget_or_item_limit'
        if start <= now:
            reason = 'already_started'
        elif end > cycle_end or start >= cycle_end:
            reason = 'outside_current_credit_cycle'
        elif not any(a <= start and end <= b for a, b in available):
            reason = 'outside_available_windows'
        elif any(start < b + gap and end + gap > a for a, b in busy):
            reason = 'busy_or_travel_buffer_conflict'
        elif any(word.casefold() in text for word in excluded):
            reason = 'excluded_by_preference'
        elif row.get('bookable') is False:
            reason = 'confirmed_unavailable'
        elif row['kind'] == 'food' and not allow_food:
            reason = 'nonrefundable_food_not_acknowledged'
        if reason:
            skipped.append({'id': row['id'], 'reason': reason})
            continue
        suffix = (row['venue'].casefold(), row['name'].casefold())
        prior = [profile.get((kind,) + suffix, {}) for kind in (row['kind'], 'unknown')]
        score = sum(weight for word, weight in keyword_weights.items() if word.casefold() in text)
        score += sum(weight for name, weight in venue_weights.items() if name.casefold() == row['venue'].casefold())
        ratings = [value for group in prior for value in group.get('ratings', [])]
        old_credits = [value for group in prior for value in group.get('credits', [])]
        old_displayed = [value for group in prior for value in group.get('displayed_credits', [])]
        history_bonus = round((mean(ratings) - 3) * 10) if ratings else 0
        if score + history_bonus < 0:
            skipped.append({'id': row['id'], 'reason': 'negative_preference_score'})
            continue
        normalized = {key: row[key] for key in ('id', 'kind', 'name', 'venue', 'starts_at', 'ends_at', 'credits')}
        if choice_group is not None:
            normalized['choice_group'] = choice_group
        if row['kind'] == 'food':
            for field in ('noncancelable', 'no_credit_refund_after_order'):
                if field in row:
                    if row[field] is not None and type(row[field]) is not bool:
                        raise PlanError('Invalid food policy flag.')
                    normalized[field] = row[field]
            for field in ('food_quote_basis', 'planning_duration_basis'):
                if field in row:
                    if row[field] is not None and (not isinstance(row[field], str) or len(row[field]) > 100):
                        raise PlanError('Invalid food evidence label.')
                    normalized[field] = row[field]
        normalized.update({'utility': score + history_bonus, 'explicit_history_rating_bonus': history_bonus,
            'completed_visits_in_supplied_history': sum(group.get('visits', 0) for group in prior),
            'matching_past_cards': sum(group.get('past_cards', 0) for group in prior),
            'past_paid_credits_median': median(old_credits) if old_credits else None,
            'past_displayed_credits_median': median(old_displayed) if old_displayed else None,
            'history_match_basis': 'item_and_venue_text_without_category_or_year_inference',
            'bookable': None})
        eligible.append((start, end, normalized))
    if len(eligible) > 20:
        raise PlanError('More than 20 eligible opportunities; narrow date/time/preferences before planning.')
    eligible.sort(key=lambda item: (item[0], item[2]['id']))
    food_group_floor = {}
    for _, _, row in eligible:
        if row['kind'] == 'food' and row.get('choice_group'):
            group = row['choice_group']
            food_group_floor[group] = min(food_group_floor.get(group, row['credits']), row['credits'])
    best = {'objective': (-1, 0, 0), 'items': [], 'credits': 0, 'reference_credits': 0, 'ids': ()}

    def visit(index, spent, utility, chosen, last_end, reference_credits):
        # Alternative quotes for the same meal must not gain value just by costing more.
        objective = (min(reference_credits, target), utility, -spent)
        ids = tuple(row['id'] for row in chosen)
        if objective > best['objective'] or (objective == best['objective'] and ids < best['ids']):
            best.update(objective=objective, items=list(chosen), credits=spent,
                reference_credits=reference_credits, ids=ids)
        if index == len(eligible) or len(chosen) == max_events:
            return
        start, end, row = eligible[index]
        group_used = row.get('choice_group') is not None and any(
            previous.get('choice_group') == row['choice_group'] for previous in chosen)
        if not group_used and spent + row['credits'] <= budget and (last_end is None or start >= last_end + gap):
            reference = food_group_floor.get(row.get('choice_group'), row['credits']) if row['kind'] == 'food' else row['credits']
            visit(index + 1, spent + row['credits'], utility + row['utility'], chosen + [row], end,
                reference_credits + reference)
        visit(index + 1, spent, utility, chosen, last_end, reference_credits)

    visit(0, 0, 0, [], None, 0)
    return {'schema_version': 1, 'scope': 'provided_candidates_only', 'freshness': 'not_revalidated',
        'available_credits': budget, 'caller_supplied_spend_target': target,
        'credit_cycle_ends_at': cycle_end.isoformat(),
        'planned_credits': best['credits'], 'projected_credits_remaining': budget - best['credits'],
        'reference_credit_coverage': best['reference_credits'],
        'reference_target_shortfall': max(0, target - best['reference_credits']),
        'uncovered_spend_target': max(0, target - best['credits']),
        'utility': best['objective'][1], 'items': best['items'], 'skipped': skipped,
        'history_completeness': 'partial_rendered_history' if history_coverage else 'unverified',
        'history_coverage': history_coverage, 'eligible_opportunities': len(eligible),
        'food_coverage': food_coverage,
        'actions_executed': 0,
        'objective': 'cover_reference_credit_target_then_preference_then_smallest_spend',
        'notes': ['spend_target_is_not_an_expiry_estimate',
                  'past_paid_credits_are_not_current_prices',
                  'past_cards_do_not_prove_attendance_or_final_paid_price',
                  'same_food_alternatives_use_lowest_eligible_quote_as_reference_not_actual_spend',
                  'no_booking_or_live_availability_check']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', help='Normalized planning JSON; see synthetic-plan.json')
    parser.add_argument('--search-snapshot', help='Optional existing parse-search output to append as candidates')
    parser.add_argument('--kind', choices=('class', 'food'), help='Explicit kind for appended search rows')
    parser.add_argument('--history-snapshot', help='Optional existing parse-history output; partial evidence only')
    parser.add_argument('--food-snapshot', help='Optional normalized parse-food output; one selected item')
    args = parser.parse_args()
    try:
        with Path(args.input).open('rb') as file:
            raw = file.read(5 * 1024 * 1024 + 1)
        if len(raw) > 5 * 1024 * 1024:
            raise PlanError('Input exceeds 5 MiB.')
        data = json.loads(raw)
        if bool(args.search_snapshot) != bool(args.kind):
            raise PlanError('Supply search snapshot and its explicit kind together.')
        if args.search_snapshot:
            with Path(args.search_snapshot).open('rb') as file:
                snapshot_raw = file.read(5 * 1024 * 1024 + 1)
            if len(snapshot_raw) > 5 * 1024 * 1024:
                raise PlanError('Snapshot exceeds 5 MiB.')
            snapshot = json.loads(snapshot_raw)
            if snapshot.get('schema_version') != 1 or snapshot.get('scope') != 'rendered_search_snapshot':
                raise PlanError('Expected normalized parse-search output.')
            data['opportunities'] = list(data.get('opportunities', []))
            for row in snapshot['classes']:
                data['opportunities'].append({'id': row['source_url'], 'kind': args.kind,
                    'name': row['name'], 'venue': row['studio'], 'credits': row['credits'],
                    'starts_at': row['starts_at'], 'ends_at': row['ends_at'], 'bookable': row.get('bookable')})
        history_snapshot = None
        if args.history_snapshot:
            with Path(args.history_snapshot).open('rb') as file:
                history_raw = file.read(5 * 1024 * 1024 + 1)
            if len(history_raw) > 5 * 1024 * 1024:
                raise PlanError('History snapshot exceeds 5 MiB.')
            history_snapshot = json.loads(history_raw)
        food_snapshot = None
        if args.food_snapshot:
            with Path(args.food_snapshot).open('rb') as file:
                food_raw = file.read(5 * 1024 * 1024 + 1)
            if len(food_raw) > 5 * 1024 * 1024:
                raise PlanError('Food snapshot exceeds 5 MiB.')
            food_snapshot = json.loads(food_raw)
        print(json.dumps(plan(data, history_snapshot, food_snapshot), sort_keys=True, ensure_ascii=False, separators=(',', ':')))
        return 0
    except (ValueError, KeyError, TypeError, AttributeError, OSError, RecursionError):
        # Do not echo account input, filenames or raw exception details.
        print(json.dumps({'error': 'Invalid or unsupported planning input.'}), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
