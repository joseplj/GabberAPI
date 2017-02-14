from gabber import db
from gabber.projects.models import Project
from flask import Blueprint, redirect, render_template
import json

main = Blueprint('main', __name__)


@main.route('/', methods=['GET'])
def index():
    return render_template('views/main/index.html')


@main.route('about/', methods=['GET'])
def about():
    return render_template('views/main/about.html')


@main.route('projects/', methods=['GET'])
def projects():
    return render_template('views/main/projects.html', projects=db.session.query(Project).all())
