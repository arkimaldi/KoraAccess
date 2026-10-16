# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
"""
Ordres de gestió d'usuaris, a executar al servidor:

    python manage.py users create-admin
    python manage.py users create --role operator
    python manage.py users list
    python manage.py users reset-password <usuari>
    python manage.py users deactivate <usuari>
    python manage.py users activate <usuari>

L'accés al servidor és la font de confiança: per això el primer administrador
es crea així i no des d'una pantalla web, on el primer que hi arribés es
convertiria en administrador. I per això també és el camí per recuperar l'accés
si s'oblida la contrasenya de l'últim administrador.

Les contrasenyes es demanen sempre de manera interactiva i sense mostrar-les:
mai com a argument, que quedaria a l'historial de l'intèrpret d'ordres.
"""

import click
from flask.cli import AppGroup

from app import mgr_auth
from app.db_models import Users
from app.messages import AppError, MESSAGES

users_cli = AppGroup('users', help='Gestió d\'usuaris.')


def _prompt_password(label='Contrasenya'):
    return click.prompt(label, hide_input=True, confirmation_prompt='Repetiu-la')


def _fail(message):
    raise click.ClickException(message)


def _get_user_or_fail(username):
    user = mgr_auth.get_user_by_username(username)
    if user is None:
        _fail(f'No existeix l\'usuari {mgr_auth.normalize_username(username)}.')
    return user


def _app_error_text(e):
    """Text anglès dels errors de política de contrasenyes."""
    try:
        return MESSAGES[e.key].format(**e.params)
    except (KeyError, IndexError):
        return str(e)


def _create(username, full_name, role):
    password = _prompt_password()
    try:
        user = mgr_auth.create_user(username, password, role, full_name=full_name)
    except AppError as e:
        _fail(_app_error_text(e))
    click.echo(f'Creat l\'usuari {user.username} amb perfil {user.role}.')


@users_cli.command('create-admin')
@click.option('--username', prompt='Nom d\'usuari', default='admin', show_default=True)
@click.option('--full-name', prompt='Nom complet', default='', show_default=False)
def create_admin(username, full_name):
    """Crea un administrador. Per a la instal·lació inicial."""
    _create(username, full_name, 'admin')


@users_cli.command('create')
@click.option('--username', prompt='Nom d\'usuari')
@click.option('--full-name', prompt='Nom complet', default='', show_default=False)
@click.option('--role', type=click.Choice(mgr_auth.ROLES), default='operator', show_default=True)
def create(username, full_name, role):
    """Crea un usuari."""
    _create(username, full_name, role)


@users_cli.command('list')
def list_users():
    """Llista els usuaris."""
    users = Users.query.order_by(Users.username).all()
    if not users:
        click.echo('No hi ha cap usuari. Creeu-ne un amb: python manage.py users create-admin')
        return
    click.echo(f'{"USUARI":20} {"PERFIL":9} {"ACTIU":6} {"CANVI PEND.":11} DARRER LOGIN')
    for u in users:
        last = u.last_login_dts.strftime('%Y-%m-%d %H:%M') if u.last_login_dts else '—'
        click.echo(f'{u.username:20} {u.role:9} {"sí" if u.is_active else "no":6} '
                   f'{"sí" if u.must_change_password else "no":11} {last}')


@users_cli.command('reset-password')
@click.argument('username')
@click.option('--temporary/--permanent', default=True, show_default=True,
              help='Temporal: l\'usuari l\'haurà de canviar en entrar.')
def reset_password(username, temporary):
    """Restableix la contrasenya i tanca totes les sessions de l'usuari."""
    user = _get_user_or_fail(username)
    password = _prompt_password('Contrasenya nova')
    try:
        mgr_auth.check_password_policy(password)
    except AppError as e:
        _fail(_app_error_text(e))
    user.password_hash = mgr_auth.hash_password(password)
    user.password_changed_dts = mgr_auth.utcnow()
    user.must_change_password = temporary
    mgr_auth.revoke_user_sessions(user)
    mgr_auth._initial_password_no_longer_valid(user)
    click.echo(f'Contrasenya restablerta per a {user.username}. Sessions tancades.'
               + (' L\'haurà de canviar en entrar.' if temporary else ''))


def _set_active(username, active):
    user = _get_user_or_fail(username)
    # Les mateixes regles que la pantalla d'usuaris: viuen a mgr_auth.
    try:
        mgr_auth.set_active(user, active)
    except AppError as e:
        _fail(_app_error_text(e))
    click.echo(f'Usuari {user.username} {"activat" if active else "desactivat; sessions tancades"}.')


@users_cli.command('deactivate')
@click.argument('username')
def deactivate(username):
    """Desactiva un usuari i en tanca les sessions."""
    _set_active(username, False)


@users_cli.command('activate')
@click.argument('username')
def activate(username):
    """Torna a activar un usuari."""
    _set_active(username, True)
