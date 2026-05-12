import json
import logging
import pandas as pd
import os
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

logger = logging.getLogger(__name__)

# Column display widths (in Excel units). Adjust as needed.
COLUMN_WIDTHS = {
    "S No":           6,
    "Region":         10,
    "University Name": 30,
