"""Celery tasks for AI assessment."""

from celery import shared_task
from edx_django_utils.monitoring import set_code_owner_attribute
from submissions import api as submissions_api

from openassessment.assessment.ai_client import essay_text_from_submission, grade_essay
from openassessment.assessment.errors.ai import AIGradingServiceError
from openassessment.assessment.signals import assessment_complete_signal


@shared_task(
    bind=True,
    acks_late=True,
    autoretry_for=(AIGradingServiceError,),
    max_retries=3,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
)
@set_code_owner_attribute
def grade_essay_task(self, submission_uuid, rubric):  # pylint: disable=unused-argument
    """Grade a submission once and notify the ORA workflow when the score is ready."""
    from openassessment.assessment.api import ai as ai_api

    existing = ai_api.get_latest_assessment(submission_uuid)
    if existing is not None:
        return existing["id"]

    submission = submissions_api.get_submission(submission_uuid)
    grading_result = grade_essay(essay_text_from_submission(submission), rubric)
    assessment = ai_api.create_assessment(
        submission_uuid,
        rubric,
        grading_result["assessment"],
        grading_result["model"],
    )
    assessment_complete_signal.send(sender=grade_essay_task, submission_uuid=submission_uuid)
    return assessment["id"]
