<p align="center"><img src="assets/logo.png" alt="Oddculator by Odds Intelligence" width="600"></p>

# Oddculator

Discord slash-command betting calculator. Results are only visible to the member who ran the command.

| Command | What it does |
|---|---|
| `/payout stake odds` | Profit, total return, break-even probability |
| `/parlay stake legs` | Combined odds and payout (legs separated by commas or spaces) |
| `/novig odds_a odds_b` | Vig and fair probabilities/odds |
| `/ev odds win_prob [bankroll] [kelly_fraction]` | EV, edge, Kelly stake |
| `/hedge stake odds hedge_odds` | Equal-profit hedge stake |
| `/build1line ml rl15 [opp_ml] [opp_rl15]` | Fair -1 run/puck line from the ML and -1.5 price |
| `/minus1 ml rl15 alt1 [opp_ml] [opp_rl15]` | EV of an offered -1 price vs. the fair line |
| `/convert odds` | American / decimal / implied probability |

Odds are auto-detected: `-110`, `+150`, or `1.91`.

## Run

```bash
cp .env.example .env   # set DISCORD_TOKEN, optionally GUILD_ID
docker compose pull && docker compose up -d
```

To build locally instead: `docker compose up -d --build`.

## Image

GitHub Actions builds and pushes `ghcr.io/tw1zt3d2four7/oddculator` on every push to `main` (`latest`, `sha-*`) and on `v*` tags (`1.2.3`). Pull requests build without pushing.
