"""Interface stub for thesis Sec 4.2.4 (lead/lag analysis vs agency
ratings) -- NOT implemented yet. Deliberately not built out: it depends on
data/processed/ratings_panel.csv (src/data_acquisition/ingest_ratings.py,
issue #3), which currently has 0 real rows -- 0/44 countries have had
their rating-action history manually collected yet (see CLAUDE.md's
"Ratings data acquisition" section and state.md's open items table).

This stub exists so the plug-in point is settled now, before real ratings
data lands, rather than re-deriving the interface later: once
ratings_panel.csv has real rows, compute_lead_lag() below is where
Sec 4.2.4 / Sec 5.1's lead/lag chart and RQ1/H1's paired t-test get built.

Expected inputs (schema, not values):
  risk_labels_df : the output of build_risk_labels.label_panel() /
    data/processed/stage1_risk_labels.parquet. Required columns:
      country_code, country_name, rebal_date (quarter-end, datetime64),
      risk_label (one of core-eligible / excluded / satellite-candidate /
      insufficient_data), raw_cluster_label.
    A numeric risk *score* (not just a categorical tier) is needed for
    the paired t-test H1 describes ("mean ML risk score in the 1-4
    quarters preceding the downgrade" vs "pre-event baseline") -- the
    categorical risk_label alone isn't sufficient for that test. This
    will require build_risk_labels.py to also emit a continuous score
    (e.g. distance-to-nearest-safe-centroid, or cluster rank as a
    continuous proxy) before Sec 4.2.4 can actually run -- flagged here
    as a known follow-up, not solved by this stub.
  ratings_panel_df : data/processed/ratings_panel.csv (from
    ingest_ratings.py). Required columns: country, date, agency, rating,
    rating_numeric, action (upgrade/downgrade/affirm/initial/...),
    available_date.
  downgrade_window_quarters : int, how many quarters before/after each
    downgrade event to include in the event-window comparison (thesis
    Sec 1.5's H1 test describes 1-4 quarters preceding).

Expected output (schema, not values):
  One row per (country, downgrade event date), with at minimum:
    country, downgrade_date, pre_event_mean_risk_score,
    baseline_mean_risk_score, quarters_lead (how many quarters the risk
    score's deterioration precedes the downgrade, if any), p_value (from
    the paired t-test thesis Sec 1.5 / 4.2.4 specifies).

Do not implement the analysis body until ratings_panel.csv has real,
non-empty coverage for a meaningful subset of the 44-country universe --
building it against an empty/synthetic input would produce numbers with
nothing to validate against.
"""


def compute_lead_lag(risk_labels_df, ratings_panel_df, downgrade_window_quarters: int = 4):
    raise NotImplementedError(
        "Sec 4.2.4 lead/lag analysis is blocked on real ratings data (issue #3, "
        "0/44 countries collected as of this stub's authoring). See this module's "
        "docstring for the expected input/output schema to implement against once "
        "data/processed/ratings_panel.csv has real coverage."
    )
