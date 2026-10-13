"""Tools to look into a surrogate model: sliders, sections, maps, sensitivity, Pareto choices, parallel coordinates.

Everything here works on a *bdopt surrogate* (``bdopt.surrogate.Surrogate``: ``predict`` and, for some models,
``predict_unit_std``) and the bdopt ``Problem`` it was trained for. It is plain Python: open this file to see how each
picture is made. Objectives are energy meters in joules; they are shown in kWh (``scale=3.6e6``).

    ParameterExplorer(surrogate, problem, training=...)   sliders for every parameter, with four views (tabs)
    sobol_indices(surrogate, problem)                      which parameters matter, with interactions
    tornado(surrogate, problem)                            what each parameter alone can do, from the centre
    parallel_coordinates(designs, problem)                 brushable plot of many designs (plotly)
    ParetoExplorer(front, problem, surrogate)              choose a design of the Pareto front with weights
    learning_curve(make_surrogate, data, problem)          does the surrogate need more simulations?
"""
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import ipywidgets as widgets
from IPython.display import clear_output, display

JOULES_PER_KWH = 3.6e6
BLUE, ORANGE, GREEN, GREY = "#2f6db5", "#d9822b", "#3a9b5c", "#9aa3ad"


# ------------------------------------------------------------------------------------------------ small helpers

def _kind(parameter):
    return parameter.value_descriptor.kind          # "continuous", "integer" or "categorical"


def _numeric(problem):
    """Names of the parameters that can be on an axis (not the categorical ones)."""
    return [p.name for p in problem.parameters if _kind(p) != "categorical"]


def _bounds(parameter):
    d = parameter.value_descriptor
    return float(d.min), float(d.max)


def _centre(problem):
    """The design in the middle of every range (the first option of a categorical parameter's middle bin)."""
    return problem.decode(np.full((1, problem.n_var), 0.5)).iloc[0].to_dict()


def _table(problem, designs):
    """A list of design dictionaries, or a DataFrame, as a parameter table in the order of the problem."""
    if isinstance(designs, pd.DataFrame):
        return designs[problem.parameter_names].reset_index(drop=True)
    return pd.DataFrame(designs)[problem.parameter_names]


def _has_std(surrogate):
    return bool(getattr(surrogate, "has_uncertainty", False))


def predict(surrogate, problem, designs, scale=JOULES_PER_KWH, with_std=False):
    """Predicted objectives of ``designs`` (a table or a list of dictionaries) in kWh; optionally the std as well."""
    table = _table(problem, designs)
    y = surrogate.predict(table).to_numpy(float) / scale
    if not with_std:
        return y
    std = surrogate.predict_unit_std(problem.encode(table)) if _has_std(surrogate) else None
    return y, (None if std is None else np.asarray(std, float) / scale)


def _grid(problem, name, design, points=60):
    """``points`` designs that differ from ``design`` only in parameter ``name``, and the values of that parameter."""
    parameter = next(p for p in problem.parameters if p.name == name)
    if _kind(parameter) == "categorical":
        values = list(parameter.value_descriptor.options)
    else:
        lo, hi = _bounds(parameter)
        values = np.linspace(lo, hi, points if _kind(parameter) == "continuous" else int(hi - lo) + 1)
    table = pd.DataFrame([dict(design, **{name: v}) for v in values])[problem.parameter_names]
    return values, table


# ---------------------------------------------------------------------------------------- the explorer with tabs

