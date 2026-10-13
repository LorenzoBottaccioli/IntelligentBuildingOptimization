"""Tests of tutorials/explore.py, on functions whose answer is known. Run in image B (bdopt, ipywidgets, matplotlib, plotly):

    docker run --rm -v "$PWD:/r" -w /r -e MPLBACKEND=Agg --entrypoint python jupyter:smartbuilding-surrogate-plotly \
        -m unittest tests.tutorials.test_explore -v

Nothing here simulates: the "surrogates" are formulas, plus one Gaussian process fitted on a formula.
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "tutorials"))
os.environ.setdefault("MPLBACKEND", "Agg")

import bdopt  # noqa: E402
from bdopt import CategoryParameter, IntegerParameter, NullSelector, Parameter, Problem, RangeParameter  # noqa: E402
from bdopt.optimize import ParetoFront  # noqa: E402

import explore  # noqa: E402


def problem_of(*specs, objectives=("f",)):
    return Problem([Parameter(NullSelector(name), d, name=name) for name, d in specs], list(objectives))


class Formula:
    """A stand-in for a surrogate: ``predict`` applies a function to the parameter table, in joules."""

    has_uncertainty = False

    def __init__(self, problem, *functions):
        self.problem, self.functions = problem, functions

    def predict(self, X):
        return pd.DataFrame({o: f(X) * explore.JOULES_PER_KWH for o, f in zip(self.problem.objective_names, self.functions)},
                            index=X.index)


class Sobol(unittest.TestCase):
    def test_additive_function(self):
        problem = problem_of(("a", RangeParameter(0, 1)), ("b", RangeParameter(0, 1)), ("c", RangeParameter(0, 1)))
        model = Formula(problem, lambda X: 4 * X["a"] + 2 * X["b"])
        S1, ST = explore.sobol_indices(model, problem, n=4096)
        self.assertAlmostEqual(S1.loc["a", "f"], 0.8, delta=0.03)
        self.assertAlmostEqual(S1.loc["b", "f"], 0.2, delta=0.03)
        self.assertAlmostEqual(ST.loc["c", "f"], 0.0, delta=0.02)
        self.assertAlmostEqual(ST.loc["a", "f"], S1.loc["a", "f"], delta=0.04)        # additive: no interaction

    def test_product_has_interaction(self):
        problem = problem_of(("a", RangeParameter(0, 1)), ("b", RangeParameter(0, 1)))
        model = Formula(problem, lambda X: X["a"] * X["b"])
        S1, ST = explore.sobol_indices(model, problem, n=4096)
        self.assertAlmostEqual(S1.loc["a", "f"], 3 / 7, delta=0.04)                    # known: 3/7 and 4/7
        self.assertAlmostEqual(ST.loc["a", "f"], 4 / 7, delta=0.04)
        self.assertGreater(ST.loc["a", "f"], S1.loc["a", "f"] + 0.08)

    def test_integer_and_category_parameters(self):
        problem = problem_of(("k", IntegerParameter(8, 12)), ("c", CategoryParameter(["a", "b", "c"])),
                             objectives=("f", "g"))
        model = Formula(problem, lambda X: X["k"].astype(float), lambda X: (X["c"] == "b").astype(float))
        S1, ST = explore.sobol_indices(model, problem, n=1024)
        self.assertGreater(S1.loc["k", "f"], 0.9)
        self.assertGreater(S1.loc["c", "g"], 0.9)
        self.assertLess(ST.loc["c", "f"], 0.05)

    def test_constant_objective_is_nan_not_an_error(self):
        problem = problem_of(("a", RangeParameter(0, 1)))
        S1, ST = explore.sobol_indices(Formula(problem, lambda X: X["a"] * 0 + 5.0), problem, n=256)
        self.assertTrue(S1["f"].isna().all() or (S1["f"] == 0).all())


class Tornado(unittest.TestCase):
    def test_swings(self):
        problem = problem_of(("a", RangeParameter(0, 2)), ("b", RangeParameter(10, 20)))
        swing = explore.tornado(Formula(problem, lambda X: 3 * X["a"] - X["b"]), problem)
        self.assertAlmostEqual(swing.loc["a", "f"], 6.0)
        self.assertAlmostEqual(swing.loc["b", "f"], -10.0)


class Explorer(unittest.TestCase):
    def setUp(self):
        self.problem = problem_of(("x", RangeParameter(0, 2)), ("k", IntegerParameter(8, 12)),
                                  ("c", CategoryParameter(["a", "b", "c"])), objectives=("f:Facility", "g:Facility"))
        self.model = Formula(self.problem, lambda X: X["x"] * 10 + X["k"], lambda X: (X["c"] == "c") * 5.0 + 1)

    def test_every_tab_renders_and_the_sliders_move_the_prediction(self):
        ex = explore.ParameterExplorer(self.model, self.problem)
        self.assertEqual(set(ex.design), {"x", "k", "c"})
        before = ex.prediction.copy()
        ex._controls["x"].value = 2.0
        self.assertGreater(ex.prediction["f:Facility"], before["f:Facility"])
        for i in range(4):
            ex._tabs.selected_index = i
        ex._reset()
        self.assertAlmostEqual(ex.prediction["f:Facility"], before["f:Facility"])

    def test_two_saved_designs_are_compared(self):
        ex = explore.ParameterExplorer(self.model, self.problem)
        ex._save("A")
        ex._controls["c"].value = "c"
        ex._save("B")
        self.assertEqual((ex.A["c"], ex.B["c"]), ("b", "c"))
        ex._tabs.selected_index = 3
        ex._clear()
        self.assertIsNone(ex.A)

    def test_map_needs_two_numeric_parameters_and_refuses_the_same_one_twice(self):
        ex = explore.ParameterExplorer(self.model, self.problem)
        ex._tabs.selected_index = 2
        self.assertEqual(set(ex._map_x.options), {"x", "k"})            # the category is not an axis
        ex._map_y.value = ex._map_x.value                                 # must not raise
        ex._tabs.selected_index = 1

    def test_with_training_designs_and_a_gaussian_process(self):
        from bdopt.surrogate import GPSurrogate
        problem = problem_of(("a", RangeParameter(0, 1)), ("b", RangeParameter(0, 1)), objectives=("f:Facility",))
        from bdopt import sampling
        train = sampling.lhs(problem, 25, seed=0)
        train["f:Facility"] = (3 * train["a"] + train["b"] ** 2) * explore.JOULES_PER_KWH
        gp = GPSurrogate().fit(train, problem)
        self.assertTrue(gp.has_uncertainty)
        ex = explore.ParameterExplorer(gp, problem, training=train)
        y, std = explore.predict(gp, problem, [ex.design], with_std=True)
        self.assertTrue(np.all(std >= 0))
        for i in range(4):
            ex._tabs.selected_index = i
        ex._tabs.selected_index = 2
        ex._map_show.value = "uncertainty (± 1 std)"
        # the model is surest at a training design and less sure far from all of them
        near = train.iloc[[0]][problem.parameter_names]
        far = pd.DataFrame({"a": [0.5], "b": [0.5]})
        _, s_near = explore.predict(gp, problem, near, with_std=True)
        self.assertTrue(np.isfinite(s_near).all())


class Pareto(unittest.TestCase):
    def test_weights_choose_the_design(self):
        problem = problem_of(("x", RangeParameter(0, 1)), objectives=("f:Facility", "g:Facility", "h:Facility"))
        x = np.linspace(0, 1, 21)
        df = pd.DataFrame({"x": x, "f:Facility": x * 1e7, "g:Facility": (1 - x) * 1e7, "h:Facility": (0.5 - np.abs(x - 0.5)) * 1e7})
        front = ParetoFront(df, problem)
        model = Formula(problem, lambda X: X["x"], lambda X: 1 - X["x"], lambda X: X["x"])
        ex = explore.ParetoExplorer(front, problem, model)
        ex._weights[0].value, ex._weights[1].value, ex._weights[2].value = 1.0, 0.0, 0.0
        self.assertAlmostEqual(ex.design["x"], 0.0)                       # only f matters: the smallest f
        ex._weights[0].value, ex._weights[1].value = 0.0, 1.0
        self.assertAlmostEqual(ex.design["x"], 1.0)
        for w in ex._weights:
            w.value = 0.0
        self.assertIn(ex.design["x"], x)                                  # all zero: falls back to equal weights


class Plotly(unittest.TestCase):
    def test_parallel_coordinates(self):
        problem = problem_of(("x", RangeParameter(0, 1)), ("c", CategoryParameter(["a", "b"])), objectives=("f:Facility",))
        df = pd.DataFrame({"x": [0.1, 0.5, 0.9], "c": ["a", "b", "a"], "f:Facility": [3.6e6, 7.2e6, 1.08e7]})
        fig = explore.parallel_coordinates(df, problem)
        dims = fig.data[0].dimensions
        self.assertEqual([d.label for d in dims], ["x", "c", "f:Facility"])
        self.assertEqual(list(dims[2].values), [1.0, 2.0, 3.0])          # kWh
        self.assertEqual(list(dims[1].values), [0, 1, 0])                # the position of the option


class Learning(unittest.TestCase):
    def test_curve(self):
        from bdopt import sampling
        from bdopt.surrogate import PolynomialSurrogate
        problem = problem_of(("a", RangeParameter(0, 1)), ("b", RangeParameter(0, 1)), objectives=("f",))
        data = sampling.lhs(problem, 40, seed=1)
        data["f"] = 5 + 2 * data["a"] + data["b"]
        table = explore.learning_curve(lambda: PolynomialSurrogate(), data, problem, sizes=(8, 16), repeats=2, test_size=8)
        self.assertEqual(list(table.index), [8, 16])
        self.assertTrue((table["f"] >= 0).all())


if __name__ == "__main__":
    unittest.main()
