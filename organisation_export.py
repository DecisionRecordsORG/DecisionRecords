"""
The export of a whole organisation's content, for its administrators.

`build_organisation_export(tenant, actor)` returns the bytes of one ZIP file:

    README.txt        what each file is, when it was made, by whom, what is left out
    decisions.json    every decision that has not been deleted, with its history,
                      comments, links to other decisions and spaces
    decisions/*.md    one readable Markdown file per decision, under the
                      headings of the organisation's decision template
    spaces.json       the organisation's spaces and which decisions are in each
    templates.json    the decision template in use and the relationship types
    members.json      name, email address, role and joining date of each member
    audit-log.json    the organisation's audit log

What it never contains: password hashes, passkey key material, API keys or
their hashes, OAuth tokens, set-up or verification links, SSO or SMTP secrets,
sign-in history (other people's sign-ins are theirs), server logs, deleted
decisions or removed comments, and anything of another organisation. Every
query below is scoped to the one organisation: decisions by its domain (as
every decision route of the app does), everything else by its id or through
those decisions.

The content is built in memory. Before anything is built, the size of the
stored text is added up in the database; above MAX_EXPORT_BYTES the export is
refused with ExportTooLarge and nothing is read. The same limit is checked
again on the actual files as they are written, so the estimate cannot be
fooled by text the estimate does not count.
"""

import io
import json
import re
import unicodedata
import zipfile
from datetime import datetime, timezone

import sqlalchemy as sa
import sqlalchemy.orm  # noqa: F401  (sa.orm.selectinload)

from decision_relationships import get_effective_relationship_catalog
from decision_templates import build_tenant_template_payload, get_template, SECTION_KEYS
from models import (
    db, AuditLog, AuthConfig, ArchitectureDecision, DecisionComment, DecisionHistory,
    DecisionRelationship, DecisionSpace, Space, TenantMembership, TenantSettings, User,
    get_tenant_relationship_catalog, get_tenant_relationship_config,
)

# Most uncompressed content one export may hold: 100 MB. An organisation of 25
# people with thousands of decisions, their history and comments is a few MB.
# Above the limit the export is refused with a message saying to contact
# support, rather than building a file the server and the browser struggle with.
MAX_EXPORT_BYTES = 100 * 1024 * 1024

# At most this many exports of one organisation within an hour, whoever asks.
EXPORTS_PER_HOUR = 10

ACTION_ORGANISATION_DATA_EXPORTED = 'organisation_data_exported'

FILES = ('README.txt', 'decisions.json', 'spaces.json', 'templates.json', 'members.json', 'audit-log.json')

# Keys of an audit entry's details that are never copied into the export,
# whatever wrote them. No current entry has one; this keeps a future one out.
_SECRET_KEY = re.compile(r'(secret|token|password|passw|hash|api_?key|credential|private)', re.IGNORECASE)


class ExportTooLarge(Exception):
    """The organisation's content is larger than MAX_EXPORT_BYTES."""

    def __init__(self, size):
        super().__init__(f'Export would be {size} bytes, more than {MAX_EXPORT_BYTES}')
        self.size = size


def _iso(value):
    return value.isoformat() if value else None


def _enum(value):
    return getattr(value, 'value', value)


def _person(user):
    """{id, name} of a person, or None. Never their address or anything else."""
    if user is None:
        return None
    return {'id': user.id, 'name': user.get_full_name().strip() or (user.email or '').split('@')[0]}


def _scrub(value):
    """A copy of audit details without any key that looks like a secret."""
    if isinstance(value, dict):
        return {key: _scrub(item) for key, item in value.items() if not _SECRET_KEY.search(str(key))}
    if isinstance(value, list):
        return [_scrub(item) for item in value]
    return value


def slugify(text, max_length=60):
    """Lower-case ASCII letters, digits and hyphens, for a file name."""
    ascii_text = unicodedata.normalize('NFKD', text or '').encode('ascii', 'ignore').decode('ascii')
    slug = re.sub(r'[^a-z0-9]+', '-', ascii_text.lower()).strip('-')
    return slug[:max_length].rstrip('-') or 'untitled'


