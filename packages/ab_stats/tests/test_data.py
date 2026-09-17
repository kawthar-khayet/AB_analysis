"""Tests de validation et de normalisation des données (étape 2)."""

from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd
import pytest

from ab_stats.data import (
    BinaryEncoding,
    DecimalAmbiguity,
    DecimalSeparator,
    ExclusionReason,
    GroupMapping,
    MetricDeclaration,
    ProposedMetricType,
    normalize,
    profile_group_column,
    profile_metric_column,
)
from ab_stats.exceptions import (
    DataValidationError,
    InsufficientSampleError,
    InternalConsistencyError,
    InvalidParameterError,
)
from ab_stats.results import Method, MetricType

# Le fichier d'exemple du guide d'import :
# visitor_id,variant,converted
VARIANT = ["control", "treatment", "control", "treatment",
           "control", "treatment", "control", "treatment"]
CONVERTED = [0, 1, 1, 0, 0, 1, 1, 1]

AB = GroupMapping(a="control", b="treatment")
BINARY = MetricDeclaration(MetricType.BINARY)
EUROS = MetricDeclaration(MetricType.CONTINUOUS, unit="euros")


def codes(dataset) -> set[str]:
    return {warning.code for warning in dataset.report.warnings}


# ---------------------------------------------------------------------------
# Profil de la colonne groupe
# ---------------------------------------------------------------------------


def test_group_profile_counts_values_by_frequency() -> None:
    profile = profile_group_column(["b", "a", "a", None, "", "a", "b", "c"])

    assert profile.n_rows == 8
    assert profile.n_missing == 2
    assert profile.n_distinct == 3
    assert [(v.value, v.count) for v in profile.values] == [("a", 3), ("b", 2), ("c", 1)]


def test_group_profile_flags_case_and_whitespace_variants_without_merging() -> None:
    profile = profile_group_column(["control", "Control", "control ", "treatment"])

    assert profile.n_distinct == 4
    assert len(profile.similar_values) == 1
    assert set(profile.similar_values[0].values) == {"control", "Control", "control "}


def test_group_profile_truncates_long_listings() -> None:
    profile = profile_group_column([f"user_{i}" for i in range(120)], max_listed=10)

    assert profile.n_distinct == 120
    assert len(profile.values) == 10
    assert profile.is_truncated


# ---------------------------------------------------------------------------
# Profil de la colonne métrique : type proposé
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ([0, 1, 1, 0], ProposedMetricType.BINARY),
        (["0", "1", "1.0", None], ProposedMetricType.BINARY),
        ([1, 1, 1], ProposedMetricType.BINARY),
        (["yes", "no", "yes"], ProposedMetricType.BINARY_ENCODABLE),
        ([0, 5, 5, 0], ProposedMetricType.BINARY_ENCODABLE),
        ([True, False, True], ProposedMetricType.BINARY_ENCODABLE),
        ([49.9, 0.0, 132.75, 27.3], ProposedMetricType.CONTINUOUS),
        (["49.90", "32.50", "n/a", "12"], ProposedMetricType.CONTINUOUS),
        (["faible", "moyen", "élevé"], ProposedMetricType.UNSUPPORTED),
        ([None, "", np.nan], ProposedMetricType.UNSUPPORTED),
    ],
)
def test_metric_profile_proposes_type(values, expected) -> None:
    assert profile_metric_column(values).proposed_type is expected


def test_metric_profile_exposes_its_evidence() -> None:
    profile = profile_metric_column([0] * 8 + [1] * 2 + [None])

    assert profile.n_rows == 11
    assert profile.n_missing == 1
    assert profile.n_distinct == 2
    assert [(v.value, v.count) for v in profile.top_values] == [("0", 8), ("1", 2)]


def test_metric_profile_reports_non_numeric_values() -> None:
    profile = profile_metric_column(["49.90", "n/a", "32.50", "?", "n/a", "12"])

    assert profile.proposed_type is ProposedMetricType.CONTINUOUS
    assert profile.n_non_numeric == 3
    assert set(profile.non_numeric_examples) == {"n/a", "?"}


# ---------------------------------------------------------------------------
# Profil de la colonne métrique : séparateur décimal
# ---------------------------------------------------------------------------