class ParameterExplorer:
    """One slider (or menu) per parameter, and what the surrogate says about the design you build.

    Four tabs, all driven by the same sliders:
      Prediction  the objectives in kWh (with ± 2 standard deviations if the model can say how sure it is), the
                  range of the training data in grey, and the designs saved as A and B
      Sections    each objective against each parameter, the others kept where the sliders are
      Map         one objective (or its uncertainty) against two parameters, with the training designs on top
      Compare     the designs A and B side by side

    ``design`` is the dictionary of the current slider values: ``EnergyPlusEvaluator.evaluate`` takes it as well.
    """

    def __init__(self, surrogate, problem, training=None, start=None, scale=JOULES_PER_KWH, unit="kWh"):
        self.surrogate, self.problem, self.scale, self.unit = surrogate, problem, scale, unit
        self.training = None if training is None else training[problem.parameter_names + problem.objective_names]
        self.start = dict(_centre(problem) if start is None else start)
        self.A = self.B = None
        self._controls = {}
        for p in problem.parameters:
            d, name = p.value_descriptor, p.name
            style = {"description_width": "210px"}
            if _kind(p) == "categorical":
                c = widgets.Dropdown(options=list(d.options), value=self.start[name], description=name, style=style)
            elif _kind(p) == "integer":
                c = widgets.IntSlider(min=int(d.min), max=int(d.max), value=int(self.start[name]), description=name,
                                      style=style, continuous_update=False, layout=widgets.Layout(width="520px"))
            else:
                lo, hi = _bounds(p)
                c = widgets.FloatSlider(min=lo, max=hi, step=(hi - lo) / 200, value=float(self.start[name]),
                                        description=name, readout_format=".3g", style=style, continuous_update=False,
                                        layout=widgets.Layout(width="520px"))
            c.observe(self._changed, names="value")
            self._controls[name] = c
        button = lambda text, tip, fn: self._button(text, tip, fn)
        self._buttons = widgets.HBox([
            button("Reset", "back to the starting design", self._reset),
            button("Save as A", "keep this design as A", lambda _: self._save("A")),
            button("Save as B", "keep this design as B", lambda _: self._save("B")),
            button("Clear A and B", "forget the saved designs", self._clear)])
        self._outputs = {k: widgets.Output() for k in ("Prediction", "Sections", "Map", "Compare")}
        self._tabs = widgets.Tab(children=list(self._outputs.values()))
        for i, k in enumerate(self._outputs):
            self._tabs.set_title(i, k)
        self._tabs.observe(lambda _: self._render(), names="selected_index")
        self._build_map_controls()
        self.widget = widgets.VBox([*self._controls.values(), self._buttons, self._tabs])
        self._render()

    # -- controls
    @staticmethod
    def _button(text, tooltip, callback):
        b = widgets.Button(description=text, tooltip=tooltip, layout=widgets.Layout(width="auto"))
        b.on_click(callback)
        return b

    def _default_map(self):
        """The objective that most parameters move, and the two parameters that move it most (from the starting design)."""
        names = _numeric(self.problem)
        swing = pd.DataFrame(0.0, index=names, columns=self.problem.objective_names)
        for name in names:
            _, table = _grid(self.problem, name, self.start, points=2)
            y = predict(self.surrogate, self.problem, table, self.scale)
            swing.loc[name] = np.abs(y[-1] - y[0])
        relative = (swing / swing.max().replace(0, np.nan)).fillna(0)
        objective = relative.sum().idxmax()
        top = list(relative[objective].sort_values(ascending=False).index)
        return top[0], top[1] if len(top) > 1 else top[0], objective

    def _build_map_controls(self):
        names = _numeric(self.problem)
        x0, y0, objective0 = self._default_map()
        self._map_x = widgets.Dropdown(options=names, value=x0, description="x axis")
        self._map_y = widgets.Dropdown(options=names, value=y0, description="y axis")
        self._map_obj = widgets.Dropdown(options=self.problem.objective_names, value=objective0, description="objective")
        shows = ["prediction"] + (["uncertainty (± 1 std)"] if _has_std(self.surrogate) else [])
        self._map_show = widgets.ToggleButtons(options=shows, description="show")
        for c in (self._map_x, self._map_y, self._map_obj, self._map_show):
            c.observe(lambda _: self._render(), names="value")
        self._map_box = widgets.VBox([widgets.HBox([self._map_x, self._map_y]),
                                      widgets.HBox([self._map_obj, self._map_show])])

    @property
    def design(self):
        return {name: c.value for name, c in self._controls.items()}

    @property
    def prediction(self):
        """The current design's objectives in kWh, as a Series."""
        return pd.Series(predict(self.surrogate, self.problem, [self.design], self.scale)[0], index=self.problem.objective_names)

    def _changed(self, _):
        self._render()

    def _reset(self, _=None):
        for name, c in self._controls.items():
            c.unobserve(self._changed, names="value")
            c.value = self.start[name]
            c.observe(self._changed, names="value")
        self._render()

    def _save(self, which):
        setattr(self, which, self.design)
        self._render()

    def _clear(self, _=None):
        self.A = self.B = None
        self._render()

    # -- drawing
    def _render(self):
        name = list(self._outputs)[self._tabs.selected_index]
        out = self._outputs[name]
        with out:
            clear_output(wait=True)
            getattr(self, "_draw_" + name.lower())()

    def _draw_prediction(self):
        names = self.problem.objective_names
        shown = [("current", self.design, BLUE)] + [(k, v, c) for k, v, c in (("A", self.A, ORANGE), ("B", self.B, GREEN)) if v]
        fig, ax = plt.subplots(figsize=(7.2, 3.6))
        width = 0.8 / len(shown)
        for j, (label, design, colour) in enumerate(shown):
            y, std = predict(self.surrogate, self.problem, [design], self.scale, with_std=True)
            x = np.arange(len(names)) + (j - (len(shown) - 1) / 2) * width
            ax.bar(x, y[0], width * 0.9, color=colour, label=label,
                   yerr=None if std is None else 2 * std[0], capsize=3, ecolor="black")
            for xi, yi in zip(x, y[0]):
                ax.text(xi, yi, f"{yi:,.0f}", ha="center", va="bottom", fontsize=8)
        if self.training is not None:       # the range the model has seen, behind the bars
            for i, n in enumerate(names):
                lo, hi = self.training[n].min() / self.scale, self.training[n].max() / self.scale
                ax.plot([i, i], [lo, hi], color=GREY, lw=7, alpha=0.35, solid_capstyle="butt", zorder=0,
                        label="range of the simulated designs" if i == 0 else None)
        ax.set_xticks(range(len(names)), [n.replace(":Facility", "") for n in names])
        ax.set_ylabel(self.unit)
        ax.legend(fontsize=8, loc="upper right")
        note = "bars: surrogate prediction" + (", error bars: ± 2 std (the model's own uncertainty)" if _has_std(self.surrogate)
                                                  else "; this model does not give an uncertainty")
        ax.set_title(note, fontsize=9)
        plt.show()
        plt.close(fig)
        total = self.prediction.sum()
        print(f"Sum of the objectives for the current design: {total:,.0f} {self.unit}")

    def _draw_sections(self):
        problem, design = self.problem, self.design
        names, nobj = problem.parameter_names, problem.n_obj
        fig, axes = plt.subplots(nobj, len(names), figsize=(2.8 * len(names), 2.2 * nobj), squeeze=False, sharey="row")
        for j, name in enumerate(names):
            values, table = _grid(problem, name, design)
            y, std = predict(self.surrogate, problem, table, self.scale, with_std=True)
            for i in range(nobj):
                ax = axes[i][j]
                if _kind(next(p for p in problem.parameters if p.name == name)) == "categorical":
                    ax.plot(range(len(values)), y[:, i], "o-", color=BLUE)
                    ax.set_xticks(range(len(values)), values, fontsize=7)
                    ax.axvline(values.index(design[name]), color="black", ls=":")
                else:
                    ax.plot(values, y[:, i], color=BLUE)
                    if std is not None:
                        ax.fill_between(values, y[:, i] - 2 * std[:, i], y[:, i] + 2 * std[:, i], color=BLUE, alpha=0.2, lw=0)
                    ax.axvline(design[name], color="black", ls=":")
                if i == nobj - 1:
                    ax.set_xlabel(name, fontsize=8)
                if j == 0:
                    ax.set_ylabel(problem.objective_names[i].replace(":Facility", "") + f"\n[{self.unit}]", fontsize=8)
                ax.tick_params(labelsize=7)
        fig.suptitle("each curve: one parameter moves, the others stay where the sliders are (dotted line: current value)",
                     fontsize=9)
        fig.tight_layout()
        plt.show()
        plt.close(fig)

    def _draw_map(self):
        display(self._map_box)
        x, y, objective = self._map_x.value, self._map_y.value, self._map_obj.value
        if x == y:
            print("Choose two different parameters for the axes.")
            return
        px_, py_ = (next(p for p in self.problem.parameters if p.name == n) for n in (x, y))
        gx = np.linspace(*_bounds(px_), 45)
        gy = np.linspace(*_bounds(py_), 45)
        XX, YY = np.meshgrid(gx, gy)
        table = pd.DataFrame([dict(self.design, **{x: a, y: b}) for a, b in zip(XX.ravel(), YY.ravel())])[self.problem.parameter_names]
        values, std = predict(self.surrogate, self.problem, table, self.scale, with_std=True)
        k = self.problem.objective_names.index(objective)
        uncertainty = self._map_show.value.startswith("uncertainty") and std is not None
        Z = (std[:, k] if uncertainty else values[:, k]).reshape(XX.shape)
        fig, ax = plt.subplots(figsize=(6.4, 4.4))
        cs = ax.contourf(XX, YY, Z, levels=14, cmap="magma" if uncertainty else "viridis")
        bar = fig.colorbar(cs, label=("± 1 std of " if uncertainty else "") + f"{objective} [{self.unit}]")
        bar.formatter.set_useOffset(False)           # plain numbers, no "+1.67e4" above the plot
        bar.update_ticks()
        if self.training is not None:
            ax.scatter(self.training[x], self.training[y], c="white", edgecolor="black", s=22, label="simulated designs")
        ax.plot(self.design[x], self.design[y], "rx", ms=11, mew=2, label="current design")
        ax.set_xlabel(x)
        ax.set_ylabel(y)
        ax.legend(fontsize=8, loc="upper right")
        ax.set_title("the other parameters stay where the sliders are" + ("\n(where the model is unsure, simulate more designs)"
                                                                         if uncertainty else ""), fontsize=9)
        plt.show()
        plt.close(fig)

    def _draw_compare(self):
        if not (self.A and self.B):
            print("Press 'Save as A' for one design, move the sliders, then 'Save as B'. The two are compared here.")
            return
        ya, yb = (predict(self.surrogate, self.problem, [d], self.scale)[0] for d in (self.A, self.B))
        objectives = pd.DataFrame({"A": ya, "B": yb, f"B - A [{self.unit}]": yb - ya,
                                   "B vs A [%]": 100 * (yb - ya) / ya}, index=self.problem.objective_names)
        objectives.loc["total"] = [ya.sum(), yb.sum(), (yb - ya).sum(), 100 * (yb - ya).sum() / ya.sum()]
        objectives = objectives.round(1) + 0.0          # + 0.0 turns -0.0 into 0.0
        parameters = pd.DataFrame({"A": self.A, "B": self.B})
        display(parameters.style.format(precision=3).set_caption("the two designs"))
        display(objectives.style.format(precision=1).set_caption("what the surrogate predicts for them"))


