"""Les sept méthodes d'analyse du catalogue."""

from ab_stats.analyses.binary import fisher_exact, two_proportion_z
from ab_stats.analyses.continuous import student_t, welch_t
from ab_stats.analyses.nonparametric import mann_whitney_u
from ab_stats.analyses.resampling import bootstrap_test, permutation_test

__all__ = [
    "two_proportion_z",
    "fisher_exact",
    "welch_t",
    "student_t",
    "mann_whitney_u",
    "permutation_test",
    "bootstrap_test",
]
