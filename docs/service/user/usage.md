---
author: Nikos Sokos
created: 2026-11-02
service: wfcatalog
tags:
  - user
---

# Usage

Metadata is presented with a daily granularity. Metadata for the previous day
is always available with a maximum delay of 12 hours. Please refer to
<http://www.orfeus-eu.org/data/eida/eidaws/wfcatalog/> for a complete description of the service.

Current service major version: 1.

## Available methods

| Method | Description |
| --- | --- |
| `/query` | interface to the WFCatalog |
| `/version` | dictates service version number |
| `/application.wadl` | WADL description of service |

## GET /query: obtain waveform metadata

Example:

```
https://orfeus-eu.org/eidaws/wfcatalog/1/query?network=NL&station=HGN&channel=LHZ&starttime=2017-11-19T00:00:00Z&endtime=2017-11-20T00:00:00Z
```

Temporal constraints:

| Parameter | Type | Description |
| --- | --- | --- |
| `starttime` | string | Start time for time window in UTC; ISO-8601 i.e. 2017-11-19T12:00:00Z |
| `endtime` | string | Endtime for time window in UTC; ISO-8601 i.e. 2017-11-20T12:00:00Z |

SEED identifiers:

| Parameter | Type | Description |
| --- | --- | --- |
| `network` | string | SEED Network code |
| `station` | string | SEED Station code |
| `location` | string | SEED Location code. Use `--` for blank location identifiers |
| `channel` | string | SEED Channel code |

Request options:

| Parameter | Type | Description |
| --- | --- | --- |
| `csegments` | boolean | Include continuous segments |
| `format` | `json` | Response format |
| `granularity` | `day` | Granularity of metrics |
| `include` | `default`, `sample`, `header`, `all` | Level of detail |
| `longestonly` | boolean | Limit to single continuous segment that is the longest |
| `minimumlength` | number | Limit to continuous segment longer than this length |

Record options:

| Parameter | Type | Description |
| --- | --- | --- |
| `encoding` | `STEIM2` | Waveform data encoding |
| `num_records` | integer | Number of records in document |
| `quality` | `D`, `R`, `Q`, `M` | SEED Quality code |
| `record_length` | integer | Record length |
| `sample_rate` | number | Number of samples per second |

Sample metric options:

| Parameter | Type | Description |
| --- | --- | --- |
| `max_gap` | number | Maximum gap length in seconds |
| `max_overlap` | number | Maximum overlap length in seconds |
| `num_gaps` | integer | Number of gaps |
| `num_overlaps` | integer | Number of overlaps |
| `num_samples` | integer | Number of samples |
| `percent_availability` | integer | Percentage of available data |
| `sample_max` | integer | Maximum sample value |
| `sample_min` | integer | Minimum sample value |
| `sample_mean` | integer | Mean sample value |
| `sample_rms` | number | Quadratic mean of samples |
| `sample_stdev` | number | Standard deviation of samples |
| `sample_lower_quartile` | number | 25th percentile of samples |
| `sample_median` | number | 50th percentile of samples |
| `sample_upper_quartile` | number | 75th percentile of samples |
| `sum_gaps` | number | Sum of data gaps in seconds |
| `sum_overlaps` | number | Sum of data overlaps in seconds |

Header flag options (percentage of data with the given mSEED header flag bit set):

| Parameter | Flag |
| --- | --- |
| `amplifier_saturation` | data quality flags bit 0 |
| `digitizer_clipping` | data quality flags bit 1 |
| `spikes` | data quality flags bit 2 |
| `glitches` | data quality flags bit 3 |
| `missing_padded_data` | data quality flags bit 4 |
| `telemetry_sync_error` | data quality flags bit 5 |
| `digital_filter_charging` | data quality flags bit 6 |
| `suspect_time_tag` | data quality flags bit 7 |
| `calibration_signal` | activity flags bit 0 |
| `time_correction_applied` | activity flags bit 1 |
| `event_begin` | activity flags bit 2 |
| `event_end` | activity flags bit 3 |
| `positive_leap` | activity flags bit 4 |
| `event_in_progress` | activity flags bit 6 |
| `station_volume` | io-and-clock flags bit 0 |
| `long_record_read` | io-and-clock flags bit 1 |
| `short_record_read` | io-and-clock flags bit 2 |
| `start_time_series` | io-and-clock flags bit 3 |
| `end_time_series` | io-and-clock flags bit 4 |
| `clock_locked` | io-and-clock flags bit 5 |

Timing quality options:

| Parameter | Type | Description |
| --- | --- | --- |
| `timing_correction` | integer | Data with header field 16 to non-zero |
| `timing_quality_max` | number | Maximum timing quality value |
| `timing_quality_min` | number | Minimum timing quality value |
| `timing_quality_mean` | number | Mean timing quality value |
| `timing_quality_median` | number | 50th percentile of timing quality values |
| `timing_quality_lower_quartile` | number | 25th percentile of timing quality values |
| `timing_quality_upper_quartile` | number | 75th percentile of timing quality values |

## POST /query

A plain-text file containing a selection list can be sent to the service. The
contents of this message may contain multiple streams and traces to be
downloaded. Each line must contain the SEED stream identifiers delimited by a
space, followed by the trace starttime and endtime. Empty fields are marked by
an asterisk.

## Response codes

| Code | Meaning |
| --- | --- |
| 200 | Successful request, results follow |
| 204 | Request was properly formatted and submitted but no data matches the selection |
| 400 | Bad request due to improper specification, unrecognised parameter, parameter value out of range |
| 413 | Request would result in too much data being returned or the request itself is too large |
| 500 | Internal server error |
| 503 | Service temporarily unavailable, used in maintenance mode |

The full parameter specification is in
[wfcatalog_swagger.yaml](https://github.com/EIDA/wfcatalog/blob/master/wfcatalog_swagger.yaml)
and the JSON schema of the metadata documents in
[wf_metadata_schema.json](https://github.com/EIDA/wfcatalog/blob/master/wf_metadata_schema.json).