# ---------------------------------------------------------------------------------------- sensitivity

def sobol_indices(surrogate, problem, n=2048, seed=0):
    """First-order and total Sobol' indices of every parameter, for every objective, computed on the surrogate.

    The first-order index S1 is the share of the variance of an objective that the parameter explains alone; the total
    index ST adds what it explains together with the others. ST much larger than S1: the parameter acts through an
    interaction. Estimators: Saltelli (2010) for S1, Jansen for ST, with ``n * (parameters + 2)`` surrogate evaluations
    (about 14 000 here: instant for a surrogate, impossible with EnergyPlus).
    Returns two DataFrames, parameters x objectives.
    """
    import warnings
    from scipy.stats import qmc
    names, objectives, d = problem.parameter_names, problem.objective_names, problem.n_var
    # A and B must be independent: they are the two halves of ONE Sobol' sequence of 2 * d dimensions. (Two separate
    # scrambled sequences of d dimensions were measured to be 94 % correlated and gave S1 = 0.05 instead of 0.8.)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")                     # "n is not a power of 2"
        try:
            sequence = qmc.Sobol(d=2 * d, scramble=True, rng=seed)
        except TypeError:                                   # older scipy
            sequence = qmc.Sobol(d=2 * d, scramble=True, seed=seed)
        U = sequence.random(n)
    UA, UB = U[:, :d], U[:, d:]
    fA = surrogate.predict(problem.decode(UA)).to_numpy(float)
    fB = surrogate.predict(problem.decode(UB)).to_numpy(float)
    variance = np.concatenate([fA, fB]).var(axis=0)
    S1, ST = {}, {}
    for i, name in enumerate(names):
        UAB = UA.copy()
        UAB[:, i] = UB[:, i]                                # A with the column of this parameter taken from B
        fAB = surrogate.predict(problem.decode(UAB)).to_numpy(float)
        with np.errstate(divide="ignore", invalid="ignore"):
            S1[name] = (fB * (fAB - fA)).mean(axis=0) / variance
            ST[name] = 0.5 * ((fA - fAB) ** 2).mean(axis=0) / variance
    return (pd.DataFrame(S1, index=objectives).T.clip(lower=0, upper=1),
            pd.DataFrame(ST, index=objectives).T.clip(lower=0, upper=1))


