# Opt-in ordinary Astra routes

The default `routes.example.json` stays empty. In your local routes, explicitly
clone your operator-owned `gpt-mid` mapping, retaining its source, provider,
account, pool, windows, host and capacity fields:

```python
base = next(r for r in config['routes'] if r['id'] == 'gpt-mid')
config['routes'] += [
    dict(base, id='gpt-astra', model='openai/gpt-6-astra', variant='high',
         categories=['research', 'implement', 'hard']),
    dict(base, id='gpt-astra-mid', model='openai/gpt-6-astra', variant='medium',
         categories=['research', 'implement']),
]
```

This is an explicit operator edit, not installation or extra quota. Verify the
operator provider catalog exposes the selected variant. Existing protected fast
transport exclusions remain unchanged.
