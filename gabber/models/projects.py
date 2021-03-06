# -*- coding: utf-8 -*-
"""
???
"""
from .. import db
from flask_sqlalchemy import BaseQuery

codes_for_connections = db.Table(
    'codes_for_connections',
    db.Column('connection_id', db.Integer, db.ForeignKey('connection.id')),
    db.Column('code_id', db.Integer, db.ForeignKey('code.id'))
)


class QueryWithSoftDelete(BaseQuery):
    """
    Prepends is_active to the query object SQL statement.

    Note: this is modified version of Miguel Grinberg's SoftDelete: https://goo.gl/QFJK1c
    """
    _with_deleted = False

    def __new__(cls, *args, **kwargs):
        """
        The query object is created and modified here as in the init it is immutable.
        Being able to create a new instance of the query also enables overriding Object.query.get()
        """
        obj = super(QueryWithSoftDelete, cls).__new__(cls)
        # Optionally reset the query, e.g. to get all data including deleted.
        obj._with_deleted = kwargs.pop('_with_deleted', False)
        if len(args) > 0:
            super(QueryWithSoftDelete, obj).__init__(*args, **kwargs)
            return obj.filter_by(is_active=True) if not obj._with_deleted else obj
        return obj

    def __init__(self, *args, **kwargs):
        pass

    def with_deleted(self):
        """
        Lets QueryObject.query.with_deleted() be used to retrieve all the objects,
        including those that have been deleted.
        """
        return self.__class__(db.class_mapper(self._mapper_zero().class_),
                              session=db.session(), _with_deleted=True)

    def _get(self, *args, **kwargs):
        """
        This calls the original query.get function from the base class
        """
        return super(QueryWithSoftDelete, self).get(*args, **kwargs)

    def get(self, *args, **kwargs):
        """
        If QueryObject (say Project).query.get() is called it does not like the
        filter clause pre-loaded, so this workaround calls get without it.
        """
        obj = self.with_deleted()._get(*args, **kwargs)
        return obj if obj is None or self._with_deleted or obj.is_active else None


class Membership(db.Model):
    """
    Holds the user membership for projects and the users role in this project.

    Note: an association object is used to hold the role ontop of the many-to-many relationship(s).

    Relationships:
        many-to-many: a user can be a member of many projects
        many-to-many: a project can have many members
        one-to-one: each membership must have one role
    """
    id = db.Column(db.Integer, autoincrement=True, index=True, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))
    # Used to determine if a user has confirmed their membership
    confirmed = db.Column(db.Boolean, default=False)
    # Should someone leave a project, we make deactivate their membership for posterity.
    deactivated = db.Column(db.Boolean, default=False)
    # Determines (1) when membership was sent, and (2) for how long they were a member.
    date_sent = db.Column(db.DateTime, default=db.func.now())
    date_accepted = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    user = db.relationship("User", back_populates="member_of")
    project = db.relationship("Project", back_populates="members")
    role = db.relationship("Roles", backref=db.backref("member_of", uselist=False))

    def __init__(self, uid, pid, rid, confirmed=False):
        self.user_id = uid
        self.project_id = pid
        self.role_id = rid
        self.confirmed = confirmed

    @staticmethod
    def join_project(user_id, project_id):
        membership = Membership(uid=user_id, pid=project_id, rid=Roles.user_role(), confirmed=True)
        db.session.add(membership)
        db.session.commit()
        return membership

    @staticmethod
    def leave_project(user_id, project_id):
        # Given we store all the history of project joins/leaves,
        # when a user requests to leave only their most recent record is presented
        membership = Membership.query.filter_by(
            user_id=user_id,
            project_id=project_id,
            deactivated=False
        ).order_by(Membership.id.desc()).first()
        membership.deactivated = True
        db.session.commit()
        return membership


class Roles(db.Model):
    """
    The roles that can be assigned to a user, and are used to support access control on projects.

    Backrefs:
        one-to-many: a member of a project has one role, though a member can be part of many projects.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)

    @staticmethod
    def user_role():
        return Roles.query.filter_by(name='participant').first().id


class Organisation(db.Model):
    """
    An organisation associated with a specific project, which is used to add
    further context to who has created the project.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(256))
    description = db.Column(db.String(1028))
    projects = db.relationship('Project', lazy='dynamic')


class ProjectLanguage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    lang_id = db.Column(db.Integer, db.ForeignKey('supported_language.id'))

    description = db.Column(db.String(768))
    title = db.Column(db.String(64))
    slug = db.Column(db.String(256), unique=True, index=True)

    def __init__(self, pid, lid, description, title):
        from slugify import slugify
        self.project_id = pid
        self.lang_id = lid
        self.description = description
        self.title = title
        self.slug = slugify(title)