def tornado(surrogate, problem, design=None, scale=JOULES_PER_KWH, unit="kWh"):
    """For every parameter, how far each objective moves when only that parameter goes from its minimum to its maximum.

    The other parameters stay at ``design`` (default: the middle of every range). Returns a DataFrame of the swings
    (parameters x objectives) and draws one bar chart per objective, the parameters in the same order in all of them (the most influential on top).
    """
    design = dict(_centre(problem) if design is None else design)
    swing = {}
    for name in problem.parameter_names:
        _, table = _grid(problem, name, design, points=2)
        y = predict(surrogate, problem, table, scale)
        swing[name] = y[-1] - y[0]
    swing = pd.DataFrame(swing, index=problem.objective_names).T
    fig, axes = plt.subplots(1, problem.n_obj, figsize=(4.2 * problem.n_obj, 3.2), sharey=True)
    # one order for all the panels: the parameter with the largest effect (as a share of the largest swing of each objective) on top
    relative = swing.abs() / swing.abs().max().replace(0, 1)
    order = relative.sum(axis=1).sort_values().index
    for ax, objective in zip(np.atleast_1d(axes), problem.objective_names):
        s = swing[objective].reindex(order)
        ax.barh(s.index, s.values, color=[ORANGE if v > 0 else BLUE for v in s.values])
        ax.axvline(0, color="black", lw=0.8)
        ax.set_title(objective.replace(":Facility", ""), fontsize=10)
        ax.set_xlabel(f"change from min to max of the parameter [{unit}]", fontsize=8)
    fig.suptitle("what each parameter does alone, the others at the middle of their range (orange: it raises the objective)", fontsize=9)
    fig.tight_layout()
    plt.show()
    plt.close(fig)
    return swing.round(1)


