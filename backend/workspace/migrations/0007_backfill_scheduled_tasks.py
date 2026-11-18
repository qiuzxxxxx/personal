from datetime import time

from django.db import migrations


def forwards_backfill_calendar_blocks(apps, schema_editor):
    Task = apps.get_model("workspace", "Task")
    CalendarBlock = apps.get_model("workspace", "CalendarBlock")

    scheduled_tasks = Task.objects.filter(
        deleted_at__isnull=True,
        scheduled_date__isnull=False,
    )
    for task in scheduled_tasks.iterator():
        if CalendarBlock.objects.filter(
            task_id=task.id, deleted_at__isnull=True
        ).exists():
            continue
        minutes = max(15, min(240, getattr(task, "estimated_minutes", 45) or 45))
        end_total = 9 * 60 + minutes
        end_time = time(min(23, end_total // 60), end_total % 60)
        CalendarBlock.objects.create(
            owner_id=task.owner_id,
            task_id=task.id,
            title=task.title,
            block_type="task",
            origin="backfill",
            day_date=task.scheduled_date,
            start_time=time(9, 0),
            end_time=end_time,
            duration_minutes=minutes,
            is_completed=(task.status == "done"),
        )


def reverse_backfill_calendar_blocks(apps, schema_editor):
    """Remove only blocks created by this migration.

    ``origin`` was added for exactly this purpose: rolling the data migration
    back must never delete blocks that the owner created after deployment.
    """

    CalendarBlock = apps.get_model("workspace", "CalendarBlock")
    CalendarBlock.objects.filter(origin="backfill").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("workspace", "0006_task_estimated_minutes_calendarblock_focussession"),
    ]
    operations = [
        migrations.RunPython(
            forwards_backfill_calendar_blocks,
            reverse_backfill_calendar_blocks,
        ),
    ]
