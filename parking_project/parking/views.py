import datetime
import json
import qrcode
import requests
import stripe
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from geopy.distance import geodesic
from .models import ParkingArea
from .forms import PaymentForm
from celery import shared_task
from datetime import timedelta
from django.utils import timezone
from parking_project.celery import app as celery_app

stripe.api_key = settings.STRIPE_SECRET_KEY

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip #Have to change back to variable called ip later


def get_client_location(request):
    ip = get_client_ip(request)

    if ip is None:
        return None

    response = requests.get(f'https://ipinfo.io/{ip}?token=b440d5ef930e30')

    if response.status_code == 200:
        data = json.loads(response.text)
        print(f"API Response: {data}")  # Add this line to print API response

        if 'loc' in data:  # Check if 'loc' key exists in data
            return float(data['loc'].split(',')[0]), float(data['loc'].split(',')[1])
        else:
            print(f"Key 'loc' not found in API response.")
            return None
    else:
        print(f"API request failed with status code {response.status_code}.")
        return None

def get_closest_parking_areas(request):
    client_location = get_client_location(request)
    parking_areas = ParkingArea.objects.filter(available_spots__gt=0)
    parking_areas_distances = [
        (parking_area, geodesic(client_location, (parking_area.latitude, parking_area.longitude)).km)
        for parking_area in parking_areas
    ]
    parking_areas_distances.sort(key=lambda x: x[1])
    return parking_areas_distances[:5]

def process_payment(request, parking_area_id, amount):
    try:
        charge = stripe.Charge.create(
            amount=int(amount * 100),  # Amount in cents
            currency='hkd',
            source=request.POST['stripe_token'],
            description=f'Parking fee for parking area {parking_area_id}',
        )
        return charge['status'] == 'succeeded'
    except stripe.error.StripeError as e:
        return False

def index(request):
    if request.method == 'POST':
        selected_parking_area = ParkingArea.objects.get(pk=request.POST['selected_parking_area'])
        if selected_parking_area.available_spots > 0:
            payment_successful = process_payment(request, selected_parking_area.id, 10)  # Replace 10 with the desired amount
            if payment_successful:
                selected_parking_area.available_spots -= 1
                selected_parking_area.save()
                # Create the QR code with an expiry time
                qr_code = qrcode.make(f'PARK: {selected_parking_area.id}, TIME: {datetime.datetime.now()}, EXPIRY: {datetime.datetime.now() + datetime.timedelta(minutes=30)}')
                # Schedule the release_parking_spot_task to run in 30 minutes
                release_time = timezone.now() + timedelta(minutes=30)
                celery_app.send_task('parking_project.views.release_parking_spot_task', args=[selected_parking_area.id], eta=release_time)
                qr_code.save(f'media/qr_codes/{request.user.id}.png')
                return redirect('parking:qr_code')
            else:
                messages.error(request, 'Payment failed. Please try again.')
    else:
        form = PaymentForm()

    closest_parking_areas = get_closest_parking_areas(request)
    return render(request, 'parking/index.html', {'closest_parking_areas': closest_parking_areas, 'stripe_public_key': settings.STRIPE_PUBLIC_KEY})

def qr_code(request):
    return render(request, 'parking/qr_code.html', {'qr_code': f'/media/qr_codes/{request.user.id}.png'})

def release_parking_spot(request, parking_area_id):
    parking_area = ParkingArea.objects.get(pk=parking_area_id)
    parking_area.available_spots += 1
    parking_area.save()
    return JsonResponse({'status': 'success'})

@shared_task
def release_parking_spot_task(parking_area_id):
    parking_area = ParkingArea.objects.get(pk=parking_area_id)
    parking_area.available_spots += 1
    parking_area.save()