def _decision_scope(tenant):
    return sa.and_(ArchitectureDecision.domain == tenant.domain, ArchitectureDecision.deleted_at.is_(None))


def estimate_size(tenant):
    """Bytes of the stored text the export would copy, added up in the database."""
    def total(*columns, filters):
        query = db.session.query(*[sa.func.coalesce(sa.func.sum(sa.func.length(column)), 0) for column in columns])
        for condition in filters:
            query = query.filter(condition)
        return sum(int(value or 0) for value in query.one())

    decision_ids = db.session.query(ArchitectureDecision.id).filter(_decision_scope(tenant))
    size = total(ArchitectureDecision.title, ArchitectureDecision.context, ArchitectureDecision.decision,
                 ArchitectureDecision.consequences, filters=[_decision_scope(tenant)])
    size += total(DecisionHistory.title, DecisionHistory.context, DecisionHistory.decision_text,
                  DecisionHistory.consequences, filters=[DecisionHistory.decision_id.in_(decision_ids)])
    size += total(DecisionComment.body, filters=[DecisionComment.decision_id.in_(decision_ids),
                                                 DecisionComment.tenant_id == tenant.id,
                                                 DecisionComment.deleted_at.is_(None)])
    # Each decision is written twice (JSON and Markdown)
    return size * 2


class _SizedZip:
    """A ZIP in memory that refuses to grow past MAX_EXPORT_BYTES of content."""

    def __init__(self):
        self.buffer = io.BytesIO()
        self.zip = zipfile.ZipFile(self.buffer, 'w', zipfile.ZIP_DEFLATED)
        self.size = 0
        self.names = []

    def write(self, name, text):
        data = text.encode('utf-8')
        self.size += len(data)
        if self.size > MAX_EXPORT_BYTES:
            raise ExportTooLarge(self.size)
        self.zip.writestr(name, data)
        self.names.append(name)

    def write_json(self, name, value):
        self.write(name, json.dumps(value, indent=2, ensure_ascii=False) + '\n')

    def close(self):
        self.zip.close()
        return self.buffer.getvalue()


def _display_prefix(tenant):
    """The prefix of display ids, as ArchitectureDecision.get_display_id finds it."""
    auth_config = AuthConfig.query.filter_by(domain=tenant.domain).first()
    if auth_config and auth_config.tenant_prefix:
        return auth_config.tenant_prefix
    return 'ADR'


def _display_id(prefix, decision):
    if decision.decision_number is None:
        return None
    return f'{prefix}-{decision.decision_number:03d}'


def _users_by_id(user_ids):
    user_ids = {user_id for user_id in user_ids if user_id is not None}
    if not user_ids:
        return {}
    return {user.id: user for user in User.query.filter(User.id.in_(user_ids)).all()}


