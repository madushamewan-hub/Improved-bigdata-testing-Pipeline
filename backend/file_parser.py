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
    MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB (increased from 500MB)
    PREVIEW_ROWS = 5
    CHUNK_SIZE = 100000  # Process in chunks of 100k rows for large files
    
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
            return False, f"File exceeds 2GB limit. Size: {file_size / 1024 / 1024 / 1024:.1f}GB"
        
        if not os.path.exists(file_path):
            return False, "File not found"
        
        return True, ""
    
    @staticmethod
    def parse_csv(file_path: str, **kwargs) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse CSV file with chunked reading for large files"""
        try:
            # Get file size to determine if chunking is needed
            file_size = os.path.getsize(file_path)
            chunk_size = kwargs.get('chunksize', FileParser.CHUNK_SIZE)
            
            # First, get total row count without loading all data
            total_rows = sum(1 for _ in open(file_path)) - 1  # Subtract header
            
            # For large files, use chunked reading
            if file_size > 100 * 1024 * 1024:  # 100MB threshold
                chunks = []
                rows_processed = 0
                for chunk in pd.read_csv(file_path, sep=',', low_memory=False, chunksize=chunk_size):
                    chunks.append(chunk)
                    rows_processed += len(chunk)
                    # Limit total chunks to prevent memory issues
                    if len(chunks) * chunk_size > 1000000:  # Max 1M rows
                        break
                if chunks:
                    df = pd.concat(chunks, ignore_index=True)
                else:
                    df = pd.DataFrame()
                
                processing_mode = "limited" if rows_processed < total_rows else "full"
            else:
                # Small files - read directly
                df = pd.read_csv(file_path, sep=',', low_memory=False)
                rows_processed = len(df)
                total_rows = rows_processed
                processing_mode = "full"
            
            return df, {
                "total_rows": total_rows,
                "rows_processed": rows_processed,
                "processing_mode": processing_mode,
                "truncated": rows_processed < total_rows
            }
        except Exception as e:
            raise ValueError(f"CSV parse failed: {str(e)}")
    
    @staticmethod
    def parse_tsv(file_path: str, **kwargs) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse TSV file"""
        try:
            # Get total row count
            total_rows = sum(1 for _ in open(file_path)) - 1  # Subtract header
            
            df = pd.read_csv(file_path, sep='\t', low_memory=False)
            rows_processed = len(df)
            
            processing_mode = "limited" if rows_processed < total_rows else "full"
            
            return df, {
                "total_rows": total_rows,
                "rows_processed": rows_processed,
                "processing_mode": processing_mode,
                "truncated": rows_processed < total_rows
            }
        except Exception as e:
            raise ValueError(f"TSV parse failed: {str(e)}")
    
    @staticmethod
    def parse_json(file_path: str, **kwargs) -> Tuple[pd.DataFrame, Dict[str, Any]]:
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
            
            total_rows = len(df)
            return df, {
                "total_rows": total_rows,
                "rows_processed": total_rows,
                "processing_mode": "full",
                "truncated": False
            }
        except json.JSONDecodeError as e:
            raise ValueError(f"JSON parse failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"JSON processing failed: {str(e)}")
    
    @staticmethod
    def parse_ndjson(file_path: str, **kwargs) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse NDJSON file (newline-delimited JSON) with chunked reading"""
        try:
            records = []
            max_records = kwargs.get('max_records', 1000000)  # Limit to 1M records
            
            # First pass: count total lines
            total_lines = sum(1 for _ in open(file_path))
            
            # Second pass: parse records
            rows_processed = 0
            with open(file_path, 'r') as f:
                for line_num, line in enumerate(f):
                    line = line.strip()
                    if line:
                        try:
                            record = json.loads(line)
                            records.append(record)
                            rows_processed += 1
                        except json.JSONDecodeError:
                            # Skip malformed lines but continue
                            continue
                    
                    # Limit records to prevent memory issues
                    if len(records) >= max_records:
                        break
            
            if not records:
                raise ValueError("NDJSON file is empty or contains no valid JSON")
            
            df = pd.DataFrame(records)
            
            processing_mode = "limited" if rows_processed < total_lines else "full"
            
            return df, {
                "total_rows": total_lines,
                "rows_processed": rows_processed,
                "processing_mode": processing_mode,
                "truncated": rows_processed < total_lines
            }
        except json.JSONDecodeError as e:
            raise ValueError(f"NDJSON parse failed: {str(e)}")
        except Exception as e:
            raise ValueError(f"NDJSON processing failed: {str(e)}")
    
    @staticmethod
    def parse_parquet(file_path: str, **kwargs) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse Parquet file"""
        try:
            df = pd.read_parquet(file_path)
            total_rows = len(df)
            return df, {
                "total_rows": total_rows,
                "rows_processed": total_rows,
                "processing_mode": "full",
                "truncated": False
            }
        except Exception as e:
            raise ValueError(f"Parquet parse failed: {str(e)}")
    
    @staticmethod
    def parse_excel(file_path: str, **kwargs) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Parse Excel file (.xlsx, .xls)"""
        try:
            sheet_name = kwargs.get('sheet_name', 0)  # Default first sheet
            df = pd.read_excel(file_path, sheet_name=sheet_name)
            total_rows = len(df)
            return df, {
                "total_rows": total_rows,
                "rows_processed": total_rows,
                "processing_mode": "full",
                "truncated": False
            }
        except Exception as e:
            raise ValueError(f"Excel parse failed: {str(e)}")
    
    @staticmethod
    def parse_file(file_path: str, file_format: str, **kwargs) -> Tuple[pd.DataFrame, Dict[str, str], Dict[str, Any]]:
        """
        Main entry point: Parse file and return DataFrame + schema + processing info
        
        Args:
            file_path: Path to file
            file_format: File format (csv, json, parquet, etc.)
            **kwargs: Format-specific options
            
        Returns:
            Tuple of (DataFrame, schema_dict, processing_info)
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
        df, processing_info = parser_fn(file_path, **kwargs)
        
        # Infer schema
        schema = {col: str(df[col].dtype) for col in df.columns}
        
        return df, schema, processing_info
    
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
