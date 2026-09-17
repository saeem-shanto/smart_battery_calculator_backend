import uuid
from django.db import models

class Calculation(models.Model):
    class Status(models.TextChoices):
        COMPLETED="completed","Completed"
        FAILED="failed","Failed"
    class SourceMode(models.TextChoices):
        SIMPLIFIED="simplified","Simplified inputs"
        UPLOAD="upload","Uploaded interval data"
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    public_id=models.UUIDField(default=uuid.uuid4,unique=True,editable=False)
    access_token_hash=models.CharField(max_length=64,editable=False)
    status=models.CharField(max_length=12,choices=Status.choices,default=Status.COMPLETED)
    source_mode=models.CharField(max_length=12,choices=SourceMode.choices)
    input_payload=models.JSONField(default=dict)
    result_payload=models.JSONField(default=dict)
    assumptions=models.JSONField(default=list)
    warnings=models.JSONField(default=list)
    algorithm_version=models.CharField(max_length=80,blank=True)
    runtime_ms=models.PositiveIntegerField(default=0)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    updated_at=models.DateTimeField(auto_now=True)

    class Meta:
        ordering=["-created_at"]

    def __str__(self): return str(self.public_id)