class TopicLanguage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), nullable=True)
    lang_id = db.Column(db.Integer, db.ForeignKey('supported_language.id'))
    text = db.Column(db.String(260))
    is_active = db.Column(db.SmallInteger, default=1)


class Project(db.Model):
    """
    A project is the overarching theme for an interview session

    Backrefs:
        Can refer to associated prompts with 'prompts'
        Can refer to 'members' of a project with 'members'

    Relationships:
        one-to-many: a project can have many prompts
        one-to-many: a project can have many codebooks
        many-to-many: a project can have many members
    """

    query_class = QueryWithSoftDelete

    id = db.Column(db.Integer, primary_key=True)
    image = db.Column(db.String(64))
    # Used as a 'soft-delete' to preserve prompt-content for viewing
    is_active = db.Column(db.Boolean, default=True)
    # Is the project public or private? True (1) is public.
    is_public = db.Column(db.Boolean, default=True)

    # Defaults to individual unless told otherwise
    organisation = db.Column(db.Integer, db.ForeignKey('organisation.id'), default=0)
    creator = db.Column(db.Integer, db.ForeignKey('user.id'))
    default_lang = db.Column(db.Integer, db.ForeignKey('supported_language.id'))

    content = db.relationship('ProjectLanguage', backref='content', lazy='dynamic')
    topics = db.relationship('TopicLanguage', backref='topics', lazy='dynamic')
    codebook = db.relationship('Codebook', backref='project', lazy='dynamic')
    sessions = db.relationship('InterviewSession', backref='sessions', uselist=True)

    members = db.relationship('Membership', back_populates='project',
                              primaryjoin='and_(Project.id==Membership.project_id, Membership.deactivated == False)')

    created_on = db.Column(db.DateTime, default=db.func.now())
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class InterviewSession(db.Model):
    """
    An interview session between participants for a set of prompts

    Relationships:
        one-to-many: an interview must be consented by many participants
        one-to-many: many participants can be involved in one interview
        one-to-many: an interview can have many connections
    """
    id = db.Column(db.String(260), primary_key=True)
    lang_id = db.Column(db.Integer)
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    created_on = db.Column(db.DateTime)

    prompts = db.relationship('InterviewPrompts', backref='interview', lazy='joined')
    consents = db.relationship('SessionConsent', backref='interview', lazy='dynamic')
    participants = db.relationship('InterviewParticipants', backref='interview', lazy='joined')
    connections = db.relationship(
        'Connection',
        backref='interview',
        lazy='joined',
        primaryjoin="and_(InterviewSession.id==Connection.session_id, Connection.is_active)"
    )

    def consented(self, project_is_public):
        return self.all_members_public_consented() if project_is_public else self.all_members_private_consented()

    @staticmethod
    def all_consented_sessions_by_project(project, is_creator_researcher_or_admin=False, user_sessions=False):
        sessions = InterviewSession.query.filter_by(project_id=project.id).all()

        # Project creators and admins can view all sessions.
        if is_creator_researcher_or_admin:
            return sessions

        if project.is_public:
            data = [session for session in sessions
                    if session.all_members_public_consented() and not session.embargoed()]
        else:
            data = [session for session in sessions
                    if session.all_members_private_consented() and not session.embargoed()]

        # Users can always access their own conversations, hence not necessary to check for embargo
        if user_sessions:
            users_sessions = [session for session in sessions if session.user_is_participant(user_sessions)]
            return set(users_sessions + data)
        return data

    def embargoed(self):
        from datetime import datetime, timedelta
        return datetime.now() < (self.created_on + timedelta(hours=24))

    def all_members_public_consented(self):
        """
        If all participants provide consent, i.e. the set of consents only contains public.
        """
        unique_consents = set([str(i.type) for i in self.consents])
        # If only public is within the set, then all participants are in agreement to making the recording public.
        return True if 'public' in unique_consents and len(unique_consents) == 1 else False

    def all_members_private_consented(self):
        """
        If at least one participant does not want to share the Gabber (private), then its not for private.
        """
        unique_consents = set([str(i.type) for i in self.consents])
        return True if 'private' not in unique_consents else False

    def user_is_participant(self, user):
        return True if user.id in [p.user_id for p in self.participants] else False

    def generate_signed_url_for_recording(self):
        """
        Generates a timed (two-hour) URL to access the recording of this interview session

        :return: signed URL for the audio recording of the interview
        """
        from ..utils import amazon
        return amazon.signed_url(self.project_id, self.id)

    @staticmethod
    def session_url(pid, sid):
        from flask import current_app as app
        return '{0}/projects/{1}/conversations/{2}'.format(app.config['WEB_HOST'], pid, sid)

    @staticmethod
    def email_commentor(comment_creator, pid, sid):
        from ..utils.mail import MailClient
        send_mail = MailClient(comment_creator.id)
        send_mail.comment_root_response(comment_creator, pid, sid)

    @staticmethod
    def email_participants(creator, sid):
        from ..utils.mail import MailClient
        from ..models.user import User
        session = InterviewSession.query.get(sid)

        # notify all participants, except the one who created the comment if they did
        for participant in [p for p in session.participants if p.user_id != creator.id]:
            user = User.query.get(participant.user_id)
            send_mail = MailClient(user.lang)
            send_mail.comment_nested_response(user, session.project_id, sid)


