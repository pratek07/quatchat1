# group_messaging/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.mail import send_mail
from django.urls import reverse
from django.conf import settings

from .models import Group, GroupMembership, GroupInvite, Message, Attachment
from .forms import GroupForm, InviteForm, MessageForm


@login_required
def group_list(request):
    # Groups where the user is an active member
    memberships = GroupMembership.objects.filter(user=request.user, status='active').select_related('group')
    user_groups = [m.group for m in memberships]

    # Public groups (optional: not yet joined)
    public_groups = Group.objects.filter(group_type='public').exclude(memberships__user=request.user,
                                                                      memberships__status='active')

    return render(request, 'group_messaging/group_list.html', {
        'user_groups': user_groups,
        'public_groups': public_groups,
    })


@login_required
def group_create(request):
    if request.method == 'POST':
        form = GroupForm(request.POST)
        if form.is_valid():
            group = form.save(commit=False)
            group.created_by = request.user
            group.save()

            # creator becomes admin, active member
            GroupMembership.objects.create(
                user=request.user,
                group=group,
                role='admin',
                status='active'
            )

            messages.success(request, 'Group created successfully.')
            return redirect('group_messaging:group_detail', group_id=group.id)
    else:
        form = GroupForm()

    return render(request, 'group_messaging/group_create.html', {'form': form})


def _user_membership(user, group):
    try:
        return GroupMembership.objects.get(user=user, group=group)
    except GroupMembership.DoesNotExist:
        return None


@login_required
def group_detail(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    membership = _user_membership(request.user, group)

    if not membership or membership.status != 'active':
        messages.error(request, 'You are not a member of this group.')
        return redirect('group_messaging:group_list')

    if request.method == 'POST':
        form = MessageForm(request.POST, request.FILES)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.group = group
            msg.sender = request.user
            msg.save()

            # handle attachments
            files = request.FILES.getlist('attachments')
            for f in files:
                att = Attachment(message=msg, file=f, original_name=f.name)
                if att.is_allowed():
                    att.save()
                else:
                    # silently ignore disallowed or show message
                    messages.warning(request, f"File type not allowed: {f.name}")

            # later: broadcast via WebSockets
            return redirect('group_messaging:group_detail', group_id=group.id)
    else:
        form = MessageForm()

    messages_qs = group.messages.select_related('sender').prefetch_related('attachments')

    # For admin checks in template
    is_admin = membership.role == 'admin'

    return render(request, 'group_messaging/group_detail.html', {
        'group': group,
        'membership': membership,
        'is_admin': is_admin,
        'messages': messages_qs,
        'form': form,
    })


@login_required
def group_invite(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    membership = _user_membership(request.user, group)

    if not membership or membership.role != 'admin':
        messages.error(request, 'Only group admins can invite members.')
        return redirect('group_messaging:group_detail', group_id=group.id)

    if request.method == 'POST':
        form = InviteForm(request.POST, current_user=request.user)
        if form.is_valid():
            users = form.cleaned_data['users']
            for user in users:
                invite = GroupInvite.objects.create(
                    group=group,
                    invited_user=user,
                    # token auto generated
                    # expires_at optional: e.g., timezone.now()+timedelta(days=7)
                )
                join_url = request.build_absolute_uri(
                    reverse('group_messaging:join_group', args=[invite.token])
                )
                subject = f"You are invited to join group: {group.name}"
                message_body = (
                    f"Hi {user.username},\n\n"
                    f"You have been invited to join the group '{group.name}'.\n\n"
                    f"Click the link below to join:\n{join_url}\n\n"
                    f"Thanks."
                )
                send_mail(
                    subject,
                    message_body,
                    getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-reply@example.com'),
                    [user.email],
                    fail_silently=True,
                )
            messages.success(request, 'Invites sent successfully.')
            return redirect('group_messaging:group_detail', group_id=group.id)
    else:
        form = InviteForm(current_user=request.user)

    return render(request, 'group_messaging/group_invite.html', {
        'group': group,
        'form': form,
    })


@login_required
def join_group(request, token):
    invite = get_object_or_404(GroupInvite, token=token)
    if not invite.is_valid():
        messages.error(request, 'This invite link is invalid or expired.')
        return redirect('group_messaging:group_list')

    # Ensure the logged-in user matches invited user
    if invite.invited_user != request.user:
        messages.error(request, 'This invite is not for your account.')
        return redirect('group_messaging:group_list')

    group = invite.group

    membership = _user_membership(request.user, group)
    if membership and membership.status == 'active':
        messages.info(request, 'You are already a member of this group.')
        return redirect('group_messaging:group_detail', group_id=group.id)

    if group.group_type == 'public':
        # directly activate membership
        if membership:
            membership.status = 'active'
            membership.save()
        else:
            GroupMembership.objects.create(
                user=request.user,
                group=group,
                role='member',
                status='active'
            )
        invite.status = 'accepted'
        invite.save()
        messages.success(request, f'You have joined the group {group.name}.')
        return redirect('group_messaging:group_detail', group_id=group.id)

    else:
        # private: mark membership as pending; admin will approve
        if membership:
            membership.status = 'pending'
            membership.save()
        else:
            GroupMembership.objects.create(
                user=request.user,
                group=group,
                role='member',
                status='pending'
            )
        invite.status = 'accepted'
        invite.save()
        messages.info(request, f'Your request to join {group.name} is pending admin approval.')
        return redirect('group_messaging:group_list')


@login_required
def leave_group(request, group_id):
    group = get_object_or_404(Group, id=group_id)
    membership = _user_membership(request.user, group)

    if not membership or membership.status != 'active':
        messages.error(request, 'You are not an active member of this group.')
        return redirect('group_messaging:group_list')

    # optionally prevent last admin from leaving if others still there
    if membership.role == 'admin':
        other_admin_exists = GroupMembership.objects.filter(
            group=group, role='admin', status='active'
        ).exclude(user=request.user).exists()
        if not other_admin_exists:
            messages.error(request, 'You are the only admin. Assign another admin before leaving.')
            return redirect('group_messaging:group_detail', group_id=group.id)

    membership.status = 'left'
    membership.save()
    messages.success(request, f'You left the group {group.name}.')
    return redirect('group_messaging:group_list')
