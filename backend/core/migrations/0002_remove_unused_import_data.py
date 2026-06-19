from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0001_initial")]

    operations = [
        migrations.RemoveField(model_name="estimate", name="task_id"),
        migrations.RemoveField(model_name="estimateitem", name="raw_data"),
        migrations.RemoveField(model_name="pricelist", name="task_id"),
        migrations.RemoveField(
            model_name="supplierpriceitem", name="raw_data"
        ),
    ]
