AI essay assessment
===================

Open Response Assessment can grade a learner's text response asynchronously with
the OpenAI Responses API. Course authors select **AI Assessment Only** when they
create an ORA problem, or enable **AI Assessment** in the Studio editor. The
authored ORA rubric remains the source of scoring options and points.

Configuration
-------------

Configure both the LMS web processes and the Celery workers that execute ORA
tasks. Keep the API key in a deployment secret; never expose it through XBlock
fields or browser-side configuration.

.. code-block:: python

   ORA2_AI_ASSESSMENT = {
       "API_KEY": "...",  # Prefer injecting this value from your secret store.
       "MODEL": "gpt-6-luna",
       "API_URL": "https://api.openai.com/v1/responses",
       "TIMEOUT": 90,
       # Optional: replace the default grading instructions.
       # "INSTRUCTIONS": "...",
   }

If ``API_KEY`` is omitted, ORA falls back to the ``OPENAI_API_KEY`` environment
variable. ``MODEL``, ``API_URL``, ``TIMEOUT``, and ``INSTRUCTIONS`` are optional.

How grading works
-----------------

#. A learner submits a required text response.
#. After the ORA workflow transaction commits, a Celery task sends the prompt,
   rubric, and response to the Responses API.
#. Structured Outputs restrict the result to the exact criterion and option
   names authored in the rubric. ORA validates the result again server-side.
#. ORA stores the result as a native assessment with criterion feedback,
   overall feedback, and score type ``AI``.
#. The normal ORA workflow publishes the score. A later staff assessment or
   staff override takes precedence over the AI score.

The request sets ``store`` to ``false``. Transient OpenAI service failures are
retried by Celery up to three times. The task is idempotent, so retrying does not
create duplicate assessments. File-only responses are not supported; AI
Assessment requires a text response.

Operational notes
-----------------

* Ensure a Celery worker consumes the queue used by the LMS application.
* Use a model available to the configured OpenAI project, and review its cost
  and data-handling requirements before enabling the feature in production.
* Validate grading quality with representative essays and a well-defined rubric.
  AI grading should have an escalation path to staff review.
* OpenAI API errors are not shown to learners verbatim. Operators should monitor
  Celery task failures and application logs.