class InterviewPrompts(db.Model):
    """
    These are the annotations created during the capture of an interview, which differ
    from an annotation below as they are used for structural representation ontop of the recording.

    Backref:
        Can refer to associated interview with 'interview'
    """
    id = db.Column(db.Integer, primary_key=True)
    prompt_id = db.Column(db.Integer, db.ForeignKey('topic_language.id'))
    interview_id = db.Column(db.String(260), db.ForeignKey('interview_session.id'))
    # Where in the structural annotation starts and ends
    start_interval = db.Column(db.Integer)
    end_interval = db.Column(db.Integer, default=0)
    # Simplifies access to topic.text
    topic = db.relationship("TopicLanguage", lazy='joined')


class InterviewParticipants(db.Model):
    """
    The individual who was part of an interview

    Backref:
        Can refer to associated interview with 'interview'
    """
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    interview_id = db.Column(db.String(260), db.ForeignKey('interview_session.id'))
    # 0: private, 1: public, 2: delete
    consent_type = db.Column(db.Integer, default=0)
    # 0: interviewee, 1: interviewer
    # Although this could be inferred through interview.creator, this simplifies queries
    role = db.Column(db.Boolean, default=False)

    user = db.relationship("User", back_populates="participant_of")

    def __init__(self, user_id, session_id, role):
        self.user_id = user_id
        self.interview_id = session_id
        self.role = role


class Connection(db.Model):
    """
    A connection (reflective perspective or opinion) from a user on a segment of an interview.

    Relationships:
        A connection can be associated with many codes.

    Backrefs:
        Can refer to its creator with 'user'
        Can refer to its parent interview with 'interview'
    """
    query_class = QueryWithSoftDelete

    # TODO: this should be renamed to UserAnnotation as connection is outdated
    id = db.Column(db.Integer, primary_key=True)
    # Although many are chosen, a general justification by the user must be provided.
    content = db.Column(db.String(1024))
    # Where in the interview this connection starts and ends
    start_interval = db.Column(db.Integer)
    end_interval = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    # A connection can be associated with many codes
    tags = db.relationship("Code", secondary=codes_for_connections, backref="connections")
    comments = db.relationship(
        'ConnectionComments',
        backref='connection',
        lazy='joined',
        primaryjoin='and_(Connection.id==ConnectionComments.connection_id, ConnectionComments.parent_id == None)'
    )

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    session_id = db.Column(db.String(260), db.ForeignKey('interview_session.id'))

    created_on = db.Column(db.DateTime, default=db.func.now())
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())


class ConnectionComments(db.Model):
    """
    Comments can be made on connections (where parent is 0) and on themselves.

    Backrefs:
        A comment can refer to its creator with 'user'
        A comment can refer to the connection its associated with via 'connection'
    """
    __tablename__ = 'connection_comments'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.String(1024), default=None)

    is_active = db.Column(db.Boolean, default=True)

    # If this is NULL, then it is a response to the root, e.g. the annotation itself.
    parent_id = db.Column(db.Integer, db.ForeignKey('connection_comments.id'), nullable=True)
    replies = db.relationship('ConnectionComments', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    # Who created it and for what purpose?
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    connection_id = db.Column(db.Integer, db.ForeignKey('connection.id'))

    created_on = db.Column(db.DateTime, default=db.func.now())
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, content, pid, uid, aid):
        self.content = content
        self.parent_id = pid
        self.user_id = uid
        self.connection_id = aid


class Codebook(db.Model):
    """
    Holds a set of codes related to a project; acts as qualitative codebook.

    Backrefs:
        Can refer to its associated project with 'project'

    Relationships:
        one-to-many: a codebook can have many codes
    """
    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    # Used to differentiate and support multiple codebooks for the same project
    tags = db.relationship('Code', backref="codebook", lazy='dynamic')
    name = db.Column(db.String(40))


class Code(db.Model):
    """
    Holds a textual "Code" for a specific Codebook.

    Note: this approach is not ideal as we would have duplicate codes across books.

    Backref:
        Can refer to associated codebook with 'codebook'
    """
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(64))
    is_active = db.Column(db.SmallInteger, default=1)
    codebook_id = db.Column(db.Integer, db.ForeignKey('codebook.id'))
