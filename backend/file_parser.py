"""
Multi-format file parser for supporting various data input formats.
Handles CSV, JSON, Parquet, Excel, TSV, and NDJSON files.
"""
import os
import json
import pandas as pd
from typing import Tuple, Any, Dict
from pathlib import Path


class FileParser:
    """Parse different file formats into pandas DataFrame"""
    
    SUPPORTED_FORMATS = ['csv', 'json', 'ndjson', 'parquet', 'xlsx', 'xls', 'tsv']
    MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
    PREVIEW_ROWS = 5
    
    @staticmethod
    def get_file_format(filename: str) -> str:
        """Detect file format from filename"""
        ext = Path(filename).suffix.lower().lstrip('.')
        if ext == 'ndjson':
            return 'ndjson'
        return ext if ext in FileParser.SUPPORTED_FORMATS else None
    
    @staticmethod
    def validate_file(file_path: str, file_size: int) -> Tuple[bool, str]:
        """Validate file size and format"""
        if file_size > FileParser.MAX_FILE_SIZE:
            return False, f"File exceeds 500MB limit. Size: {file_size / 1024 / 1024:.1f}MB"
        
        if not os.path.exists(file_path):
            return False, "File not found"
        
        return True, ""
    
    @staticmethod
    def parse_csv(file_path: str, **kwargs) -> pd.DataFrame:
        """Parse CSV file"""
        try:
            # Support various CSV formats
            sep = kwargs.get('sep', ',')
            df = pd.read_csv(file_path, sep=sep, low_memory=False)
            return df
        except Exception as e:
            raise ValueError(f"CSV parse failed: {str(e)}")
    
    @staticmethod
    def parse_tsv(file_path: str, **kwargs) -> pd.DataFrame:
        """Parse TSV file"""
        try:
            df = pd.read_csv(file_path, sep='\t', low_memory=False)
            return df
        except Exception as e:
            raise ValueError(f"TSV parse failed: {str(e)}")
    
    @staticmethod
    def parse_json(file_path: str, **kwargs) -> pd.DataFrame:
        """Parse JSON file (array of objects)"""
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            # Handle JSON array
            if isinstance(data, list):
                df = pd.DataFrame(data)
            elif isinstance(data, dict):
                # Single object - convert to single-row dataframe
                df = pd.DataFrame([data])
            else:
                raise ValueError("JSON must be an array of objects or a single object")
            
            return df
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"JSON processing failed: {str(e)}")
    
    @staticmethod
    def parse_ndjson(file_path: str, **kwargs) -> pd.DataFrame:
        """Parse NDJSON file (newline-delimited JSON)"""
        try:
            records = []
            with open(file_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        records.append(json.loads(line))
            
            if not records:
                raise ValueError("NDJSON file is empty")
            
            df = pd.DataFrame(records)
            return df
        except json.JSONDecodeError as e:
            raise ValueError(f"NDJSON parse failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"NDJSON processing failed: {str(e)}")
    
    @staticmethod
    def parse_parquet(file_path: str, **kwargs) -> pd.DataFrame:
        """Parse Parquet file"""
        try:
            df = pd.read_parquet(file_path)
            return df
        except Exception as e:
            raise ValueError(f"Parquet parse failed: {str(e)}")
    
    @staticmethod
    def parse_excel(file_path: str, **kwargs) -> pd.DataFrame:
        """Parse Excel file (.xlsx, .xls)"""
        try:
            sheet_name = kwargs.get('sheet_name', 0)  # Default first sheet
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            return df
        except Exception as e:
            raise ValueError(f"Excel parse failed: {str(e)}")
    
    @staticmethod
    def parse_file(file_path: str, file_format: str, **kwargs) -> Tuple[pd.DataFrame, Dict[str, str]]:
        """
        Main entry point: Parse file and return DataFrame + schema
        
        Args:
            file_path: Path to file
            file_format: File format (csv, json, parquet, etc.)
            **kwargs: Format-specific options
            
        Returns:
            Tuple of (DataFrame, schema_dict)
        """
        format_lower = file_format.lower()
        
        parsers = {
            'csv': FileParser.parse_csv,
            'tsv': FileParser.parse_tsv,
            'json': FileParser.parse_json,
            'ndjson': FileParser.parse_ndjson,
            'parquet': FileParser.parse_parquet,
            'xlsx': FileParser.parse_excel,
            'xls': FileParser.parse_excel,
        }
        
        if format_lower not in parsers:
            raise ValueError(f"Unsupported format: {file_format}. Supported: {', '.join(FileParser.SUPPORTED_FORMATS)}")
        
        parser_fn = parsers[format_lower]
        df = parser_fn(file_path, **kwargs)
        
        # Infer schema
        schema = {col: str(df[col].dtype) for col in df.columns}
        
        return df, schema
    
    @staticmethod
    def get_preview(df: pd.DataFrame, rows: int = 5) -> list:
        """Get preview of dataframe rows as JSON-safe format"""
        preview_records = df.head(rows).to_dict(orient="records")
        # Sanitize NaN/inf values
        from backend.main import _sanitize_for_json
        return _sanitize_for_json(preview_records)
    
    @staticmethod
    def get_format_info() -> Dict[str, Dict[str, str]]:
        """Return info about supported file formats"""
        return {
            'csv': {
                'icon': '📄',
                'label': 'CSV (Comma-Separated)',
                'description': 'Standard CSV format with comma delimiter',
                'example': 'data.csv'
            },
            'tsv': {
                'icon': '📋',
                'label': 'TSV (Tab-Separated)',
                'description': 'Tab-separated values format',
                'example': 'data.tsv'
            },
            'json': {
                'icon': '📦',
                'label': 'JSON (Array)',
                'description': 'Array of JSON objects or single object',
                'example': '[{"id": 1, "name": "test"}]'
            },
            'ndjson': {
                'icon': '📝',
                'label': 'NDJSON (Streaming)',
                'description': 'Newline-delimited JSON, ideal for large datasets',
                'example': '{"id": 1}\n{"id": 2}'
            },
            'parquet': {
                'icon': '🚀',
                'label': 'Parquet (Big Data)',
                'description': 'Columnar format optimized for large datasets',
                'example': 'data.parquet'
            },
            'xlsx': {
                'icon': '📊',
                'label': 'Excel (.xlsx)',
                'description': 'Modern Excel spreadsheet format',
                'example': 'data.xlsx'
            },
            'xls': {
                'icon': '📊',
                'label': 'Excel (.xls)',
                'description': 'Legacy Excel format',
                'example': 'data.xls'
            }
        }