def test_metric_profile_detects_point_decimals() -> None:
    profile = profile_metric_column(["49.90", "32.50", "12"])

    assert profile.decimal_separator is DecimalSeparator.POINT
    assert profile.decimal_ambiguity is None


def test_metric_profile_detects_comma_decimals() -> None:
    profile = profile_metric_column(["49,90", "32,5", "12"])

    assert profile.decimal_separator is DecimalSeparator.COMMA
    assert profile.decimal_ambiguity is None
    assert profile.n_comma_decimal_values == 2
    assert profile.proposed_type is ProposedMetricType.CONTINUOUS


def test_metric_profile_refuses_to_guess_mixed_separators() -> None:
    profile = profile_metric_column(["49,90", "32.50", "12"])

    assert profile.decimal_separator is None
    assert profile.decimal_ambiguity is DecimalAmbiguity.MIXED_SEPARATORS


def test_metric_profile_flags_possible_thousands_separator() -> None:
    profile = profile_metric_column(["1,234", "5,678", "12,000"])

    assert profile.decimal_separator is DecimalSeparator.COMMA
    assert profile.decimal_ambiguity is DecimalAmbiguity.POSSIBLE_THOUSANDS_SEPARATOR


# ---------------------------------------------------------------------------
# Déclarations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(("a", "b"), [("control", "control"), ("", "treatment"), ("control", "  ")])
def test_group_mapping_rejects_incomplete_mapping(a, b) -> None:
    with pytest.raises(InvalidParameterError) as error:
        GroupMapping(a=a, b=b)
    assert error.value.code == "GROUP_MAPPING_INCOMPLETE"


def test_binary_encoding_rejects_identical_values() -> None:
    with pytest.raises(InvalidParameterError) as error:
        BinaryEncoding(success="yes", failure="yes")
    assert error.value.code == "BINARY_MAPPING_INVALID"


def test_binary_declaration_defaults_to_proportion_unit() -> None:
    assert MetricDeclaration(MetricType.BINARY).unit == "proportion"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"metric_type": MetricType.CONTINUOUS},
        {"metric_type": MetricType.CONTINUOUS, "unit": "proportion"},
        {"metric_type": MetricType.CONTINUOUS, "unit": "euros",
         "binary_encoding": BinaryEncoding("yes", "no")},
        {"metric_type": MetricType.BINARY, "unit": "euros"},
        {"metric_type": "binary"},
    ],
)
def test_metric_declaration_rejects_incoherent_declarations(kwargs) -> None:
    with pytest.raises(InvalidParameterError) as error:
        MetricDeclaration(**kwargs)
    assert error.value.code == "METRIC_DECLARATION_INVALID"


# ---------------------------------------------------------------------------
# Normalisation : cas nominaux
# ---------------------------------------------------------------------------


def test_normalize_binary_example_from_import_guide() -> None:
    dataset = normalize(VARIANT, CONVERTED, mapping=AB, declaration=BINARY)

    np.testing.assert_array_equal(dataset.group_a, [0, 1, 0, 1])
    np.testing.assert_array_equal(dataset.group_b, [1, 0, 1, 1])
    assert dataset.metric_type is MetricType.BINARY
    assert dataset.unit == "proportion"
    assert dataset.report.n_input == 8
    assert dataset.report.n_retained == 8
    assert dataset.report.n_excluded == 0
    assert dataset.report.exclusions == ()


def test_normalize_accepts_declared_binary_encoding() -> None:
    dataset = normalize(
        ["control", "treatment", "control", "treatment"],
        ["no", "yes", "yes", "yes"],
        mapping=AB,
        declaration=MetricDeclaration(MetricType.BINARY, binary_encoding=BinaryEncoding("yes", "no")),
    )

    np.testing.assert_array_equal(dataset.group_a, [0, 1])
    np.testing.assert_array_equal(dataset.group_b, [1, 1])


def test_normalize_continuous_metric() -> None:
    dataset = normalize(
        ["control", "treatment", "control", "treatment"],
        ["42.5", 49.0, " 38 ", "55.5"],
        mapping=AB,
        declaration=EUROS,
    )

    np.testing.assert_array_equal(dataset.group_a, [42.5, 38.0])
    np.testing.assert_array_equal(dataset.group_b, [49.0, 55.5])
    assert dataset.unit == "euros"


