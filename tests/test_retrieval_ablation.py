"""The threshold ablation's arms keep their own settings under a profile
(experiments/retrieval_ablation.py, RUNNING_EXPERIMENTS.md step 1)."""

from experiments.retrieval_ablation import CONFIGS, arm_config


def test_every_arm_keeps_what_it_sets_under_the_illustrative_profile():
    """The illustrative profile sets restore_below_threshold off. Applied
    after the arm, it turned the restored arm into the unrestored one, and the
    ablation's check that the two match at t=0 passed without testing
    anything."""
    for label, overrides in CONFIGS:
        config = arm_config(overrides, seed=1, village="greater", profile="illustrative")
        for name, value in overrides.items():
            assert getattr(config, name) == value, (label, name)


def test_the_profile_still_sets_everything_else():
    config = arm_config(dict(CONFIGS[4][1]), seed=1, village="greater", profile="illustrative")
    assert config.restore_below_threshold is True
    assert config.lessons_satisfied is True and config.declared_lessons is True
    assert config.days_per_year == 28


def test_a_year_given_explicitly_wins():
    config = arm_config(dict(CONFIGS[0][1]), seed=1, village="greater",
                        days_per_year=8, profile="illustrative")
    assert config.days_per_year == 8
