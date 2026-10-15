# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()

# Sense límits per defecte: només es limiten els endpoints que ho declaren.
# Memòria del procés: el servidor és un sol procés amb fils, n'hi ha prou.
limiter = Limiter(key_func=get_remote_address, storage_uri='memory://', default_limits=[])