def test_normalize_converts_declared_comma_decimals_and_records_it() -> None:
    dataset = normalize(
        ["control", "treatment", "control", "treatment"],
        ["49,90", "32,50", "12", "0,75"],
        mapping=AB,
        declaration=MetricDeclaration(
            MetricType.CONTINUOUS, unit="euros", decimal_separator=DecimalSeparator.COMMA
        ),
    )

    np.testing.assert_array_equal(dataset.group_a, [49.90, 12.0])
    np.testing.assert_array_equal(dataset.group_b, [32.50, 0.75])
    assert dataset.report.decimal_conversions == 3


def test_normalize_accepts_pandas_and_numpy_columns() -> None:
    frame = pd.DataFrame({"variant": VARIANT, "converted": CONVERTED})

    from_pandas = normalize(frame["variant"], frame["converted"], mapping=AB, declaration=BINARY)
    from_numpy = normalize(np.array(VARIANT), np.array(CONVERTED), mapping=AB, declaration=BINARY)

    np.testing.assert_array_equal(from_pandas.group_a, from_numpy.group_a)
    np.testing.assert_array_equal(from_pandas.group_b, [1, 0, 1, 1])


def test_normalized_arrays_are_read_only() -> None:
    dataset = normalize(VARIANT, CONVERTED, mapping=AB, declaration=BINARY)

    with pytest.raises(ValueError):
        dataset.group_a[0] = 1.0


def test_validation_report_is_frozen() -> None:
    dataset = normalize(VARIANT, CONVERTED, mapping=AB, declaration=BINARY)

    with pytest.raises(dataclasses.FrozenInstanceError):
        dataset.report.n_input = 0


# ---------------------------------------------------------------------------
# Normalisation : exclusions
# ---------------------------------------------------------------------------


def test_exclusions_are_counted_by_reason_with_sample_rows() -> None:
    groups = ["control", None, "treatment", "control", "treatment", "control", "treatment"]
    metric = ["10", "20", "", "n/a", "30", "40", "?"]

    dataset = normalize(groups, metric, mapping=AB, declaration=EUROS)
    report = dataset.report

    np.testing.assert_array_equal(dataset.group_a, [10.0, 40.0])
    np.testing.assert_array_equal(dataset.group_b, [30.0])
    assert report.n_input == 7
    assert report.n_retained == 3
    assert report.n_excluded == 4
    assert report.excluded(ExclusionReason.MISSING_GROUP) == 1
    assert report.excluded(ExclusionReason.MISSING_METRIC) == 1
    assert report.excluded(ExclusionReason.NON_NUMERIC_METRIC) == 2

    by_reason = {summary.reason: summary for summary in report.exclusions}
    assert by_reason[ExclusionReason.MISSING_GROUP].sample_row_indices == (1,)
    assert by_reason[ExclusionReason.NON_NUMERIC_METRIC].sample_row_indices == (3, 6)
    assert {v.value for v in by_reason[ExclusionReason.NON_NUMERIC_METRIC].values} == {"n/a", "?"}


def test_one_row_is_excluded_for_a_single_reason_only() -> None:
    # Groupe manquant ET métrique manquante : seul le premier motif compte.
    dataset = normalize(
        [None, "control", "treatment"], [None, "1", "2"], mapping=AB, declaration=EUROS
    )

    assert dataset.report.excluded(ExclusionReason.MISSING_GROUP) == 1
    assert dataset.report.excluded(ExclusionReason.MISSING_METRIC) == 0


def test_booleans_and_infinite_values_are_not_continuous_numbers() -> None:
    dataset = normalize(
        ["control", "treatment", "control", "treatment", "control"],
        [True, 2.0, float("inf"), 3.0, 4.0],
        mapping=AB,
        declaration=EUROS,
    )

    assert dataset.report.excluded(ExclusionReason.NON_NUMERIC_METRIC) == 2
    np.testing.assert_array_equal(dataset.group_a, [4.0])


# ---------------------------------------------------------------------------
# Normalisation : groupes non mappés (option 2)
# ---------------------------------------------------------------------------


GROUPS_WITH_DIRTY_VALUE = ["control", "treatment", "Control", "control", "treatment"]
METRIC_FOR_DIRTY = [0, 1, 1, 1, 0]


