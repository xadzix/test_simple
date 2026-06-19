from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("core", "0002_remove_unused_import_data")]

    operations = [
        migrations.AlterModelOptions(
            name="catalogproduct", options={"ordering": ["name"]}
        ),
        migrations.AlterModelOptions(
            name="pricelist", options={"ordering": ["-created_at"]}
        ),
        migrations.AlterModelOptions(
            name="supplier", options={"ordering": ["name"]}
        ),
        migrations.RemoveField(model_name="catalogproduct", name="updated_at"),
        migrations.RemoveField(model_name="estimate", name="updated_at"),
        migrations.RemoveField(
            model_name="estimateitem", name="matched_automatically"
        ),
        migrations.RemoveField(model_name="pricelist", name="updated_at"),
        migrations.RemoveField(model_name="project", name="description"),
        migrations.RemoveField(model_name="project", name="updated_at"),
        migrations.RemoveField(model_name="supplier", name="updated_at"),
        migrations.AlterField(
            model_name="estimateitem",
            name="match_status",
            field=models.CharField(
                choices=[
                    ("matched", "Сопоставлено"),
                    ("no_match", "Без соответствия"),
                ],
                default="no_match",
                max_length=16,
            ),
        ),
    ]
