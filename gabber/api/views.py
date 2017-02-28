from gabber import app, db
from gabber.users.models import User
from gabber.projects.models import Interview, Project, ProjectPrompt, Participant, ComplexNeeds
from gabber.consent.models import InterviewConsent
from flask import jsonify, request, Blueprint
import json
import os

api = Blueprint('api', __name__)


@api.route('projects', methods=['GET'])
def projects():
    # TODO: filter based on user credentials.
    # TODO: use built-in __dict__ and filter to simplify accessing from models.
    res = []
    for project in Project.query.join(ProjectPrompt).all():
        uri = (request.url_root[0:(len(request.url_root)-1)] +
               app.static_url_path + '/img/' + str(project.id) + '/')

        prompts = [{'imageName': uri + p.image_path, 'prompt': p.text_prompt}
                   for p in project.prompts]

        res.append({'theme': project.title, 'prompts': prompts})

    return jsonify(res), 200


@api.route('register', methods=['POST'])
def register():
    username = request.form.get('email', None)
    password = request.form.get('password', None)
    fullname = request.form.get('fullname', None)

    if not username or not password or not fullname:
        return jsonify({'error': 'All fields are required.'}), 400

    if username in [user.username for user in db.session.query(User.username)]:
        return jsonify({'error': 'An account with that email exists.'}), 400

    db.session.add(User(username, password, fullname))
    db.session.commit()
    return jsonify({'success': 'A user has been created successfully'}), 200


@api.route('auth', methods=['POST'])
def login():
    username = request.form.get('username', None)
    password = request.form.get('password', None)

    if not username or not password:
        return jsonify({'error': 'All fields are required.'}), 400

    known_users = [user.username for user in db.session.query(User.username)]
    if username and username in known_users:
        user = User.query.filter_by(username=username).first()
        if user and user.is_correct_password(password):
            return jsonify({'success': 'We did it!'}), 200
        return jsonify({'error': 'Incorrect password provided.'}), 400
    return jsonify({'error': 'Username and password do not match.'}), 400


@api.route('upload', methods=['POST'])
def upload():
    """
    Allows a client to upload an audio interview with associated meta-data,
    including details of participants in a JSON encoded file.
    """
    # TODO: return better errors for specific missing data.
    if not request.files or not request.form:
        return jsonify({'error': 'Required data has not been sent.'}), 400

    #TODO: this is a string that we expect to be in JSON serialised.
    participants = request.form.get('participants', None)

    if participants:
        parts = [Participant(name=i['Name'], email=i['Email'],
                             gender=i['Gender'], age=i['Age'],
                             consent=[InterviewConsent(type='ALL')])
                 for i in json.loads(participants)]
    else:
        return jsonify({'error': 'No participants were interviewed.'}), 400

    #TODO: validate: check mime type, use magic_python.
    interviewFile = request.files['experience']
    filename = interviewFile.filename.split(".")[0] + ".mp4"
    interviewFile.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

    interview = Interview(
        audio=filename,
        location=request.form.get('location', None),
        prompt_id=ProjectPrompt.query.filter_by(
            text_prompt=request.form.get('promptText', None)).first().id
    )

    needs = request.form.get('ComplexNeedsAsJSON', None)
    # These are optional (only for FF deployment) so don't produce an error.
    if needs:
        cn = [ComplexNeeds(type=key, timeline=value['timeline'],
                           month=value['month'], year=value['year'],
                           interview_id=interview.id,
                           participant_id=parts[0].id)
              for key, value in json.loads(needs).items()]

        parts[0].complexneeds.extend(cn)

    # Populating relationship fields outside constructor due to extending lists.
    interview.consents.extend([i.consent.first() for i in parts])
    interview.participants.extend(parts)

    db.session.add(interview)
    db.session.commit()

    return jsonify({'success': 'We did it!'}), 200