from pydantic import BaseModel


class CreateRequestSchema(BaseModel):
    title: str | None = None
    manikin_type: str | None = None
    training_type: str | None = None
    feedback_type: str | None = None
    training_mode: str | None = None
    duration: int | None = None
    compression_limit: int | None = None
    cycle_limit: int | None = None
    ventilation_limit: int | None = None
    per_compression: int | None = None
    per_ventilation: int | None = None
    organization_id: int
    cpr_guideline_id: int
