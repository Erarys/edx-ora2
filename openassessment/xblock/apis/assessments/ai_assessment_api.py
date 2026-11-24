"""Read-only XBlock data adapter for AI assessment results."""

from openassessment.assessment.api import ai as ai_api


class AIAssessmentAPI:
    def __init__(self, block):
        self._block = block

    @property
    def assessment(self):
        submission_uuid = self._block.workflow_data.workflow.get("submission_uuid")
        if submission_uuid is None:
            return None
        return ai_api.get_latest_assessment(submission_uuid)
