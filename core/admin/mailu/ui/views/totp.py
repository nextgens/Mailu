import base64
import io

from flask import current_app as app
from flask_babel import lazy_gettext as _

from mailu import models, utils
from mailu.ui import ui, forms, access

import pyotp
import qrcode

import flask
import flask_login
import wtforms_components

@ui.route('/totp/list', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/totp/list/<path:user_email>', methods=['GET'])
@access.owner(models.User, 'user_email')
def totp_list(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    return flask.render_template('totp/list.html', user=user)


@ui.route('/totp/create', methods=['GET', 'POST'], defaults={'user_email': None})
@ui.route('/totp/create/<path:user_email>', methods=['GET', 'POST'])
@access.owner(models.User, 'user_email')
def totp_create(user_email):
    user_email = user_email or flask_login.current_user.email
    user = models.User.query.get(user_email) or flask.abort(404)
    form = forms.TOTPForm()
    wtforms_components.read_only(form.displayed_b32secret)
    if not form.b32secret.data:
        form.b32secret.data = pyotp.random_base32()
    url = pyotp.totp.TOTP(form.b32secret.data).provisioning_uri(name=user_email, issuer_name=app.config['HOSTNAME'])
    q = qrcode.QRCode(box_size=5)
    q.add_data(url)
    buf = io.BytesIO()
    q.make_image().save(buf)
    data = base64.b64encode(buf.getvalue()).decode('utf-8')
    form.displayed_b32secret.data = form.b32secret.data
    form.displayed_url.data = url
    if form.validate_on_submit():
        totp = pyotp.TOTP(form.b32secret.data)
        if totp.verify(form.displayed_verify.data, valid_window=1):
            utils.TOTP_block(user_email, form.displayed_verify.data)
            token = models.TOTP(user=user)
            form.populate_obj(token)
            models.db.session.add(token)
            models.db.session.commit()
            flask.flash(_('TOTP created'))
            redir = flask.session.pop('redirect_to') or flask.url_for('.totp_list', user_email=user.email)
            return flask.redirect(redir)
        flask.flash(_('Invalid TOTP verification code!'),'error')
    return flask.render_template('totp/create.html', form=form, url_data=url, img_data=data)

@ui.route('/totp/delete/<totp_id>', methods=['GET', 'POST'])
@access.confirmation_required("delete a TOTP")
@access.owner(models.TOTP, 'totp_id')
def totp_delete(totp_id):
    totp = models.TOTP.query.get(totp_id) or flask.abort(404)
    user = totp.user
    models.db.session.delete(totp)
    models.db.session.commit()
    flask.flash(_('TOTP deleted'))
    return flask.redirect(
        flask.url_for('.totp_list', user_email=user.email))
