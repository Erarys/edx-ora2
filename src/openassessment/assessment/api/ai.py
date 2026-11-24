"""Public workflow API for OpenAI-backed rubric assessment."""

import logging

from django.db import DatabaseError, transaction

from openassessment.assessment.ai_client import get_ai_grading_config
from openassessment.assessment.errors.ai import (
    AIAssessmentInternalError,
    AIAssessmentRequestError,
    AIGradingConfigurationError,
)
from openassessment.assessment.models import Assessment, AssessmentPart, InvalidRubricSelection
from openassessment.assessment.score_type_constants import AI_TYPE
from openassessment.assessment.serializers import (
    InvalidRubric,
    full_assessment_dict,
    rubric_from_dict,
    serialize_assessments,
)

logger = logging.getLogger(__name__)


def submitter_is_finished(submission_uuid, ai_requirements):  # pylint: disable=unused-argument
    """Learners have no additional action after submitting their response."""
    return True


def assessment_is_finished(submission_uuid, ai_requirements, course_settings):  # pylint: disable=unused-argument
    """Return whether an AI assessment has been stored for the submission."""
    return get_latest_assessment(submission_uuid) is not None


def get_score(submission_uuid, ai_requirements, course_settings):  # pylint: disable=unused-argument
    """Return the latest AI score in the workflow score format."""
    assessment = get_latest_assessment(submission_uuid)
    if assessment is None:
        return None
    return {
        "points_earned": assessment["points_earned"],
        "points_possible": assessment["points_possible"],
        "contributing_assessments": [assessment["id"]],
        "staff_id": None,
    }


def on_init(submission_uuid, rubric=None):
    """Validate configuration and enqueue grading after the workflow transaction commits."""
    if rubric is None:
        raise AIAssessmentRequestError("No rubric was provided for AI Assessment.")
    try:
        rubric_from_dict(rubric)
        get_ai_grading_config()
    except (InvalidRubric, AIGradingConfigurationError) as exc:
        raise AIAssessmentRequestError(str(exc)) from exc

    from openassessment.assessment.tasks import grade_essay_task
    transaction.on_commit(lambda: grade_essay_task.delay(submission_uuid, rubric))


def get_latest_assessment(submission_uuid):
    """Return the most recent AI assessment for a submission, if one exists."""
    try:
        assessments = serialize_assessments(Assessment.objects.filter(
            submission_uuid=submission_uuid,
            score_type=AI_TYPE,
        ).order_by("-scored_at")[:1])
    except DatabaseError as exc:
        raise AIAssessmentInternalError(
            f"Could not retrieve AI assessment for submission {submission_uuid}."
        ) from exc
    return assessments[0] if assessments else None


def get_assessment_scores_by_criteria(submission_uuid):
    """Return criterion scores from the latest AI assessment."""
    try:
        assessments = list(Assessment.objects.filter(
            submission_uuid=submission_uuid,
            score_type=AI_TYPE,
        ).order_by("-scored_at")[:1])
        return Assessment.get_median_score_dict(Assessment.scores_by_criterion(assessments))
    except DatabaseError as exc:
        raise AIAssessmentInternalError(
            f"Could not retrieve AI criterion scores for submission {submission_uuid}."
        ) from exc


@transaction.atomic
def create_assessment(submission_uuid, rubric_dict, result, model):
    """Persist validated OpenAI rubric selections as a native ORA assessment."""
    existing = get_latest_assessment(submission_uuid)
    if existing is not None:
        return existing

    options_selected = {}
    criterion_feedback = {}
    for criterion in rubric_dict.get("criteria", []):
        criterion_name = criterion["name"]
        criterion_result = result["criteria"][criterion_name]
        criterion_feedback[criterion_name] = criterion_result.get("feedback", "")
        if criterion.get("options"):
            options_selected[criterion_name] = criterion_result["selected_option"]

    try:
        rubric = rubric_from_dict(rubric_dict)
        assessment = Assessment.create(
            rubric,
            f"openai:{model}"[:40],
            submission_uuid,
            AI_TYPE,
            feedback=result.get("overall_feedback", ""),
        )
        AssessmentPart.create_from_option_names(
            assessment,
            options_selected,
            feedback=criterion_feedback,
        )
    except (InvalidRubric, InvalidRubricSelection, DatabaseError) as exc:
        logger.exception("Could not create AI assessment for submission %s", submission_uuid)
        raise AIAssessmentInternalError(str(exc)) from exc
    return full_assessment_dict(assessment)