def sensitivity_plot(S1, ST):
    """Bars of the first-order and total Sobol' indices (the output of ``sobol_indices``), one panel per objective."""
    fig, axes = plt.subplots(1, S1.shape[1], figsize=(4.2 * S1.shape[1], 3.2), sharey=True)
    positions = np.arange(len(S1))
    for ax, objective in zip(np.atleast_1d(axes), S1.columns):
        ax.barh(positions - 0.2, S1[objective].values, 0.4, color=BLUE, label="alone (S1)")
        ax.barh(positions + 0.2, ST[objective].values, 0.4, color=ORANGE, label="with the interactions (ST)")
        ax.set_yticks(positions, S1.index)
        ax.set_xlim(0, 1)
        ax.set_title(objective.replace(":Facility", ""), fontsize=10)
        ax.set_xlabel("share of the variance explained", fontsize=8)
    np.atleast_1d(axes)[0].legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    plt.show()
    plt.close(fig)


# ---------------------------------------------------------------------------------------- parallel coordinates

def parallel_coordinates(designs, problem, color=None, scale=JOULES_PER_KWH):
    """The brushable plot of the original course notebooks (plotly): one line per design, one axis per variable.

    Drag on an axis to keep only the designs in that range (drag again to move or remove the range); drag the axis
    titles to reorder the axes. The objectives are shown in kWh.
    """
    import plotly.express as px
    df = designs[problem.parameter_names + problem.objective_names].copy()
    df[problem.objective_names] = df[problem.objective_names] / scale
    for p in problem.parameters:
        if _kind(p) == "categorical":         # plotly needs numbers: the position of the option in the list
            options = list(p.value_descriptor.options)
            df[p.name] = df[p.name].map(options.index)
    color = color or problem.objective_names[0]
    fig = px.parallel_coordinates(df, color=color, dimensions=list(df.columns),
                                  color_continuous_scale=px.colors.diverging.Tealrose)
    fig.update_traces(labelangle=-20)
    fig.update_layout(margin=dict(l=80, r=60, t=110, b=30), height=470)
    return fig


