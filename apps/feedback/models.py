import uuid
from django.db import models
from apps.calculations.models import Calculation

class Feedback(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    calculation=models.ForeignKey(Calculation,null=True,blank=True,on_delete=models.SET_NULL,related_name="feedback_items")
    rating=models.PositiveSmallIntegerField()
    comment=models.TextField(blank=True,max_length=2000)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    def __str__(self): return f"{self.rating}/5 - {self.created_at:%Y-%m-%d}"
