from pydantic import BaseModel

from models import TrainingProgram


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
    cvr_compression: int | None = None
    cvr_ventilation: int | None = None
    organization_id: int
    cpr_guideline_id: int

    @property
    def convert_to_model(self):
        return TrainingProgram(
            title=self.title,
            manikin_type=self.manikin_type,
            training_type=self.training_type,
            feedback_type=self.feedback_type,
            training_mode=self.training_mode,
            duration=self.duration,
            compression_limit=self.compression_limit,
            cycle_limit=self.cycle_limit,
            ventilation_limit=self.ventilation_limit,
            per_compression=self.per_compression,
            per_ventilation=self.per_ventilation,
            cpr_guideline_id=self.cpr_guideline_id if self.cpr_guideline_id else 2,
            organization_id=self.organization_id
        )


class CreateResponseSchema(BaseModel):
    id: int
    title: str | None = None
    manikin_type: str | None = None
    training_type: str | None = None
    feedback_type: str | None = None
    training_mode: str | None = None
    duration: int | None = None
    compression_limit: int | None = None
    cycle_limit: int | None = None
    ventilation_limit: int | None = None
    cvr_compression: int | None = None
    cvr_ventilation: int | None = None
    organization_id: int
    cpr_guideline_id: int