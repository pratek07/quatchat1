# group_messaging\forms.py
from django import forms
from django.contrib.auth import get_user_model

from .models import Group, Message

User = get_user_model()


class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'description', 'group_type']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Group name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'group_type': forms.Select(attrs={'class': 'form-select'}),
        }


class InviteForm(forms.Form):
    users = forms.ModelMultipleChoiceField(
        queryset=User.objects.none(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        current_user = kwargs.pop('current_user', None)
        super().__init__(*args, **kwargs)
        qs = User.objects.all()
        if current_user is not None:
            qs = qs.exclude(id=current_user.id)
        self.fields['users'].queryset = qs


# 🔧 Custom widget to allow multiple file selection
class MultiFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MessageForm(forms.ModelForm):
    attachments = forms.FileField(
        widget=MultiFileInput(attrs={'class': 'form-control'}),
        required=False
    )

    class Meta:
        model = Message
        fields = ['text']
        widgets = {
            'text': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Type a message...'
            }),
        }