# ---------------------------------------------------------------------------------------- the Pareto front

class ParetoExplorer:
    """Choose a design of the Pareto front by saying how much each objective matters.

    A weight of 0 makes an objective irrelevant, a larger weight makes it count more: the design shown is
    ``front.closest_to_ideal(weights)``. Below the plot: the design, what the surrogate predicts for it and, if an
    ``evaluator`` is given, a button that simulates it with EnergyPlus and compares the two.
    """

    def __init__(self, front, problem, surrogate, evaluator=None, scale=JOULES_PER_KWH, unit="kWh", background=None):
        self.front, self.problem, self.surrogate, self.evaluator = front, problem, surrogate, evaluator
        self.scale, self.unit, self.background = scale, unit, background
        self.design = None
        self._weights = [widgets.FloatSlider(min=0, max=1, step=0.05, value=1.0, description=n.replace(":Facility", ""),
                                             style={"description_width": "150px"}, continuous_update=False,
                                             layout=widgets.Layout(width="520px")) for n in problem.objective_names]
        for w in self._weights:
            w.observe(lambda _: self._render(), names="value")
        self._simulate = widgets.Button(description="Simulate this design with EnergyPlus", button_style="info",
                                        layout=widgets.Layout(width="auto"))
        self._simulate.on_click(self._run_energyplus)
        self._plot, self._table, self._check = widgets.Output(), widgets.Output(), widgets.Output()
        controls = [widgets.HTML("<b>How much does each objective matter?</b>"), *self._weights]
        if evaluator is not None:
            controls += [self._simulate]
        self.widget = widgets.VBox([*controls, self._plot, self._table, self._check])
        self._render()

    @property
    def weights(self):
        return [w.value for w in self._weights]

    def _render(self):
        weights = self.weights
        if not any(weights):
            weights = [1.0] * len(weights)
        best = self.front.closest_to_ideal(weights=weights)
        self.design = {n: best[n] for n in self.problem.parameter_names}
        names = self.problem.objective_names
        pairs = [(0, 1), (0, 2), (1, 2)][: 1 if len(names) == 2 else 3]
        with self._plot:
            clear_output(wait=True)
            fig, axes = plt.subplots(1, len(pairs), figsize=(4.0 * len(pairs), 3.4), squeeze=False)
            for ax, (i, j) in zip(axes[0], pairs):
                if self.background is not None:
                    ax.plot(self.background[names[i]] / self.scale, self.background[names[j]] / self.scale, ".", color=GREY, ms=2, alpha=0.5)
                ax.plot(self.front.df[names[i]] / self.scale, self.front.df[names[j]] / self.scale, "o", color=BLUE, ms=4)
                ax.plot(best[names[i]] / self.scale, best[names[j]] / self.scale, "*", color="red", ms=15, mec="black")
                ax.set_xlabel(names[i].replace(":Facility", "") + f" [{self.unit}]", fontsize=8)
                ax.set_ylabel(names[j].replace(":Facility", "") + f" [{self.unit}]", fontsize=8)
                ax.tick_params(labelsize=7)
            fig.suptitle("the Pareto front (blue); the star is the design that the weights select", fontsize=9)
            fig.tight_layout()
            plt.show()
            plt.close(fig)
        with self._table:
            clear_output(wait=True)
            y, std = predict(self.surrogate, self.problem, [self.design], self.scale, with_std=True)
            display(pd.DataFrame([self.design]).style.format(precision=3).hide(axis="index").set_caption("the selected design"))
            prediction = pd.DataFrame({f"surrogate [{self.unit}]": y[0]}, index=names)
            if std is not None:
                prediction["± 2 std"] = 2 * std[0]
            display(prediction.round(1).T)

    def _run_energyplus(self, _):
        with self._check:
            clear_output(wait=True)
            print("Simulating one year with EnergyPlus (about half a minute)...")
            names = self.problem.objective_names
            simulated = self.evaluator.evaluate(pd.DataFrame([self.design]))[names].iloc[0] / self.scale
            predicted = pd.Series(predict(self.surrogate, self.problem, [self.design], self.scale)[0], index=names)
            clear_output(wait=True)
            display(pd.DataFrame({f"surrogate [{self.unit}]": predicted, f"EnergyPlus [{self.unit}]": simulated,
                                  "difference [%]": 100 * (predicted - simulated) / simulated}).round(1))


