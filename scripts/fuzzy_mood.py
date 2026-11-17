"""Auditable musical-affect fuzzification; no inference about human wellbeing.

Mamdani min implication, max aggregation, numerical centroid over 401 samples.
Membership breakpoints and rule choices are heuristic, versioned, not learned.
"""
import math
from datetime import datetime

VERSION = 'mamdani-music-v1'
MIN_CONFIDENCE = 0.7

def valid_number(value, low, high):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and low <= value <= high

def partition(value):
    """Ruspini shoulder/triangle/shoulder partition on [-1, 1]."""
    return {'negative': max(0.0, -value), 'neutral': 1.0 - abs(value), 'positive': max(0.0, value)}

def centroid(heights, samples=401):
    if samples < 3 or samples % 2 != 1:
        raise ValueError('Use an odd grid of at least three samples')
    numerator = denominator = 0.0
    # Trapezoidal integration: half-weight the two endpoints.
    for i in range(samples):
        x = -1 + 2 * i / (samples - 1)
        membership = partition(x)
        y = max(min(heights.get(name, 0), degree) for name, degree in membership.items())
        weight = 0.5 if i in (0, samples - 1) else 1.0
        numerator += weight * x * y
        denominator += weight * y
    return numerator / denominator if denominator else None

def infer(mood):
    v, e, c = (mood.get(field) for field in ('valence', 'energy', 'confidence'))
    unknown = {'method': VERSION, 'status': 'unknown', 'memberships': {},
               'rules': [], 'valence_score': None, 'energy_score': None}
    if mood.get('label') == 'unknown' or not valid_number(v, -1, 1) or not valid_number(e, 0, 1) or not valid_number(c, 0, 1) or c < MIN_CONFIDENCE:
        return unknown
    vm, em = partition(v), partition(2 * e - 1)
    valence_names = {'negative': 'sad', 'neutral': 'neutral', 'positive': 'happy'}
    energy_names = {'negative': 'calm', 'neutral': 'moderate', 'positive': 'energetic'}
    rules, memberships = [], {}
    vh, eh = dict.fromkeys(vm, 0.0), dict.fromkeys(em, 0.0)
    for a, av in vm.items():
        for b, bv in em.items():
            firing = min(av, bv)
            if firing <= 0:
                continue
            label = valence_names[a] + '_' + energy_names[b]
            memberships[label] = firing
            rules.append({'if_valence': a, 'if_energy': b, 'then': label, 'activation': firing})
            # Each rule retains both linguistic coordinates as its consequent.
            vh[a] = max(vh[a], firing)
            eh[b] = max(eh[b], firing)
    return {'method': VERSION, 'status': 'estimated', 'memberships': memberships,
            'rules': rules, 'valence_score': centroid(vh), 'energy_score': (centroid(eh) + 1) / 2,
            'input_basis': mood.get('basis', 'unspecified'),
            'input_confidence': c, 'membership_is_probability': False}

def time_memberships(local_time):
    if not local_time:
        return {}
    time = datetime.fromisoformat(local_time)
    hour = time.hour + time.minute / 60 + time.second / 3600
    result = {}
    for name, center in [('night', 3), ('morning', 9), ('afternoon', 15), ('evening', 21)]:
        distance = abs((hour - center + 12) % 24 - 12)
        result[name] = max(0.0, 1.0 - distance / 6)
    return result

def summarize(events):
    """Source × model-confidence weighted mean; Kish n_eff is not a CI."""
    used, weighted, weights, memberships = 0, 0.0, [], {}
    for event in events:
        mood = event.get('music_mood', {})
        result = infer(mood)
        source_weight = event.get('preference_weight')
        if result['status'] != 'estimated' or not valid_number(source_weight, 1, 3):
            continue
        weight = source_weight * mood['confidence']
        used += 1
        weights.append(weight)
        weighted += weight * result['valence_score']
        for label, degree in result['memberships'].items():
            memberships[label] = memberships.get(label, 0) + weight * degree
    total = sum(weights)
    return {'method': VERSION, 'total': len(events), 'classified': used,
            'coverage': used / len(events) if events else 0,
            'valence': weighted / total if total else None,
            'memberships': {label: degree / total for label, degree in memberships.items()},
            'effective_sample_size': total * total / sum(w*w for w in weights) if weights else 0,
            'statistically_validated': False}
