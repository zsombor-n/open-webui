# Dual Database Setup - OpenWebUI + Cogniforce

This documentation describes the implementation of a dual-database architecture where the application maintains two independent database connections for different business domains.

## Architecture Overview

### Database Domains
- **OpenWebUI Database**: Original business logic, user management, chats, files, etc.
- **Cogniforce Database**: Analytics, insights, and new feature development

### Key Benefits
- ✅ **Independent Development**: Teams can work on different databases without conflicts
- ✅ **Separate Migrations**: Each database has its own migration history
- ✅ **Different Servers**: Databases can be hosted on different servers/providers
- ✅ **Domain Separation**: Clear boundary between core functionality and analytics
- ✅ **Independent Deployments**: Teams can deploy database changes independently

## File Structure

```
backend/open_webui/
├── internal/
│   ├── db.py                     # OpenWebUI database connection
│   └── cogniforce_db.py          # Cogniforce database connection
├── models/                       # OpenWebUI models (existing)
├── cogniforce_models/            # Cogniforce models (new)
│   ├── __init__.py
│   ├── analytics.py              # Analytics models
│   └── repositories.py           # Database operations
├── migrations/                   # OpenWebUI migrations (existing)
├── cogniforce_migrations/        # Cogniforce migrations (new)
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_cogniforce_analytics.py
├── alembic.ini                   # OpenWebUI Alembic config
└── cogniforce_alembic.ini        # Cogniforce Alembic config
```

## Configuration

### Environment Variables

#### Required
```bash
# Original OpenWebUI database
DATABASE_URL=postgresql://user:pass@localhost:5432/openwebui

# New Cogniforce database
COGNIFORCE_DATABASE_URL=postgresql://user:pass@localhost:5432/cogniforce
```

#### Optional (Auto-configured)
If `COGNIFORCE_DATABASE_URL` is not provided:
- **PostgreSQL**: Automatically uses same server with database name `cogniforce`
- **SQLite**: Creates separate file `cogniforce.db`

### Database URL Examples
```bash
# Same PostgreSQL server, different databases
DATABASE_URL=postgresql://user:pass@localhost:5432/openwebui
COGNIFORCE_DATABASE_URL=postgresql://user:pass@localhost:5432/cogniforce

# Different PostgreSQL servers
DATABASE_URL=postgresql://user:pass@prod-server:5432/openwebui
COGNIFORCE_DATABASE_URL=postgresql://analytics:pass@analytics-server:5432/cogniforce

# Mixed: PostgreSQL + SQLite
DATABASE_URL=postgresql://user:pass@localhost:5432/openwebui
COGNIFORCE_DATABASE_URL=sqlite:///./data/cogniforce.db
```

## Database Operations

### OpenWebUI Database (Existing)
```python
from open_webui.models.users import Users
from open_webui.internal.db import get_db

# Use existing OpenWebUI database
with get_db() as session:
    users = session.query(Users).all()
```

### Cogniforce Database (New)
```python
from open_webui.cogniforce_models.repositories import UserEngagementRepository
from open_webui.internal.cogniforce_db import get_cogniforce_session

# Use Cogniforce database
engagement = UserEngagementRepository.create_or_update_engagement(
    user_id="user123",
    total_conversations=10,
    total_messages=150
)
```

### Dual Database Usage
```python
def cross_database_operation():
    # Get user from OpenWebUI database
    with get_db() as openwebui_session:
        user = openwebui_session.query(Users).filter_by(id="user123").first()

    # Create analytics in Cogniforce database
    if user:
        engagement = UserEngagementRepository.create_or_update_engagement(
            user_id=user.id,
            total_conversations=user.chat_count,  # Cross-reference data
            daily_active_days=calculate_active_days(user)
        )

    return engagement
```

## Migration Management

### OpenWebUI Migrations (Existing)
```bash
# Run OpenWebUI migrations
cd backend/open_webui
uv run alembic upgrade head

# Create new OpenWebUI migration
uv run alembic revision --autogenerate -m "Add new feature"
```

