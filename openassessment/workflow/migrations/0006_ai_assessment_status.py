# Adds the "ai" step to AssessmentWorkflow.status choices (no SQL changes).

from django.db import migrations
import model_utils.fields


class Migration(migrations.Migration):

    dependencies = [
        ("workflow", "0005_alter_assessmentworkflow_status"),
    ]

    operations = [
        migrations.AlterField(
            model_name="assessmentworkflow",
            name="status",
            field=model_utils.fields.StatusField(
                choices=[
                    ("ai", "ai"),
                    ("peer", "peer"),
                    ("self", "self"),
                    ("training", "training"),
                    ("waiting", "waiting"),
                    ("done", "done"),
                    ("cancelled", "cancelled"),
                ],
                default="ai",
                max_length=100,
                no_check_for_status=True,
                verbose_name="status",
            ),
        ),
    ]