def test_unmapped_group_values_block_until_exclusion_is_confirmed() -> None:
    with pytest.raises(DataValidationError) as error:
        normalize(GROUPS_WITH_DIRTY_VALUE, METRIC_FOR_DIRTY, mapping=AB, declaration=BINARY)

    assert error.value.code == "UNMAPPED_GROUP_VALUES"
    assert error.value.details["unmapped_values"] == [{"value": "Control", "count": 1}]
    assert error.value.details["affected_rows"] == 1
    assert error.value.details["similar_to_mapped"] == [
        {"value": "Control", "resembles": "control"}
    ]


def test_confirmed_unmapped_exclusion_is_recorded_and_warned() -> None:
    dataset = normalize(
        GROUPS_WITH_DIRTY_VALUE,
        METRIC_FOR_DIRTY,
        mapping=AB,
        declaration=BINARY,
        exclude_unmapped_groups=True,
    )

    assert dataset.report.excluded(ExclusionReason.UNMAPPED_GROUP_VALUE) == 1
    assert dataset.n_a == 2
    assert dataset.n_b == 2
    assert "SIMILAR_GROUP_VALUES" in codes(dataset)


def test_mapped_value_not_found_suggests_close_values() -> None:
    with pytest.raises(DataValidationError) as error:
        normalize(
            VARIANT,
            CONVERTED,
            mapping=GroupMapping(a="Control", b="treatment"),
            declaration=BINARY,
        )

    assert error.value.code == "GROUP_VALUE_NOT_FOUND"
    missing = error.value.details["missing"]
    assert missing == [{"field": "a", "value": "Control", "did_you_mean": ["control"]}]


# ---------------------------------------------------------------------------
# Normalisation : validation du type déclaré
# ---------------------------------------------------------------------------


def test_binary_metric_with_value_two_is_blocking() -> None:
    """Le cas du cahier des charges : 0, 1, 0, 2, 1 déclaré binaire."""
    with pytest.raises(DataValidationError) as error:
        normalize(
            ["control", "treatment", "control", "treatment", "control"],
            [0, 1, 0, 2, 1],
            mapping=AB,
            declaration=BINARY,
            metric_column_name="converted",
        )

    details = error.value.details
    assert error.value.code == "BINARY_VALIDATION_FAILED"
    assert details["column"] == "converted"
    assert details["expected_values"] == ["0", "1"]
    assert details["unexpected_values"] == [{"value": "2", "count": 1}]
    assert details["affected_rows"] == 1
    assert details["total_rows"] == 5
    assert details["sample_row_indices"] == [3]


def test_invalid_value_in_an_excluded_row_is_not_reported() -> None:
    # Le « 2 » appartient à variant_green, dont l'exclusion est confirmée :
    # il ne fait pas partie de l'analyse, il ne doit rien déclencher.
    dataset = normalize(
        ["control", "treatment", "variant_green", "control", "treatment"],
        [0, 1, 2, 1, 0],
        mapping=AB,
        declaration=BINARY,
        exclude_unmapped_groups=True,
    )

    assert dataset.report.n_retained == 4


def test_undeclared_text_encoding_is_blocking() -> None:
    with pytest.raises(DataValidationError) as error:
        normalize(["control", "treatment"], ["yes", "no"], mapping=AB, declaration=BINARY)

    assert error.value.code == "BINARY_VALIDATION_FAILED"
    assert {v["value"] for v in error.value.details["unexpected_values"]} == {"yes", "no"}


def test_declared_encoding_is_exact_and_blocks_other_spellings() -> None:
    with pytest.raises(DataValidationError) as error:
        normalize(
            ["control", "treatment", "control"],
            ["yes", "no", "YES"],
            mapping=AB,
            declaration=MetricDeclaration(
                MetricType.BINARY, binary_encoding=BinaryEncoding("yes", "no")
            ),
        )

    assert error.value.code == "BINARY_ENCODING_INCOMPLETE"
    assert error.value.details["expected_values"] == ["no", "yes"]
    assert error.value.details["unexpected_values"] == [{"value": "YES", "count": 1}]


def test_comma_decimals_declared_as_point_are_blocking() -> None:
    with pytest.raises(DataValidationError) as error:
        normalize(["control", "treatment"], ["49,90", "32.50"], mapping=AB, declaration=EUROS)

    assert error.value.code == "DECIMAL_SEPARATOR_MISMATCH"
    assert error.value.details["declared_separator"] == "."
    assert error.value.details["examples"] == [{"value": "49,90", "count": 1}]