def _collect(tenant):
    """Everything the export holds, as plain data. Reads only."""
    settings = TenantSettings.query.filter_by(tenant_id=tenant.id).first()
    template_id = settings.decision_template_id if settings else None
    template = get_template(template_id)
    prefix = _display_prefix(tenant)

    decisions = ArchitectureDecision.query.filter(_decision_scope(tenant)).options(
        sa.orm.selectinload(ArchitectureDecision.infrastructure)).order_by(
        ArchitectureDecision.decision_number.is_(None), ArchitectureDecision.decision_number,
        ArchitectureDecision.id).all()
    by_id = {decision.id: decision for decision in decisions}
    ids = list(by_id)

    history = DecisionHistory.query.filter(DecisionHistory.decision_id.in_(ids)).order_by(
        DecisionHistory.changed_at, DecisionHistory.id).all() if ids else []
    comments = DecisionComment.query.filter(
        DecisionComment.decision_id.in_(ids), DecisionComment.tenant_id == tenant.id,
        DecisionComment.deleted_at.is_(None)).order_by(
        DecisionComment.created_at, DecisionComment.id).all() if ids else []
    # A link counts only when both ends are decisions of this organisation
    # that have not been deleted
    links = DecisionRelationship.query.filter(
        DecisionRelationship.tenant_id == tenant.id, DecisionRelationship.deleted_at.is_(None),
        DecisionRelationship.source_decision_id.in_(ids), DecisionRelationship.target_decision_id.in_(ids),
    ).order_by(DecisionRelationship.id).all() if ids else []
    spaces = Space.query.filter_by(tenant_id=tenant.id).order_by(Space.is_default.desc(), Space.id).all()
    space_ids = [space.id for space in spaces]
    space_links = DecisionSpace.query.filter(
        DecisionSpace.decision_id.in_(ids), DecisionSpace.space_id.in_(space_ids)).order_by(
        DecisionSpace.id).all() if ids and space_ids else []

    people = _users_by_id(
        [d.created_by_id for d in decisions] + [d.updated_by_id for d in decisions] +
        [d.owner_id for d in decisions] + [h.changed_by_id for h in history] +
        [c.user_id for c in comments] + [s.created_by_id for s in spaces])

    type_map = get_effective_relationship_catalog(get_tenant_relationship_config(tenant.id))['type_map']
    space_by_id = {space.id: space for space in spaces}

    entries = {decision.id: {
        'id': decision.id,
        'display_id': _display_id(prefix, decision),
        'decision_number': decision.decision_number,
        'title': decision.title,
        'status': decision.status,
        'decision_type': decision.decision_type,
        'context': decision.context,
        'decision': decision.decision,
        'consequences': decision.consequences,
        'created_at': _iso(decision.created_at),
        'updated_at': _iso(decision.updated_at),
        'created_by': _person(people.get(decision.created_by_id)),
        'updated_by': _person(people.get(decision.updated_by_id)),
        'owner': _person(people.get(decision.owner_id)),
        # Someone named as owner who has no account here
        'owner_email': decision.owner_email if decision.owner_id is None else None,
        'spaces': [],
        'infrastructure': [{'id': item.id, 'name': item.name, 'type': item.type}
                           for item in decision.infrastructure if item.domain == tenant.domain],
        'relationships': [],
        'comments': [],
        'history': [],
    } for decision in decisions}

    for link in space_links:
        space = space_by_id[link.space_id]
        entries[link.decision_id]['spaces'].append({'id': space.id, 'name': space.name})

    for link in links:
        config = type_map.get(link.relationship_type) or {}
        for decision_id, other_id, direction in (
                (link.source_decision_id, link.target_decision_id, 'outgoing'),
                (link.target_decision_id, link.source_decision_id, 'incoming')):
            label = config.get('label', link.relationship_type)
            if direction == 'incoming':
                label = config.get('inverse_label') or label
            other = by_id[other_id]
            entries[decision_id]['relationships'].append({
                'id': link.id,
                'direction': direction,
                'relationship_type': link.relationship_type,
                'label': label,
                'notes': link.notes,
                'decision': {'id': other.id, 'display_id': _display_id(prefix, other), 'title': other.title},
                'created_at': _iso(link.created_at),
            })

    for comment in comments:
        entries[comment.decision_id]['comments'].append({
            'id': comment.id,
            'author': _person(people.get(comment.user_id)),
            # The name shown for a comment written without an account here (for example from Slack)
            'author_display': comment.author_display if comment.user_id is None else None,
            'body': comment.body,
            'created_at': _iso(comment.created_at),
            'updated_at': _iso(comment.updated_at),
        })

    for change in history:
        entries[change.decision_id]['history'].append({
            'changed_at': _iso(change.changed_at),
            'changed_by': _person(people.get(change.changed_by_id)),
            'change_reason': change.change_reason,
            'title': change.title,
            'status': change.status,
            'decision_type': change.decision_type,
            'context': change.context,
            'decision': change.decision_text,
            'consequences': change.consequences,
        })

    decisions_by_space = {}
    for link in space_links:
        decisions_by_space.setdefault(link.space_id, []).append(link.decision_id)
    space_entries = [{
        'id': space.id,
        'name': space.name,
        'description': space.description,
        'is_default': bool(space.is_default),
        'visibility': _enum(space.visibility_policy),
        'created_by': _person(people.get(space.created_by_id)),
        'created_at': _iso(space.created_at),
        'decision_ids': decisions_by_space.get(space.id, []),
    } for space in spaces]

    template_payload = build_tenant_template_payload(template_id, tenant.industry)
    catalog = get_tenant_relationship_catalog(tenant.id)
    templates = {
        'decision_template': {
            'id': template_payload['template_id'],
            'chosen_by_organisation': template_payload['template_chosen'],
            'industry': template_payload['industry'],
            'industry_title': template_payload['industry_title'],
            'template': template_payload['template'],
        },
        'relationship_types': catalog['types'],
        'relationship_packs': catalog['packs'],
    }

    return {
        'template': template,
        'decisions': [entries[decision.id] for decision in decisions],
        'spaces': space_entries,
        'templates': templates,
        'members': _members(tenant),
        'audit_log': _audit_log(tenant),
    }


