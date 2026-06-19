from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Estimate, PriceList


@receiver(post_delete, sender=PriceList)
@receiver(post_delete, sender=Estimate)
def delete_import_file(sender, instance, **kwargs):
    if instance.file:
        instance.file.delete(save=False)
