from gabber import db, helper
from gabber.models import Experience
from flask import render_template, send_from_directory, \
    Markup, flash, url_for, request, redirect, Blueprint

main = Blueprint('main', __name__)


@main.route('/', methods=['GET'])
def index():
    """
    Displays chronologically all experiences that have been made public.
    """
    # All of the experiences that have been consented for public display.
    experiences = Experience.query.filter(Experience.consent != "NONE").all()
    # Pass information we want to display to simplify view logic.
    filtered_experiences = []
    # TODO: transcriptions as "subtitles below audios" for non-natives?
    for experience in experiences:
        # An audio experience is required
        audio = url_for('main.protected', filename=experience.experience)
        # Taking a picture of interviewee is optional. Only show if allowed.
        if experience.authorImage and experience.consent == 'ALL':
            image = url_for('main.protected', filename=experience.authorImage)
        else:
            image = url_for('main.protected', filename='default.png')
        filtered_experiences.append({'audio': audio, 'image': image})
    return render_template('home.html', experiences=filtered_experiences)


@main.route('consent/<token>', methods=['POST'])
def validate_consent(token):
    # TODO: user can re-approve their experience until expiration time met.
    experience_path = helper.confirm_consent(token)[1]
    experience = Experience.query.filter_by(experience=experience_path).first()
    # TODO: validate input -- those haxzors may modify the name property
    # for malicious intent, but for now. Let's make it work.
    experience.consent = request.form['consent']
    db.session.commit()
    # Display a message upon submitting their consent on the home page.
    # That way, if they do approve, they can see their experience too.
    flash(Markup('<h3>Thank you for approving your experience. If you \
                    would like to gather your friends experiences, consider \
                    downloading <a href="/download">gabber</a>.</h3>'))
    return redirect(url_for('main.index'))


@main.route('consent/<token>', methods=['GET'])
def display_consent(token):
    # Get the audio-experience (AX) associated with this consent.
    # The interviewees name and path to the recorded audio is encoded in URI.
    consent = helper.confirm_consent(token)
    # The consent URI exists for a period of time to prevent hacks.
    if not consent:
        return "Approval for this experience has expired."
    # The contents of the experience to display to the user.
    experience_to_approve = {
        'name': consent[0],
        'audio': url_for('main.protected', filename=consent[1]),
        'image': consent[2]
    }
    # Display the experience that the user needs to approve.
    return render_template('consent.html', data=experience_to_approve)


@main.route('protected/<filename>')
def protected(filename):
    # Store on root with nginx config to prevent anyone viewing audios
    # TODO: however, if the filename is known, then anyone can download.
    return send_from_directory('protected', filename)
