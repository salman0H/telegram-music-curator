"""Read-only diagnostic for tracks that logged provider failures in run 123."""
import os
import recommendations

TRACKS = [
    ('Lenny Loops', 'rainy day'),
    ('TOOL', 'Schism'),
    ("Destiny's Child", 'Birthday'),
    ('Chezile', 'Blue'),
    ('HIM', 'Join Me In Death'),
    ('Mob Entertainment', 'Lights Off'),
]

if __name__ == '__main__':
    if not os.environ.get('LASTFM_API_KEY'):
        raise SystemExit('LASTFM_API_KEY is missing')
    for artist, title in TRACKS:
        titles = recommendations.recommend_tracks(artist, title)
        print(f'[diagnostic] {artist} — {title}: {titles}')
