"""Errors raised by OpenAI-backed assessment."""

from .base import AssessmentError


class AIAssessmentError(AssessmentError):
    """Base error for AI assessment."""


class AIAssessmentRequestError(AIAssessmentError):
    """The AI assessment request or rubric is invalid."""


class AIAssessmentInternalError(AIAssessmentError):
    """An internal error occurred while storing an AI assessment."""


class AIGradingConfigurationError(AIAssessmentError):
    """The OpenAI grading integration is not configured."""


class AIGradingServiceError(AIAssessmentError):
    """The OpenAI API failed or returned an unusable response."""
