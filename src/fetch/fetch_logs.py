import pandas as pd
from typing import Any, Dict, List

from src.db.clickhouse.services import ClickHouseServices
from src.db.redis.services import RedisServices


class FetchLogs:
    def __init__(self, start_duration: str = None, end_duration: str = None):
        self.start_duration = start_duration
        self.end_duration = end_duration

        self.redis_services = RedisServices()
        self.clickhouse_services = ClickHouseServices()

    def _flatten_column(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Dynamically flattens a single dict cell by one level.
        Nested sub-dicts are stringified to preserve their values as readable strings.

        Example:
            Input:  {'diagnostics': {'total_schedules': 511}, 'source': {'sdk': 'python'}}
            Output: {'total_schedules': 511, 'sdk': 'python'}
        """
        flat = {}
        for section, content in data.items():
            if isinstance(content, dict):
                for key, value in content.items():
                    flat[key] = str(value) if isinstance(value, dict) else value
            else:
                flat[section] = content
        return flat

    def _flatten_columns(self, df: pd.DataFrame, *column_names: str) -> pd.DataFrame:
        """
        Accepts one or more column names and flattens each of them dynamically.
        Each target column is expanded into individual columns and the original is dropped.

        Args:
            df:              Input DataFrame.
            *column_names:   One or more column names to flatten, e.g.:
                             _flatten_columns(df, "source_info")
                             _flatten_columns(df, "source_info", "server_info", "request_info")

        Returns:
            DataFrame with target columns replaced by their flattened keys.
        """
        for col in column_names:
            if col not in df.columns:
                continue  # silently skip columns that don't exist

            flattened = df[col].apply(
                lambda x: self._flatten_column(x) if isinstance(x, dict) else {}
            )
            flattened_df = pd.DataFrame(flattened.tolist(), index=df.index)
            df = pd.concat([df.drop(columns=[col]), flattened_df], axis=1)

        return df

    def _normalize_redis_record(self, raw_logs: List[Dict]) -> List[Dict]:
        normalized = []
        for record in raw_logs:
            for log_id, log_data in record.items():
                flat_record = {"log_id": log_id, **log_data}
                normalized.append(flat_record)
        return normalized

    def _build_dataframe(self, records: List[Dict]) -> pd.DataFrame:
        df = pd.DataFrame(records)
        df = self._flatten_columns(df, "source_info")
        df = self._flatten_columns(df, "message_info")
        return df

    def fetch_format_redis(self) -> pd.DataFrame:
        raw_logs = self.redis_services.get_object()
        normalized = self._normalize_redis_record(raw_logs)
        return self._build_dataframe(normalized)

    def fetch_format_clickhouse(self) -> pd.DataFrame:
        raw_logs = self.clickhouse_services.fetch_logs()
        return self._build_dataframe(raw_logs)

    def merge_format_logs(self) -> pd.DataFrame:
        redis_df = self.fetch_format_redis()
        clickhouse_df = self.fetch_format_clickhouse()

        merged_df = pd.concat([redis_df, clickhouse_df], ignore_index=True)

        merged_df["log_id"] = merged_df["log_id"].astype(str)
        merged_df["timestamp"] = pd.to_datetime(merged_df["timestamp"], utc=True)
        merged_df = merged_df.sort_values("timestamp").reset_index(drop=True)

        return merged_df


if __name__ == "__main__":
    fetch_logs = FetchLogs()
    logs = fetch_logs.merge_format_logs()
    print(f"=========={type(logs)}==========")
    print(logs.columns)
    print(logs.head())
    logs.to_csv('logs_export_20260226_081818.csv')