def _members(tenant):
    """Name, address, role and joining date: what administrators see in Settings, Users."""
    memberships = {membership.user_id: membership
                   for membership in TenantMembership.query.filter_by(tenant_id=tenant.id).all()}
    users = User.query.filter(
        sa.or_(User.sso_domain == tenant.domain, User.id.in_(list(memberships) or [-1])),
        User.deleted_at.is_(None), User.is_anonymized.isnot(True),
    ).order_by(User.id).all()
    members = []
    for user in users:
        membership = memberships.get(user.id)
        if membership is None and user.sso_domain != tenant.domain:
            continue
        if membership is not None:
            role = _enum(membership.global_role)
            joined = membership.joined_at or user.created_at
        else:
            # An older account without a membership row: its role is the legacy flag
            role = 'admin' if user.is_admin else 'user'
            joined = user.created_at
        members.append({
            'id': user.id,
            'name': user.get_full_name().strip() or None,
            'email': user.email,
            'role': role,
            'joined_at': _iso(joined),
        })
    return members


def _audit_log(tenant):
    entries = AuditLog.query.filter_by(tenant_id=tenant.id).order_by(AuditLog.created_at, AuditLog.id).all()
    actors = _users_by_id([entry.actor_user_id for entry in entries])
    return [{
        'id': entry.id,
        'action': entry.action_type,
        'actor': _person(actors.get(entry.actor_user_id)),
        'target_entity': entry.target_entity,
        'target_id': entry.target_id,
        'details': _scrub(entry.details),
        'created_at': _iso(entry.created_at),
    } for entry in entries]


def _person_line(person):
    return person['name'] if person else 'unknown'


def decision_markdown(entry, template):
    """One decision as Markdown, under the headings of the organisation's template."""
    heading = f"{entry['display_id']}: {entry['title']}" if entry['display_id'] else entry['title']
    lines = [f'# {heading}', '']
    facts = [('Status', entry['status'])]
    if entry['decision_type']:
        facts.append(('Type', entry['decision_type']))
    if entry['owner']:
        facts.append(('Owner', entry['owner']['name']))
    elif entry['owner_email']:
        facts.append(('Owner', entry['owner_email']))
    facts.append(('Created', f"{entry['created_at']} by {_person_line(entry['created_by'])}"))
    facts.append(('Last updated', entry['updated_at']))
    if entry['spaces']:
        facts.append(('Spaces', ', '.join(space['name'] for space in entry['spaces'])))
    lines += [f'- {label}: {value}' for label, value in facts]

    for key in SECTION_KEYS:
        lines += ['', f"## {template['sections'][key]['label']}", '', (entry[key] or '').strip() or '_Empty_']

    if entry['relationships']:
        lines += ['', '## Related decisions', '']
        for link in entry['relationships']:
            other = link['decision']
            name = f"{other['display_id']}: {other['title']}" if other['display_id'] else other['title']
            note = f" ({link['notes']})" if link['notes'] else ''
            lines.append(f"- {link['label']} {name}{note}")

    if entry['infrastructure']:
        lines += ['', '## Infrastructure', '']
        lines += [f"- {item['name']} ({item['type']})" for item in entry['infrastructure']]

    if entry['comments']:
        lines += ['', '## Comments']
        for comment in entry['comments']:
            author = comment['author']['name'] if comment['author'] else (comment['author_display'] or 'unknown')
            lines += ['', f"**{author}**, {comment['created_at']}:", '', comment['body'].strip()]

    if entry['history']:
        lines += ['', '## History', '']
        for change in entry['history']:
            reason = f": {change['change_reason']}" if change['change_reason'] else ''
            lines.append(f"- {change['changed_at']}, {_person_line(change['changed_by'])}, "
                         f"status {change['status']}{reason}")

    return '\n'.join(lines) + '\n'


