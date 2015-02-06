from __future__ import absolute_import

from datetime import timedelta
from django.utils import timezone
from rest_framework.response import Response

from sentry.api.base import Endpoint
from sentry.api.permissions import assert_perm
from sentry.api.serializers import serialize
from sentry.models import Group, GroupStatus, Project, Team


class TeamGroupsNewEndpoint(Endpoint):
    def get(self, request, organization_slug, team_slug):
        """
        Return a list of the newest groups for a given team.

        The resulting query will find groups which have been seen since the
        cutoff date, and then sort those by score, returning the highest scoring
        groups first.
        """
        team = Team.objects.get(
            organization__slug=organization_slug,
            slug=team_slug,
        )

        assert_perm(team, request.user, request.auth)

        minutes = int(request.REQUEST.get('minutes', 15))
        limit = min(100, int(request.REQUEST.get('limit', 10)))

        project_list = Project.objects.get_for_user(user=request.user, team=team)

        project_dict = dict((p.id, p) for p in project_list)

        cutoff = timedelta(minutes=minutes)
        cutoff_dt = timezone.now() - cutoff

        group_list = list(Group.objects.filter(
            project__in=project_dict.keys(),
            status=GroupStatus.UNRESOLVED,
            active_at__gte=cutoff_dt,
        ).extra(
            select={'sort_value': 'score'},
        ).order_by('-score', '-first_seen')[:limit])

        for group in group_list:
            group._project_cache = project_dict.get(group.project_id)

        return Response(serialize(group_list, request.user))
