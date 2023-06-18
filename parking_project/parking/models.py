from django.db import models

class ParkingArea(models.Model):
    name = models.CharField(max_length=100)
    latitude = models.FloatField()
    longitude = models.FloatField()
    total_spots = models.IntegerField()
    available_spots = models.IntegerField()