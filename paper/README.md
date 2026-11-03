# Paper

The paper, "Non-player characters that learn, grow up, and pass it on", is a
Research Article for **ACM Games: Research and Practice**. Its LaTeX source is
kept in its own repository.

`check_numbers.py` checks that every number the paper quotes matches the run
logs, reading the paper's LaTeX from `../paper-hearthwick-ACMGames` beside
this repository and the runs from `runs/`:

```bash
python paper/check_numbers.py --paper submission
```

It needs the run logs (the paper's data archive) in `runs/` and the results
in `results/`. It also prints the paper's word count, references included.
