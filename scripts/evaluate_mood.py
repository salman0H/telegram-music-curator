"""Evaluate a frozen model on independent human musical-valence labels.
Input JSON: [{"model_valence":0.4,"human_valence":0.2,"energy":0.5,"confidence":0.8}].
No Telegram fetching, model fitting or personal wellbeing targets.
"""
import argparse
import json
from fuzzy_mood import infer, valid_number, VERSION

def evaluate(rows):
    raw_errors, fuzzy_errors = [], []
    for row in rows:
        if not valid_number(row.get('human_valence'), -1, 1):
            raise ValueError('Each human_valence must be finite and within [-1,1]')
        result = infer({'label': 'estimated', 'valence': row.get('model_valence'),
                        'energy': row.get('energy'), 'confidence': row.get('confidence')})
        if result['status'] == 'unknown':
            continue
        target = row['human_valence']
        raw_errors.append(abs(row['model_valence'] - target))
        fuzzy_errors.append(abs(result['valence_score'] - target))
    n = len(fuzzy_errors)
    return {'method': VERSION, 'total': len(rows), 'evaluated': n,
            'coverage': n / len(rows) if rows else 0,
            'raw_mae': sum(raw_errors)/n if n else None,
            'fuzzy_mae': sum(fuzzy_errors)/n if n else None,
            'validity_note': 'Held-out labels required; lower MAE is better; fuzzy may be worse. No clinical validation.'}

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('labels')
    args=parser.parse_args()
    with open(args.labels, encoding='utf-8') as stream:
        print(json.dumps(evaluate(json.load(stream)), indent=2))
