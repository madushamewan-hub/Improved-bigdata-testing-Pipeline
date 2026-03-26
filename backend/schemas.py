from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

class DatasetCreate(BaseModel):
    name: str
    type: str
    schema_json: Dict[str, Any]

class DatasetResponse(BaseModel):
    id: int
    name: str
    type: str
    uploaded_at: datetime
    row_count: int
    schema_json: Dict[str, Any]

class StageCheckResultResponse(BaseModel):
    stage_name: str
    check_name: str
    issue_type: str
    passed: bool
    findings_count: int
    notes: Optional[str]

class PipelineResultResponse(BaseModel):
    pipeline_type: str
    detection_accuracy: float
    precision: float
    recall: float
    false_positives: int
    false_negatives: int
    detected_loss: int
    detected_duplicates: int
    detected_corruption: int
    detected_inconsistency: int
    latency_ms: float
    overhead_ms: float

class ExperimentRunRequest(BaseModel):
    dataset_id: int
    scenario_name: str
    mode: str  # baseline, proposed, compare

class ExperimentRunResponse(BaseModel):
    id: int
    dataset_id: int
    scenario_name: str
    mode: str
    status: str
    started_at: datetime
    finished_at: Optional[datetime]

class DashboardStats(BaseModel):
    total_experiments: int
    baseline_detection_rate: float
    proposed_detection_rate: float
    baseline_false_negatives: int
    proposed_false_negatives: int
    average_overhead_ms: float

class PipelineFlowNode(BaseModel):
    id: str
    label: str
    stage: str
    checks: List[str]
    issue_types: List[str]
    x: int
    y: int

class PipelineFlowResponse(BaseModel):
    pipeline_type: str
    nodes: List[PipelineFlowNode]
    edges: List[Dict[str, str]]