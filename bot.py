"""Oddculator: Discord betting calculator bot.

Slash commands: /payout /parlay /novig /ev /hedge /minus1 /build1line /convert
Odds are auto-detected everywhere: -110, +150, or decimal like 1.91.
"""
import logging
import math
import os
import re

import discord
from discord import app_commands

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

log = logging.getLogger("oddculator")
GREEN, RED, BLUE = 0x2ECC71, 0xE74C3C, 0x5865F2
BRAND = "Oddculator by Odds Intelligence"
ICON_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "icon.png")


# ---------- math helpers ----------
def parse_odds(s) -> float:
    """American (-110, +150) or decimal (1.91) -> decimal odds."""
    t = str(s).strip().replace("\u2212", "-")
    try:
        n = float(t)
    except (TypeError, ValueError):
        raise ValueError(f"`{s}` isn't valid odds. Use -110, +150, or 1.91.")
    if not math.isfinite(n):
        raise ValueError("Odds must be a finite number.")
    if abs(n) >= 100:
        decimal = 1 + n / 100 if n > 0 else 1 + 100 / -n
        if not math.isfinite(decimal) or decimal <= 1:
            raise ValueError("Odds must convert to decimal odds greater than 1.")
        return decimal
    if n > 1:
        return n
    raise ValueError(f"`{s}` isn't valid odds. American odds need a magnitude of 100+, decimal odds must be above 1.")


def to_american(d: float) -> str:
    return f"+{round((d - 1) * 100)}" if d >= 2 else f"{round(-100 / (d - 1))}"


def money(x: float) -> str:
    return f"{'-' if x < 0 else ''}${abs(x):,.2f}"


def pct(x: float, nd: int = 2) -> str:
    return f"{x * 100:.{nd}f}%"


def fair_prob(odds, opp=None) -> float:
    """Implied probability, de-vigged against the opposite side when given."""
    p = 1 / parse_odds(odds)
    if opp is not None:
        q = 1 / parse_odds(opp)
        p = p / (p + q)
    return p


def positive(x: float, name: str) -> float:
    if not math.isfinite(x) or x <= 0:
        raise ValueError(f"{name} must be a finite number above 0.")
    return x


def build_minus1(ml, rl15, opp_ml=None, opp_rl15=None) -> dict:
    """Build a -1 line (win by 2+ wins, win by exactly 1 pushes) from the ML and -1.5 prices."""
    p_ml, p_rl = fair_prob(ml, opp_ml), fair_prob(rl15, opp_rl15)
    if not (0 < p_rl < p_ml < 1):
        raise ValueError("Inputs must produce valid probabilities: the -1.5 win probability must be above 0 and below the moneyline win probability.")
    w, push, l = p_rl, p_ml - p_rl, 1 - p_ml
    return {"p_ml": p_ml, "w": w, "push": push, "l": l,
            "fair_dec": 1 + l / w, "breakeven": w / (w + l)}


def odds_embed_ok(title, color, fields, desc=None, footer=None) -> discord.Embed:
    e = discord.Embed(title=title, description=desc, color=color)
    e.set_author(name=BRAND, icon_url="attachment://icon.png")
    for name, value, inline in fields:
        e.add_field(name=name, value=value, inline=inline)
    if footer:
        e.set_footer(text=footer)
    return e


# ---------- bot ----------
class Bot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        gid = os.environ.get("GUILD_ID", "").strip()
        if gid:  # guild sync is instant; global sync can take up to an hour
            guild = discord.Object(id=int(gid))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        else:
            await self.tree.sync()

    async def on_ready(self):
        log.info("Logged in as %s", self.user)


bot = Bot()
tree = bot.tree


async def respond(inter: discord.Interaction, build):
    try:
        embed = build()
        await inter.response.send_message(embed=embed, file=discord.File(ICON_PATH, filename="icon.png"), ephemeral=True)
    except ValueError as e:
        await inter.response.send_message(f"\\u274c {e}", ephemeral=True)
    except Exception:
        log.exception("Unexpected command failure")
        message = "Something went wrong while calculating that result. Check your inputs and try again."
        try:
            if inter.response.is_done():
                await inter.followup.send(message, ephemeral=True)
            else:
                await inter.response.send_message(message, ephemeral=True)
        except Exception:
            log.exception("Unable to send command error response")


