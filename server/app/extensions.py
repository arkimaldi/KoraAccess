# (C) 2026 Kimaldi Electronics,s.l. <www.kimaldi.com>. All rights reserved.
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()
