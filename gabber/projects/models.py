# -*- coding: utf-8 -*-
"""
???
"""
from gabber import db

codes_for_connections = db.Table(
    'codes_for_connections',
    db.Column('connection_id', db.Integer, db.ForeignKey('connection.id')),
    db.Column('code_id', db.Integer, db.ForeignKey('code.id'))
)


class Membership(db.Model):
    """
    Holds the user membership for projects and the users role in this project.

    Note: an association object is used to hold the role ontop of the many-to-many relationship(s).

    Relationships:
        many-to-many: a user can be a member of many projects
        many-to-many: a project can have many members
        one-to-one: each membership must have one role
    """
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'))

    user = db.relationship("User", back_populates="member_of")
    project = db.relationship("Project", back_populates="members")
    role = db.relationship("Roles", backref=db.backref("member_of", uselist=False))

    def __init__(self, uid, pid, rid):
        self.user_id = uid
        self.project_id = pid
        self.role_id = rid


class Roles(db.Model):
    """
    The roles that can be assigned to a user, and are used to support access control on projects.

    Backrefs:
        one-to-many: a member of a project has one role, though a member can be part of many projects.
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)


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
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(64))
    # URL-friendly representation of the title
    slug = db.Column(db.String(256), unique=True, index=True)
    description = db.Column(db.String(256))

    creator = db.Column(db.Integer, db.ForeignKey('user.id'))
    # Is the project public or private? True (1) is public.
    isProjectPublic = db.Column(db.Boolean, default=1)
    # Should consent (via email) be enabled for this project?
    isConsentEnabled = db.Column(db.Boolean, default=0)

    codebook = db.relationship('Codebook', backref='project', lazy='dynamic')
    prompts = db.relationship('ProjectPrompt', backref='project', lazy='dynamic')
    members = db.relationship("Membership", back_populates="project")

    created_on = db.Column(db.DateTime, default=db.func.now())
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def __init__(self, title, description, creator, visibility):
        from slugify import slugify
        self.title = title
        self.slug = slugify(title)
        self.description = description
        self.creator = creator
        self.isProjectPublic = visibility

    def active_prompts(self):
        """
        Obtains the prompts for this project that are active

        :return: list of Prompt objects that are currently active for this project
        """
        return [prompt for prompt in self.prompts if prompt.is_active]

    def project_as_json(self):
        """
        Create a JSON containing the project title and project prompts (text and images) for use in API.

        Returns: dict of dicts containing the project title and associated prompts formatted for API consumption.
        """
        # TODO: do we really only want active prompts?
        return {
            'id': self.id,
            'title': self.title,
            'slug': self.slug,
            'description': self.description,
            'creator': self.creator,
            'isPublic': self.isProjectPublic,
            'HasConsent': self.isConsentEnabled,
            'timestamp': self.created_on.strftime("%Y-%m-%d %H:%M:%S"),
            'prompts': [p.serialize() for p in self.prompts if p.is_active],
            'codebook': [c.text for c in self.codebook.first().codes.all()] if self.codebook.first() else []
        }


class ProjectPrompt(db.Model):
    """
    The discussion prompts used within the application for a project

    Backrefs:
        Can refer to its parent project with 'project'

    Relationships:
        one-to-many: a projectPrompt can be used by many interviews
    """
    id = db.Column(db.Integer, primary_key=True)
    creator = db.Column(db.Integer, db.ForeignKey('user.id'))
    text_prompt = db.Column(db.String(64))
    image_path = db.Column(db.String(64), default="default.jpg")
    # Used as a 'soft-delete' to preserve prompt-content for viewing
    is_active = db.Column(db.SmallInteger, default=1)

    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))

    created_on = db.Column(db.DateTime, default=db.func.now())
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def serialize(self):
        """
        A serialized version of a prompt to use within views

        returns
            dict: a serialization of a prompt
        """
        from flask import request
        from gabber import app
        # Only required as the server is behind a proxy @OpenLab
        uri = (request.url_root[0:(len(request.url_root)-1)] +
               app.static_url_path + '/img/' + str(self.project_id) + '/')

        return {
            'id': self.id,
            'text': self.text_prompt,
            'imageURL': uri + str("" if not None else self.image_path),
            'creatorID': self.creator,
            'projectID': self.project_id
        }


class InterviewSession(db.Model):
    """
    An interview session between participants for a set of prompts

    Relationships:
        one-to-many: an interview must be consented by many participants
        one-to-many: many participants can be involved in one interview
        one-to-many: an interview can have many connections
    """
    id = db.Column(db.String(260), primary_key=True)
    recording_url = db.Column(db.String(260))
    creator_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    project_id = db.Column(db.Integer, db.ForeignKey('project.id'))
    created_on = db.Column(db.DateTime, default=db.func.now())

    prompts = db.relationship('InterviewPrompts', backref='interview', lazy='dynamic')
    participants = db.relationship('InterviewParticipants', backref='interview', lazy='dynamic')
    connections = db.relationship('Connection', backref='interview', lazy='dynamic')

    def creator(self):
        """
        ??

        :returns ??
        """
        from gabber.users.models import User
        return User.query.get(self.creator_id)

    def project(self):
        """
        The project associated with this interview

        :returns The project associated with this interview.
        """
        return Project.query.get(self.project_id)

    def codebook(self):
        """
        returns all codes associated with this project
        """
        cb = self.project().codebook.first()
        return [{'text': str(i.text), 'id': i.id} for i in cb.codes.all()] if cb else []


class InterviewPrompts(db.Model):
    """
    These are the annotations created during the capture of an interview, which differ
    from an annotation below as they are used for structural representation ontop of the recording.

    Backref:
        Can refer to associated interview with 'interview'
    """
    id = db.Column(db.Integer, primary_key=True)
    prompt_id = db.Column(db.Integer, db.ForeignKey('project_prompt.id'))
    interview_id = db.Column(db.String(260), db.ForeignKey('interview_session.id'))
    # Where in the structural annotation starts and ends
    start_interval = db.Column(db.Integer)
    end_interval = db.Column(db.Integer, default=0)
    # TODO: fix this: we want to update from app
    #created_on = db.Column(db.DateTime, default=db.func.now())

    def serialize(self):
        """
        A serialized version of a connection to use within views

        returns
            dict: a serialization of a connection
        """
        from gabber.users.models import User
        import datetime
        return {
            'id': str(self.id).encode('utf-8'),
            'start': self.start_interval,
            'end': self.end_interval,
            'length': self.end_interval - self.start_interval,
            'timestamp': 10,
            'days_since': 10,
            'interview': {
                'id': self.interview_id.encode('utf-8'),
                'topic': ProjectPrompt.query.get(self.prompt_id).text_prompt.encode('utf-8'),
                # TODO: why is this hard-coded?
                'url': str("https://gabber.audio" + "/protected/" + InterviewSession.query.get(self.interview_id).recording_url),
                'uri': "https://gabber.audio/project/session/interview/" + str(self.interview_id) + "?r=" + str(self.id)
            }
        }


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
    role = db.Column(db.Boolean, default=0)

    def fullname(self):
        """
        The project associated with this interview

        :returns The project associated with this interview.
        """
        from gabber.users.models import User
        return User.query.get(self.user_id).fullname


class Connection(db.Model):
    """
    A connection (reflective perspective or opinion) from a user on a segment of an interview.

    Relationships:
        A connection can be associated with many codes.

    Backrefs:
        Can refer to its creator with 'user'
        Can refer to its parent interview with 'interview'
    """
    id = db.Column(db.Integer, primary_key=True)
    # Although many are chosen, a general justification by the user must be provided.
    justification = db.Column(db.String(1120))
    # Where in the interview this connection starts and ends
    start_interval = db.Column(db.Integer)
    end_interval = db.Column(db.Integer, default=0)

    # A connection can be associated with many codes
    codes = db.relationship("Code", secondary=codes_for_connections, backref="connections")
    comments = db.relationship('ConnectionComments', backref='connection', lazy='dynamic')

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    interview_id = db.Column(db.Integer, db.ForeignKey('interview_session.id'))

    created_on = db.Column(db.DateTime, default=db.func.now())
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def serialize(self):
        """
        A serialized version of a connection to use within views

        returns
            dict: a serialization of a connection
        """
        from gabber.users.models import User
        import datetime
        return {
            'id': self.id,
            'content': u''.join(self.justification).encode('utf-8').strip(),
            'start': self.start_interval,
            'end': self.end_interval,
            'length': self.end_interval - self.start_interval,
            'timestamp': self.created_on.strftime("%Y-%m-%d %H:%M:%S"),
            'days_since': abs((self.created_on - datetime.datetime.now()).days),
            'creator': u''.join(User.query.filter_by(id=self.user_id).first().fullname).encode('utf-8').strip(),
            'creator_id': User.query.filter_by(id=self.user_id).first().id,
            'tags': [str(i.text) for i in self.codes],
            'comments': [i.serialize() for i in self.comments],
            'interview': {
                'id': self.interview_id,
                # TODO: why is this hard-coded?
                'url': str("https://gabber.audio" + "/protected/" + InterviewSession.query.get(self.interview_id).recording_url),
                'uri': "https://gabber.audio/project/session/interview/" + str(self.interview_id) + "?r=" + str(self.id)
            }
        }


class ConnectionComments(db.Model):
    """
    Comments can be made on connections (where parent is 0) and on themselves.

    Backrefs:
        A comment can refer to its creator with 'user'
        A comment can refer to the connection its associated with via 'connection'
    """
    __tablename__ = 'connection_comments'

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(1120), default=None)

    # If this is zero, then it is a response to the root, e.g. the connection itself.
    parent_id = db.Column(db.Integer, db.ForeignKey('connection_comments.id'))
    children = db.relationship('ConnectionComments', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')

    # Who created it and for what purpose?
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    connection_id = db.Column(db.Integer, db.ForeignKey('connection.id'))

    created_on = db.Column(db.DateTime, default=db.func.now())
    updated_on = db.Column(db.DateTime, default=db.func.now(), onupdate=db.func.now())

    def serialize(self):
        from gabber.users.models import User
        import datetime
        return {
            'id': self.id,
            'pid': self.parent_id,
            'content': str(self.text),
            'timestamp': self.created_on.strftime("%Y-%m-%d %H:%M:%S"),
            'days_since': abs((self.created_on - datetime.datetime.now()).days),
            'creator': str(User.query.filter_by(id=self.user_id).first().fullname),
            'children': [i.serialize() for i in self.children.order_by(db.desc(ConnectionComments.created_on)).all()],
        }


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
    name = db.Column(db.String)
    codes = db.relationship('Code', backref="codebook", lazy='dynamic')


class Code(db.Model):
    """
    Holds a textual "Code" for a specific Codebook.

    Note: this approach is not ideal as we would have duplicate codes across books.

    Backref:
        Can refer to associated codebook with 'codebook'
    """
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(64))
    codebook_id = db.Column(db.Integer, db.ForeignKey('codebook.id'))


class Playlists(db.Model):
    """
    The name and creator of a playlist.
    TODO: for simplicity this does not consider a collaborative playlist
    """
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(140))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    regions = db.relationship('PlaylistRegions', cascade="all,delete", backref="playlist", lazy='dynamic')

    def serialize(self):
        """
        A serialized version of a playlist, including all associated regions

        :return: a serialization (dict) of the playlist region
        """
        return {
            'id': self.id,
            'title': self.name,
            'uid': self.user_id,
            'regions': [r.serialize() for r in self.regions]
        }


class PlaylistRegions(db.Model):
    """
    The regions chosen by a user for a specific playlist
    """
    id = db.Column(db.Integer, primary_key=True)
    note = db.Column(db.String)
    playlist_id = db.Column(db.Integer, db.ForeignKey('playlists.id'))
    # TODO: previously named regions connections
    region_id = db.Column(db.Integer, db.ForeignKey('connection.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __init__(self, uid, pid, rid):
        self.user_id = uid
        self.playlist_id = pid
        self.region_id = rid

    def serialize(self):
        """
        A serialized version of a region for a playlist

        :return: a serialization (dict) of the playlist region
        """
        region = Connection.query.get(self.region_id).serialize()
        # Assign the true region ID rather than the ID of this model object
        region['id'] = self.region_id
        region['note'] = self.note
        region['region_id'] = self.region_id
        region['playlist_region_id'] = self.id
        region['playlist_id'] = self.playlist_id
        region['user_id'] = self.user_id
        return region
