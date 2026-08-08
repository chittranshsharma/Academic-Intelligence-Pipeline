import json
import logging
import pandas as pd
import os

logger = logging.getLogger(__name__)



class FacultyExporter:
    def __init__(self, input_json="cleaned_data.json", output_dir="output"):
        self.input_json = input_json
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.csv_path = os.path.join(self.output_dir, "faculty_data.csv")

    def _build_dataframe(self, data):
        df = pd.DataFrame(data)

        # ── Deduplicate ──
        if "profile_link" in df.columns:
            before = len(df)
            df = df.drop_duplicates(subset=["profile_link"], keep="first")
            removed = before - len(df)
            if removed:
                logger.info(f"Removed {removed} duplicate entries.")

        # ── Clean phone / profile_link ──
        if "phone" in df.columns:
            df["phone"] = df["phone"].fillna("NA").replace("", "NA")
        if "profile_link" in df.columns:
            df["profile_link"] = df["profile_link"].fillna("")

        # ── Rename columns ──
        rename_mapping = {
            "country":          "Region",
            "university":       "University Name",
            "department":       "Department",
            "name":             "Faculty Name",
            "origin":           "Origin",
            "role":             "Position",
            "email":            "Email",
            "phone":            "Phone",
            "profile_link":     "Profile link",
            "research_interests": "Research",
            "summary":          "Notes",
        }
        df = df.rename(columns=rename_mapping)

        # ── Column order ──
        ordered_cols = [
            "Region", "University Name", "Department", "Faculty Name",
            "Origin", "Position", "Email", "Phone", "Profile link",
            "Research", "Notes",
        ]
        existing = [c for c in ordered_cols if c in df.columns]
        df = df[existing]

        # ── Fill any remaining NaN in text cols ──
        df = df.fillna("")

        # ── S No ──
        df.insert(0, "S No", range(1, len(df) + 1))
        return df

    def export(self):
        if not os.path.exists(self.input_json):
            logger.error(f"Input file {self.input_json} does not exist.")
            return

        with open(self.input_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data:
            logger.warning("No data to export.")
            return

        df = self._build_dataframe(data)

        try:
            # ── CSV ──
            df.to_csv(self.csv_path, index=False, encoding="utf-8")
            logger.info(f"Exported CSV  -> {self.csv_path}")
        except Exception as e:
            logger.error(f"Export error: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exporter = FacultyExporter()
    exporter.export()