### Cogniforce Migrations (New)
```bash
# Run Cogniforce migrations
cd backend/open_webui
uv run alembic -c cogniforce_alembic.ini upgrade head

# Create new Cogniforce migration
uv run alembic -c cogniforce_alembic.ini revision --autogenerate -m "Add analytics feature"
```

### Independent Migration Histories
```bash
# Check OpenWebUI migration status
uv run alembic current
uv run alembic history

# Check Cogniforce migration status
uv run alembic -c cogniforce_alembic.ini current
uv run alembic -c cogniforce_alembic.ini history
```

## Development Workflow

### Team A (OpenWebUI Core)
1. Develops features in `models/` directory
2. Creates migrations with standard `alembic` commands
3. Uses `get_db()` for database operations
4. Deploys to OpenWebUI database independently

### Team B (Cogniforce Analytics)
1. Develops features in `cogniforce_models/` directory
2. Creates migrations with `alembic -c cogniforce_alembic.ini`
3. Uses `get_cogniforce_session()` for database operations
4. Deploys to Cogniforce database independently

### Cross-Team Integration
- Teams can reference each other's data via repositories
- No direct database coupling
- Clear interfaces between domains
- Independent deployment cycles

## Models

### OpenWebUI Models (Existing)
Located in `models/` directory, inherit from `Base`:
```python
from open_webui.internal.db import Base

class User(Base):
    __tablename__ = "user"
    # ... existing model definition
```

### Cogniforce Models (New)
Located in `cogniforce_models/` directory, inherit from `CogniforceBase`:
```python
from open_webui.internal.cogniforce_db import CogniforceBase

class ConversationAnalysis(CogniforceBase):
    __tablename__ = "conversation_analysis"
    # ... new model definition
```

## Deployment

### Database Creation
```sql
-- Create databases
CREATE DATABASE openwebui;
CREATE DATABASE cogniforce;

-- Grant permissions
GRANT ALL PRIVILEGES ON DATABASE openwebui TO your_user;
GRANT ALL PRIVILEGES ON DATABASE cogniforce TO your_user;
```

### Application Startup
1. Both database connections are established automatically
2. Each database runs its own migration check
3. Independent connection pools are maintained
4. Failures in one database don't affect the other

### Production Considerations
- **Connection Pooling**: Each database has separate pool configuration
- **Monitoring**: Monitor both databases independently
- **Backups**: Separate backup strategies for each database
- **Performance**: Optimize each database for its specific workload
- **Security**: Different access controls per database domain

## Troubleshooting

### Connection Issues
```bash
# Test OpenWebUI database connection
uv run python -c "from open_webui.internal.db import engine; print(engine.execute('SELECT 1').scalar())"

# Test Cogniforce database connection
uv run python -c "from open_webui.internal.cogniforce_db import cogniforce_engine; print(cogniforce_engine.execute('SELECT 1').scalar())"
```

### Migration Issues
```bash
# Reset migrations if needed
uv run alembic stamp head                           # OpenWebUI
uv run alembic -c cogniforce_alembic.ini stamp head # Cogniforce

# Check current revision
uv run alembic current                              # OpenWebUI
uv run alembic -c cogniforce_alembic.ini current    # Cogniforce
```

### Import Issues
Ensure proper imports:
```python
# OpenWebUI database
from open_webui.internal.db import get_db, Base
from open_webui.models.users import Users

# Cogniforce database
from open_webui.internal.cogniforce_db import get_cogniforce_session, CogniforceBase
from open_webui.cogniforce_models.analytics import ConversationAnalysis
```

## Future Extensions

### Adding New Cogniforce Models
1. Create model in `cogniforce_models/`
2. Import in `cogniforce_migrations/env.py`
3. Generate migration: `alembic -c cogniforce_alembic.ini revision --autogenerate`
4. Run migration: `alembic -c cogniforce_alembic.ini upgrade head`

### Adding Third Database
Follow the same pattern:
1. Create `third_db.py` connection module
2. Create `third_models/` directory
3. Create `third_alembic.ini` configuration
4. Create `third_migrations/` directory
5. Update `env.py` with third database configuration

This architecture scales to support multiple independent database domains as your application grows.