@tree.command(name="payout", description="Profit, total return and break-even probability for a bet")
@app_commands.describe(stake="Amount risked in dollars", odds="-110, +150, or 1.91")
async def payout(inter: discord.Interaction, stake: float, odds: str):
    def build():
        positive(stake, "Stake")
        d = parse_odds(odds)
        profit = stake * (d - 1)
        return odds_embed_ok("Payout", GREEN, [
            ("Profit", money(profit), True),
            ("Total return", money(stake * d), True),
            ("Break-even probability", pct(1 / d), True),
            ("Odds", f"{to_american(d)} / {d:.3f}", True),
        ])
    await respond(inter, build)


@tree.command(name="parlay", description="Combined odds and payout for a parlay")
@app_commands.describe(stake="Amount risked in dollars", legs="Odds for each leg, separated by commas or spaces: -110 +150 1.91")
async def parlay(inter: discord.Interaction, stake: float, legs: str):
    def build():
        positive(stake, "Stake")
        parts = [p for p in re.split(r"[,\s;]+", legs.strip()) if p]
        if len(parts) < 2:
            raise ValueError("A parlay needs at least 2 legs.")
        if len(parts) > 20:
            raise ValueError("Max 20 legs.")
        ds = [parse_odds(p) for p in parts]
        D = 1
        for d in ds:
            D *= d
        lines = "\n".join(f"{i}. {to_american(d)} ({d:.3f})" for i, d in enumerate(ds, 1))
        return odds_embed_ok(f"{len(ds)}-leg parlay", GREEN, [
            ("Profit", money(stake * (D - 1)), True),
            ("Total return", money(stake * D), True),
            ("Combined odds", f"{to_american(D)} / {D:.3f}", True),
            ("Implied probability", pct(1 / D), True),
            ("Legs", lines, False),
        ], footer="Assumes independent legs. Correlated same-game legs are priced differently by books.")
    await respond(inter, build)


@tree.command(name="novig", description="Remove the vig from a two-way market")
@app_commands.describe(odds_a="Side A odds", odds_b="Side B odds")
async def novig(inter: discord.Interaction, odds_a: str, odds_b: str):
    def build():
        pa, pb = 1 / parse_odds(odds_a), 1 / parse_odds(odds_b)
        t = pa + pb
        fa, fb = pa / t, pb / t
        return odds_embed_ok("No-vig", BLUE, [
            ("Vig", pct(t - 1), True),
            ("Book margin", pct(t), True),
            ("\u200b", "\u200b", True),
            ("Side A fair", f"{pct(fa)}\n{to_american(1 / fa)} / {1 / fa:.3f}", True),
            ("Side B fair", f"{pct(fb)}\n{to_american(1 / fb)} / {1 / fb:.3f}", True),
        ], footer="Proportional method: each implied probability divided by their sum.")
    await respond(inter, build)


@tree.command(name="ev", description="Expected value, edge and Kelly stake")
@app_commands.describe(odds="Odds you can get", win_prob="Your win probability in percent, e.g. 45",
                       bankroll="Optional bankroll in dollars for a stake size",
                       kelly_fraction="Fraction of full Kelly (default 0.25)")
async def ev(inter: discord.Interaction, odds: str, win_prob: float, bankroll: float | None = None, kelly_fraction: float = 0.25):
    def build():
        d = parse_odds(odds)
        if not 0 < win_prob < 100:
            raise ValueError("Win probability must be between 0 and 100.")
        if not math.isfinite(win_prob) or not 0 < win_prob < 100:
            raise ValueError("Win probability must be a finite percentage between 0 and 100.")
        if not math.isfinite(kelly_fraction) or not 0 < kelly_fraction <= 1:
            raise ValueError("Kelly fraction must be greater than 0 and no more than 1. Use 0.25 for quarter Kelly.")
        p, b = win_prob / 100, d - 1
        e = p * b - (1 - p)
        k = max(0.0, (b * p - (1 - p)) / b)
        fields = [
            ("EV per $100", money(e * 100), True),
            ("EV %", f"{e * 100:+.2f}%", True),
            ("Edge vs. implied", f"{(p - 1 / d) * 100:+.2f} pts", True),
            ("Full Kelly", pct(k), True),
            (f"{kelly_fraction:g}x Kelly", pct(k * kelly_fraction), True),
        ]
        if bankroll is not None:
            positive(bankroll, "Bankroll")
            stake = bankroll * k * kelly_fraction
            fields.append(("Suggested stake", money(stake), True))
            if stake > 0:
                fields.append(("Profit if it wins", money(stake * b), True))
        foot = "No positive edge at this price, so Kelly says stake nothing." if e <= 0 else \
            "Kelly is very sensitive to your probability. Fractional Kelly limits the damage from an overestimated edge."
        return odds_embed_ok("EV & Kelly", GREEN if e > 0 else RED, fields, footer=foot)
    await respond(inter, build)


