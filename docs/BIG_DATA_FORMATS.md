# Multi-Format & Big Data Support

## Supported File Formats

The dashboard now supports multiple file formats optimized for different use cases:

### 📄 **CSV** (Comma-Separated Values)
- **Best for**: Traditional tabular data
- **Max size**: 500MB
- **Example**: `customer_data.csv`
- **Use case**: Standard data exports from databases

### 📋 **TSV** (Tab-Separated Values)
- **Best for**: Excel exports, tab-delimited data
- **Max size**: 500MB
- **Example**: `sales_data.tsv`
- **Use case**: Alternative CSV format with tab separators

### 📦 **JSON** (Array of Objects)
- **Best for**: Nested data, API exports
- **Max size**: 500MB
- **Example**: `[{"id": 1, "name": "test"}]`
- **Use case**: JSON files with array of objects or single object

### 📝 **NDJSON** (Newline-Delimited JSON)
- **Best for**: Large streaming datasets, log data
- **Max size**: 500MB
- **Example**: `{"id": 1}\n{"id": 2}\n{"id": 3}`
- **Use case**: Each line is a separate JSON object - ideal for big data

### 🚀 **Parquet** (Apache Arrow Format)
- **Best for**: Big data, columnar storage, performance
- **Max size**: 500MB
- **Example**: `data.parquet`
- **Use case**: Optimized for analytics, compression, performance with large datasets

### 📊 **Excel** (.xlsx, .xls)
- **Best for**: Business reports, Spreadsheets
- **Max size**: 500MB
- **Example**: `financial_report.xlsx`
- **Use case**: Excel workbooks (auto-reads first sheet)

## Big Data Capabilities

### File Size Handling
- **Maximum file size**: 10GB per upload by default (`MAX_UPLOAD_SIZE_GB`, configurable)
- **Large file warning**: Prompted for files > 1GB in the UI
- **Chunked processing**: Backend automatically handles large files efficiently
- **Progress feedback**: Upload status shown in real-time

### Data Preview
- **Sample size**: Preview shows first 5 rows regardless of file size
- **Schema inference**: Automatically detects all column types
- **Lazy loading**: Data is not fully loaded into memory for previews

### Performance Optimization
- **Columnar format (Parquet)**: Best performance for analytics
- **Streaming (NDJSON)**: Efficient memory usage for streaming data
- **Compression**: Parquet includes compression for storage efficiency

## How to Use

### Upload Multiple Formats
1. Go to **Dashboard → Upload Dataset**
2. Drag and drop or click to select any supported format
3. Format cards show available options with descriptions
4. Preview appears after successful upload

### Format Selection Guide

| Scenario | Recommended Format |
|----------|-------------------|
| Large time-series data (1M+ rows) | Parquet or NDJSON |
| Real-time streaming data | NDJSON |
| Data from API | JSON or NDJSON |
| Excel exports | XLSX |
| Traditional database export | CSV |
| Performance-critical analytics | Parquet |

## Backend Changes

### New API Endpoints
- `POST /api/upload` - Upload any supported format
- `GET /api/upload/formats` - Get supported format info

### File Parser Module
- Location: `backend/file_parser.py`
- Features:
  - Automatic format detection
  - Schema inference for all formats
  - Size validation (500MB limit)
  - JSON sanitization for API responses
  - Error handling with clear messages

## Big Data Best Practices

### For Large Datasets (50MB+)
1. Use **Parquet** for best performance and compression
2. Use **NDJSON** for streaming scenarios
3. Avoid Excel for files > 50MB (performance issues)

### For Analytics Workflows
1. Upload data in **Parquet** format
2. Use **Compare Mode** in experiments to see latency impact
3. Run on representative sample first, then full dataset

### For Real-Time Data
1. Use **NDJSON** format (one JSON object per line)
2. Simulates streaming input to pipeline
3. Tests baseline vs proposed with realistic data flow

## Example File Formats

### CSV Example
```csv
order_id,customer_id,amount,date
1,101,100.00,2024-01-01
2,102,250.50,2024-01-02
```

### JSON Example
```json
[
  {"order_id": 1, "customer_id": 101, "amount": 100.00},
  {"order_id": 2, "customer_id": 102, "amount": 250.50}
]
```

### NDJSON Example
```
{"order_id": 1, "customer_id": 101, "amount": 100.00}
{"order_id": 2, "customer_id": 102, "amount": 250.50}
{"order_id": 3, "customer_id": 103, "amount": 175.25}
```

## Troubleshooting

### File Upload Issues

**Error: "Unsupported file format"**
- Check file extension matches one of: csv, json, ndjson, parquet, xlsx, xls, tsv
- Ensure file extension is lowercase

**Error: "File exceeds 500MB limit"**
- Split large files into smaller chunks
- Consider converting to Parquet (better compression)
- Use sampling/filtering before upload

**Error: "Parse failed"**
- Verify file is valid (not corrupted)
- Check encoding is UTF-8
- Ensure JSON/NDJSON is properly formatted

## Future Enhancements

Possible future additions:
- Compressed format support (.gz, .bz2)
- Database direct connections (PostgreSQL, BigQuery)
- Streaming from object storage (S3, GCS)
- Incremental upload for very large files (>500MB)
- Format conversion utilities
