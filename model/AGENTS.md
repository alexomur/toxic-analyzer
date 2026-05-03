# AGENTS.md

- Read `model/README.md` first.
- Then inspect `model/pyproject.toml`.
- Then inspect `model/src/`, `model/tests/`, and `model/configs/`.

- Use `model/notebooks/` only for research tasks.
- Do not write production code in `.ipynb`.
- Keep training, evaluation, and inference logic in Python modules under `model/src/`.
- Do not add `backend`, public API, or service-contract work to `model/` tasks unless the task explicitly requires it.
- Do not include `model/data/` or `model/artifacts/` in git changes.

- For toxicity-labeling tasks, use the working definition in `model/README.md`.
- Treat dismissive imperative cases such as `поплачь`, `ну поплачь`, `поплачь об этом`, `поплач ещё` carefully.
- Do not treat `поплач*` as a general lexical rule; use the dismissive-imperative meaning, not the token alone.
- Do not generalize that pattern to the whole root `плач`.
