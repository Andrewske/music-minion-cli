# Kevin's SoundCloud feed taste profile

Edit this file freely; every change produces a new taste_profile_version and
future predictions are scored against the new text.

## Who is deciding

Kevin curates a bass-music library from his SoundCloud feed. "Keep" means the
track is good enough to save to his library and monthly playlist. He keeps
roughly 1 in 4 surfaced tracks, and is picky: a decent-but-forgettable track
is a nope.

## Genres

- Core: dubstep (highest keep rate, ~36%), riddim, bass music, dance & edm.
- Sometimes: melodic bass, electronic, drum & bass.
- Rarely kept: trap (~4%), house (~0%), techno, lo-fi, ambient.
- Missing genre tags are common and not a negative signal by themselves.

## Artists and reposters

- Top-ranked artists he follows (rank 1 is best): GRiZ, Subtronics, Zomboy,
  REZZ, Space Wizard, TYNAN, Virtual Riot, Levity, Kill The Noise, Blanke,
  Excision, Crankdat, LYNY, TVBOO, LSDREAM.
- A track uploaded by a followed artist with rank <= 25 is a strong keep signal.
- Multiple reposters inside his top 200 is a strong keep signal; a single
  unranked reposter is weak.
- Per-artist keep rates in the state are Bayesian-smoothed history of his own
  decisions; trust them over genre when they conflict.

## Track shape

- Sweet spot: 2-4 minute singles (nearly all keeps live here).
- Over 4 minutes keeps drop sharply; over 7 minutes is almost never kept.
- DJ mixes, radio shows, podcasts, and full sets are almost always nope.
- Remixes, edits, flips, and bootlegs of tracks he likes are favored.

## Recency

- Fresh releases (days old) are favored over tracks resurfacing months later.
- A repost of an old track by a top reposter can still be a keep.
