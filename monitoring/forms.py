from django import forms

from .models import MonitorTarget


class MonitorTargetForm(forms.ModelForm):
    class Meta:
        model = MonitorTarget
        fields = ("name", "url", "is_active", "check_interval")
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Masalan: Google"}),
            "url": forms.URLInput(attrs={"class": "form-control", "placeholder": "https://google.com"}),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "check_interval": forms.NumberInput(attrs={"class": "form-control", "min": 5}),
        }
        labels = {
            "name": "Target nomi",
            "url": "Website URL",
            "is_active": "Faol",
            "check_interval": "Tekshiruv intervali (sekund)",
        }