def markdown_file_name(entry, taken):
    stem = re.sub(r'[^A-Za-z0-9-]+', '-', entry['display_id'] or f"decision-{entry['id']}").strip('-')
    name = f"decisions/{stem}-{slugify(entry['title'])}.md"
    if name in taken:
        name = f"decisions/{stem}-{slugify(entry['title'])}-{entry['id']}.md"
    taken.add(name)
    return name


def readme_text(tenant, actor, made_at, counts):
    name = tenant.name or tenant.domain
    return f"""Decision Records: export of the organisation {name} ({tenant.domain})

Made on {made_at} (UTC) by {actor.get_full_name().strip() or actor.email} ({actor.email}),
an administrator of the organisation, from Organisation settings.

What each file is
-----------------
decisions.json   Every decision that has not been deleted ({counts['decisions']}), with
                 its display id, status, type, the three text sections, owner and
                 creator (id and name), dates, spaces, links to other decisions,
                 comments ({counts['comments']}) and its history of changes.
decisions/       The same decisions, one Markdown file each, under the headings of
                 the organisation's decision template.
spaces.json      The organisation's spaces ({counts['spaces']}) and the decisions in each.
templates.json   The decision template in use, its headings and decision types, and
                 the relationship types decisions can be linked with.
members.json     Each member ({counts['members']}): name, email address, role and the
                 date they joined.
audit-log.json   The organisation's audit log ({counts['audit_log']} entries): who did
                 what, and when.

Dates are in UTC (ISO 8601). JSON files are UTF-8.

What is not included
--------------------
- Decisions that were deleted, and comments that were removed.
- Sign-in history: each person's sign-ins are theirs. Each person can export
  their own data, sign-ins included, from their profile (Privacy & Data).
- Passwords, passkeys, API keys, tokens of connected applications, set-up and
  verification links, and the secrets of the organisation's SSO, email,
  Slack and Teams settings.
- Server logs.
- Anything of another organisation.
"""


def build_organisation_export(tenant, actor, now=None):
    """The ZIP file of `tenant`'s content as bytes, and a summary. Reads only.

    Raises ExportTooLarge, before reading the content when the stored text is
    already too large, or while writing when the files turn out to be.
    """
    estimate = estimate_size(tenant)
    if estimate > MAX_EXPORT_BYTES:
        raise ExportTooLarge(estimate)

    made_at = (now or datetime.now(timezone.utc)).replace(microsecond=0).isoformat()
    data = _collect(tenant)
    counts = {
        'decisions': len(data['decisions']),
        'comments': sum(len(entry['comments']) for entry in data['decisions']),
        'spaces': len(data['spaces']),
        'members': len(data['members']),
        'audit_log': len(data['audit_log']),
    }

    archive = _SizedZip()
    archive.write('README.txt', readme_text(tenant, actor, made_at, counts))

    taken = set()
    markdown = []
    for entry in data['decisions']:
        entry['markdown_file'] = markdown_file_name(entry, taken)
        markdown.append((entry['markdown_file'], decision_markdown(entry, data['template'])))

    organisation = {'name': tenant.name or tenant.domain, 'domain': tenant.domain}
    archive.write_json('decisions.json', {
        'organisation': organisation, 'exported_at': made_at, 'decisions': data['decisions']})
    for name, text in markdown:
        archive.write(name, text)
    archive.write_json('spaces.json', {'organisation': organisation, 'spaces': data['spaces']})
    archive.write_json('templates.json', {'organisation': organisation, **data['templates']})
    archive.write_json('members.json', {'organisation': organisation, 'members': data['members']})
    archive.write_json('audit-log.json', {'organisation': organisation, 'entries': data['audit_log']})

    summary = dict(counts, bytes=archive.size, files=len(archive.names))
    return archive.close(), summary
