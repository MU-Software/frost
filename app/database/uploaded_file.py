import app.common.utils as utils
import app.database as db_module
import app.database.user as user_module

db = db_module.db


class UploadedFile(db_module.DefaultModelMixin, db.Model):
    __tablename__ = 'TB_UPLOADED_FILE'
    uuid = db.Column(db_module.PrimaryKeyType,
                     db.Sequence('SQ_UploadedFile_UUID'),
                     primary_key=True,
                     nullable=False)

    uploaded_by_id = db.Column(db_module.PrimaryKeyType,
                               db.ForeignKey('TB_USER.uuid'),
                               nullable=True)
    uploaded_by = db.relationship(user_module.User, primaryjoin=uploaded_by_id == user_module.User.uuid)

    mimetype = db.Column(db.String, nullable=False)
    size = db.Column(db.Integer, nullable=False)
    filename = db.Column(db.String, unique=True, nullable=False)
    original_filename = db.Column(db.String, nullable=False)
    additional_data = db.Column(db.String, nullable=True)  # JSON parsable data
    alternative_data = db.Column(db.String, nullable=True)  # JSON parsable data
    post_process_data = db.Column(db.String, nullable=True)  # JSON parsable data

    locked_at = db.Column(db.DateTime, nullable=True)
    locked_by_id = db.Column(db_module.PrimaryKeyType,
                             db.ForeignKey('TB_USER.uuid'),
                             nullable=True)
    locked_by = db.relationship(user_module.User, primaryjoin=locked_by_id == user_module.User.uuid)
    why_locked = db.Column(db.String, nullable=True)

    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by_id = db.Column(db_module.PrimaryKeyType,
                              db.ForeignKey('TB_USER.uuid'),
                              nullable=True)
    deleted_by = db.relationship(user_module.User, primaryjoin=deleted_by_id == user_module.User.uuid)

    private = db.Column(db.Boolean, default=False, nullable=False)
    readable = db.Column(db.Boolean, default=True, nullable=False)
    writable = db.Column(db.Boolean, default=False, nullable=False)  # Placeholder for the future

    def to_dict(self):
        result = {'resource': 'file'}

        if self.deleted_at:
            result.update({
                'deleted_at': utils.as_utctime(self.deleted_at),
                'deleted_at_timestamp': utils.as_timestamp(self.deleted_at),
            })
        elif self.locked_at:
            result.update({
                'locked_at': utils.as_utctime(self.locked_at),
                'locked_at_timestamp': utils.as_timestamp(self.locked_at),
                'why_locked': self.why_locked,
            })
        else:
            result.update({
                'uploaded_by': self.uploaded_by.to_dict(),
                'private': self.private,

                'mimetype': self.mimetype,
                'size': self.size,
                'filename': self.filename,
                'url': f'/uploads/{self.filename}',

                'additional_data': self.additional_data,
                'alternative_data': self.alternative_data,
            })

        return result