def test_point_decimals_declared_as_comma_are_blocking() -> None:
    declaration = MetricDeclaration(
        MetricType.CONTINUOUS, unit="euros", decimal_separator=DecimalSeparator.COMMA
    )
    with pytest.raises(DataValidationError) as error:
        normalize(["control", "treatment"], ["49,90", "32.50"], mapping=AB, declaration=declaration)

    assert error.value.code == "DECIMAL_SEPARATOR_MISMATCH"
    assert error.value.details["examples"] == [{"value": "32.50", "count": 1}]


# ---------------------------------------------------------------------------
# Normalisation : blocages structurels
# ---------------------------------------------------------------------------


def test_column_length_mismatch_is_an_internal_error() -> None:
    with pytest.raises(InternalConsistencyError) as error:
        normalize(VARIANT, CONVERTED[:-1], mapping=AB, declaration=BINARY)

    assert error.value.code == "COLUMN_LENGTH_MISMATCH"
    assert error.value.details["group_length"] == 8
    assert error.value.details["metric_length"] == 7


def test_empty_dataset_is_rejected() -> None:
    with pytest.raises(DataValidationError) as error:
        normalize([], [], mapping=AB, declaration=BINARY)
    assert error.value.code == "EMPTY_DATASET"


def test_group_emptied_by_exclusions_is_blocking() -> None:
    with pytest.raises(InsufficientSampleError) as error:
        normalize(
            ["control", "treatment", "control", "treatment"],
            ["10", None, "12", ""],
            mapping=AB,
            declaration=EUROS,
        )

    assert error.value.code == "EMPTY_GROUP"
    assert error.value.details["empty_groups"] == ["b"]
    assert error.value.details["exclusions"] == {"MISSING_METRIC": 2}


def test_all_rows_excluded_is_blocking() -> None:
    with pytest.raises(InsufficientSampleError) as error:
        normalize(["control", "treatment"], ["n/a", "?"], mapping=AB, declaration=EUROS)

    assert error.value.code == "ALL_ROWS_EXCLUDED"


def test_a_string_is_not_a_column() -> None:
    with pytest.raises(InvalidParameterError) as error:
        normalize("control", [1], mapping=AB, declaration=BINARY)
    assert error.value.code == "INVALID_COLUMN"


def test_two_dimensional_array_is_not_a_column() -> None:
    with pytest.raises(InvalidParameterError) as error:
        normalize(np.array([["control"], ["treatment"]]), [0, 1], mapping=AB, declaration=BINARY)
    assert error.value.code == "INVALID_COLUMN"


# ---------------------------------------------------------------------------
# Normalisation : avertissements
# ---------------------------------------------------------------------------


def test_high_exclusion_rate_warning() -> None:
    dataset = normalize(
        ["control", "treatment", "control", "treatment", "control"],
        ["10", "11", "12", "13", None],
        mapping=AB,
        declaration=EUROS,
        high_exclusion_rate=0.10,
    )

    assert "HIGH_EXCLUSION_RATE" in codes(dataset)


def test_continuous_metric_with_two_values_warns_and_suggests_binary() -> None:
    dataset = normalize(VARIANT, CONVERTED, mapping=AB, declaration=EUROS)

    warning = next(w for w in dataset.report.warnings if w.code == "CONTINUOUS_WITH_TWO_VALUES")
    assert warning.suggested_alternative is Method.TWO_PROPORTION_Z


def test_constant_group_warns_zero_variance() -> None:
    dataset = normalize(
        ["control", "treatment", "control", "treatment"],
        [0, 1, 0, 0],
        mapping=AB,
        declaration=BINARY,
    )

    warnings = [w for w in dataset.report.warnings if w.code == "ZERO_VARIANCE"]
    assert [w.affected_field for w in warnings] == ["group_a"]


def test_clean_dataset_has_no_warning() -> None:
    dataset = normalize(VARIANT, CONVERTED, mapping=AB, declaration=BINARY)

    assert dataset.report.warnings == ()


def test_invalid_exclusion_rate_threshold_is_rejected() -> None:
    with pytest.raises(InvalidParameterError):
        normalize(VARIANT, CONVERTED, mapping=AB, declaration=BINARY, high_exclusion_rate=0)
