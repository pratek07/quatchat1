# group_messaging/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid
import os


def attachment_upload_to(instance, filename):
    # uploads/group_<id>/<filename>
    return os.path.join("group_attachments", f"group_{instance.message.group_id}", filename)


class Group(models.Model):
    GROUP_TYPES = (
        ('public', 'Public'),
        ('private', 'Private'),
    )

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    group_type = models.CharField(max_length=20, choices=GROUP_TYPES, default='public')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.group_type})"


class GroupMembership(models.Model):
    ROLES = (
        ('admin', 'Admin'),
        ('member', 'Member'),
    )

    STATUSES = (
        ('active', 'Active'),
        ('pending', 'Pending'),
        ('left', 'Left'),
    )

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLES, default='member')
    status = models.CharField(max_length=20, choices=STATUSES, default='active')
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'group')

    def __str__(self):
        return f"{self.user.username} in {self.group.name} ({self.role}, {self.status})"


class GroupInvite(models.Model):
    STATUS_CHOICES = (
        ('sent', 'Sent'),
        ('accepted', 'Accepted'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled'),
    )

    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='invites')
    invited_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    token = models.CharField(max_length=200, unique=True, default=uuid.uuid4)
    status = models.CharField(max_length=50, choices=STATUS_CHOICES, default='sent')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    def is_valid(self):
        if self.status != "sent":
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    def __str__(self):
        return f"Invite {self.invited_user.email} -> {self.group.name}"


class Message(models.Model):
    group = models.ForeignKey(Group, on_delete=models.CASCADE, related_name='messages')
    sender = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # later: edited_at, is_deleted, reply_to, etc.

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f"Msg by {self.sender.username} in {self.group.name} @ {self.created_at}"


class Attachment(models.Model):
    ALLOWED_EXTENSIONS = [
        ".txt", ".docx", ".pdf", ".mp3", ".mp4", ".wav",
        ".png", ".jpeg", ".jpg", ".xlsx", ".csv",
    ]

    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=attachment_upload_to)
    original_name = models.CharField(max_length=255, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def extension(self):
        name = self.file.name
        _, ext = os.path.splitext(name)
        return ext.lower()

    def is_allowed(self):
        return self.extension() in self.ALLOWED_EXTENSIONS

    def __str__(self):
        return f"Attachment for msg {self.message_id}: {self.file.name}"