@tree.command(name="hedge", description="Hedge stake that locks in equal profit either way")
@app_commands.describe(stake="Original stake in dollars", odds="Original bet odds",
                       hedge_odds="Current odds on the opposite side")
async def hedge(inter: discord.Interaction, stake: float, odds: str, hedge_odds: str):
    def build():
        positive(stake, "Stake")
        d1, d2 = parse_odds(odds), parse_odds(hedge_odds)
        payout_ = stake * d1
        h = payout_ / d2
        lock = payout_ - stake - h
        return odds_embed_ok("Hedge", GREEN if lock >= 0 else RED, [
            ("Hedge stake", money(h), True),
            ("Profit either way", money(lock), True),
            ("Total risked", money(stake + h), True),
            ("Original bet alone", money(payout_ - stake), True),
        ], footer="This hedge locks in a loss. Prices moved against you." if lock < 0 else None)
    await respond(inter, build)


@tree.command(name="build1line", description="Build a fair -1 run/puck line from the moneyline and -1.5 price")
@app_commands.describe(ml="Team moneyline", rl15="Same team's -1.5 price",
                       opp_ml="Optional: opposing moneyline (de-vigs the ML)",
                       opp_rl15="Optional: opposing +1.5 price (de-vigs the -1.5)")
async def build1line(inter: discord.Interaction, ml: str, rl15: str, opp_ml: str | None = None, opp_rl15: str | None = None):
    def build():
        r = build_minus1(ml, rl15, opp_ml, opp_rl15)
        fd = r["fair_dec"]
        return odds_embed_ok("Build -1 line", BLUE, [
            ("Win by 2+ (wins)", pct(r["w"]), True),
            ("Win by exactly 1 (push)", pct(r["push"]), True),
            ("Lose outright", pct(r["l"]), True),
            ("Fair -1 price", f"{to_american(fd)} / {fd:.3f}", True),
            ("Break-even (excl. pushes)", pct(r["breakeven"]), True),
            ("Win probability (ML)", pct(r["p_ml"]), True),
        ], footer="De-vigged" if (opp_ml or opp_rl15) else "Raw implied probabilities include vig. Add opp_ml / opp_rl15 to de-vig.")
    await respond(inter, build)


@tree.command(name="minus1", description="Check a -1 run/puck line price against a fair line built from the ML and -1.5")
@app_commands.describe(ml="Team moneyline", rl15="Same team's -1.5 price", alt1="The -1 line price you're being offered",
                       opp_ml="Optional: opposing moneyline", opp_rl15="Optional: opposing +1.5 price")
async def minus1(inter: discord.Interaction, ml: str, rl15: str, alt1: str, opp_ml: str | None = None, opp_rl15: str | None = None):
    def build():
        r = build_minus1(ml, rl15, opp_ml, opp_rl15)
        d = parse_odds(alt1)
        e = r["w"] * (d - 1) - r["l"]  # per $1; a push returns the stake
        fd = r["fair_dec"]
        return odds_embed_ok("-1 line check", GREEN if e > 0 else RED, [
            ("Offered", f"{to_american(d)} / {d:.3f}", True),
            ("Fair", f"{to_american(fd)} / {fd:.3f}", True),
            ("EV per $100", money(e * 100), True),
            ("Win / Push / Lose", f"{pct(r['w'], 1)} / {pct(r['push'], 1)} / {pct(r['l'], 1)}", False),
        ], footer="Positive EV vs. the fair line." if e > 0 else "The offered price is worse than fair.")
    await respond(inter, build)


@tree.command(name="convert", description="Convert odds between American, decimal and implied probability")
@app_commands.describe(odds="-110, +150, or 1.91")
async def convert(inter: discord.Interaction, odds: str):
    def build():
        d = parse_odds(odds)
        return odds_embed_ok("Odds converter", BLUE, [
            ("American", to_american(d), True),
            ("Decimal", f"{d:.3f}", True),
            ("Implied", pct(1 / d), True),
        ])
    await respond(inter, build)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("Set DISCORD_TOKEN (see .env.example).")
    bot.run(token)