# ---------------------------------------------------------------------------------------- is the surrogate enough?

def learning_curve(make_surrogate, data, problem, sizes=(10, 20, 30, 40), repeats=3, test_size=10, seed=0, scale=JOULES_PER_KWH):
    """Error on designs that were left out, against the number of simulated designs used for training.

    ``make_surrogate`` is a function that returns a new untrained surrogate (``lambda: GPSurrogate()``). For each size,
    ``repeats`` random choices of training designs are fitted and tested on ``test_size`` other designs. The curve says
    whether more simulations would still help: if it is flat, they would not. Returns the table and draws it.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for size in sizes:
        for r in range(repeats):
            order = rng.permutation(len(data))
            test, train = data.iloc[order[:test_size]], data.iloc[order[test_size:test_size + size]]
            if len(train) < size:
                continue
            model = make_surrogate().fit(train, problem)
            rmse_pct = model.score(test)["rmse_pct"]
            rows.append({"training designs": size, **{o: v for o, v in zip(problem.objective_names, np.asarray(rmse_pct, float))}})
    table = pd.DataFrame(rows)
    mean, spread = table.groupby("training designs").mean(), table.groupby("training designs").std()
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    for o in problem.objective_names:
        ax.errorbar(mean.index, mean[o], yerr=spread[o].fillna(0), marker="o", capsize=3, label=o.replace(":Facility", ""))
    ax.set_xlabel("simulated designs used for training")
    ax.set_ylabel("error on unseen designs [% of the mean]")
    ax.set_title(f"mean and spread of {repeats} random choices of the training designs", fontsize=9)
    ax.legend(fontsize=8)
    plt.show()
    plt.close(fig)
    return mean.round(2)
