from gabber import ma, db
# TODO: this should help simplify refactoring
from gabber.projects.models import \
    Connection as UserAnnotations, \
    Code as Tags, \
    ConnectionComments as Comments
from marshmallow import pre_load
from gabber.api.schemas.project import HelperSchemaValidator


class UserAnnotationTagSchema(ma.ModelSchema):
    class Meta:
        model = Tags
        dateformat = "%d-%b-%Y"
        exclude = ['codebook', 'connections']


class UserAnnotationCommentSchema(ma.ModelSchema):
    user_id = ma.Function(lambda annotation: annotation.user.id)

    class Meta:
        model = Comments
        dateformat = "%d-%b-%Y"
        exclude = ['user']


class UserAnnotationSchema(ma.ModelSchema):
    """
    Current issues:
        1) tags is a list and cannot be replaced or the update does not work (since it does not know
        about the tags relationship); for now I have created labels from the tags attribute.
        2) comments have replies, which is a list of FKs rather than content. Due to the relationship,
        an infinite loop occurs when serialising itself.
    """
    labels = ma.Nested(UserAnnotationTagSchema, many=True, attribute="tags")
    comments = ma.Nested(UserAnnotationCommentSchema, many=True, attribute="comments")

    class Meta:
        model = UserAnnotations
        include_fk = True
        dateformat = "%d-%b-%Y"
        exclude = ['interview', 'user']

    @staticmethod
    def validate_intervals(attribute, data, validator):
        if attribute not in data:
            validator.errors.append('%s_REQUIRED' % attribute)
        elif validator.is_not_int(data[attribute]):
            validator.errors.append('%s_IS_NOT_INT' % attribute)
        elif data[attribute] < 0:
            validator.errors.append('%s_MUST_BE_POSITIVE_INT' % attribute)
        else:
            return True

    @pre_load()
    def __validate(self, data):
        validator = HelperSchemaValidator('USER_ANNOTATIONS')

        validator.validate('content', 'str', data)
        valid_start = self.validate_intervals('start_interval', data, validator)
        valid_end = self.validate_intervals('end_interval', data, validator)

        if valid_start and valid_end:
            if data['start_interval'] > data['end_interval']:
                validator.errors.append('START_BEFORE_END')

        # TODO: tags are currently optional
        if data.get('tags'):
            if validator.is_not_list(data['tags']):
                validator.errors.append('TAGS_IS_NOT_LIST')
            else:
                for tag in data['tags']:
                    if validator.is_not_int(tag):
                        validator.errors.append('TAG_IS_NOT_INT')

        validator.raise_if_errors()


class UserAnnotationPostSchema(ma.Schema):
    """
    A new schema is required as it loads (serializes) the object, hence we need to
    validate it to produce custom error codes, which mashmallow does not support.
    """

    message = ma.String()
    start = ma.Int()
    end = ma.Int()
    tags = ma.List(ma.Int())

    @pre_load()
    def __validate(self, data):
        validator = HelperSchemaValidator('USER_ANNOTATIONS')

        message_valid = validator.validate('message', 'str', data)
        start_valid = validator.validate('start', 'int', data)
        end_valid = validator.validate('end', 'int', data)
        tags_valid = validator.validate('tags', 'list', data)

        if tags_valid:
            for topic in data['tag']:
                if validator.is_not_str(topic):
                    validator.errors.append('TOPIC_IS_NOT_STRING')
                if not topic:
                    validator.errors.append('TOPIC_IS_EMPTY')

        validator.raise_if_errors()
