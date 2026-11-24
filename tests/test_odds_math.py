import math
import unittest

from bot import build_minus1, fair_prob, parse_odds, positive, to_american


class OddsParsingTests(unittest.TestCase):
    def test_american_and_decimal_odds(self):
        self.assertAlmostEqual(parse_odds("-110"), 1 + 100 / 110)
        self.assertAlmostEqual(parse_odds("+150"), 2.5)
        self.assertAlmostEqual(parse_odds("1.91"), 1.91)
        self.assertAlmostEqual(parse_odds("−110"), 1 + 100 / 110)

    def test_invalid_and_non_finite_odds_are_rejected(self):
        for value in ("nan", "inf", "-inf", "0", "1", "-99", "abc"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_odds(value)

    def test_decimal_to_american_format(self):
        self.assertEqual(to_american(2.5), "+150")
        self.assertEqual(to_american(1.9090909091), "-110")


class ProbabilityTests(unittest.TestCase):
    def test_no_vig_probability(self):
        self.assertAlmostEqual(fair_prob("-110", "-110"), 0.5)

    def test_one_sided_implied_probability(self):
        self.assertAlmostEqual(fair_prob("+150"), 0.4)

    def test_positive_requires_finite_value(self):
        for value in (0, -1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    positive(value, "Stake")


class MinusOneLineTests(unittest.TestCase):
    def test_win_push_loss_probabilities_and_fair_price(self):
        result = build_minus1("-150", "+120")
        self.assertAlmostEqual(result["w"], 1 / 2.2)
        self.assertAlmostEqual(result["push"], 0.6 - 1 / 2.2)
        self.assertAlmostEqual(result["l"], 0.4)
        self.assertAlmostEqual(result["w"] + result["push"] + result["l"], 1.0)
        self.assertAlmostEqual(result["fair_dec"], 1 + result["l"] / result["w"])

    def test_invalid_probability_relationship_is_rejected(self):
        with self.assertRaises(ValueError):
            build_minus1("+150", "+100")

    def test_opposing_prices_can_remove_vig(self):
        result = build_minus1("-150", "+120", "+130", "-140")
        self.assertGreater(result["w"], 0)
        self.assertGreater(result["push"], 0)
        self.assertGreater(result["l"], 0)


if __name__ == "__main__":
    unittest.main()
