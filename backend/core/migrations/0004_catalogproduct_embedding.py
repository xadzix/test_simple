from django.db import migrations
from pgvector.django import VectorExtension, VectorField


class Migration(migrations.Migration):
    dependencies = [("core", "0003_remove_out_of_scope_fields")]

    operations = [
        VectorExtension(),
        migrations.AddField(
            model_name="catalogproduct",
            name="embedding",
            field=VectorField(dimensions=1536, null=True),
        ),
    ]
