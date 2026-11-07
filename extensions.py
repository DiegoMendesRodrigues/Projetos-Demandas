# Projetos & Demandas | Solução on-line para a gestão de projetos e demandas
# Desenvolvido por Diego Mendes Rodrigues
from flask_babel import Babel
from flask_mail import Mail
from flask_security import Security
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

babel = Babel()
csrf = CSRFProtect()
db = SQLAlchemy()
mail = Mail()
security = Security()
