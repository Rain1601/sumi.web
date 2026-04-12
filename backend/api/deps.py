from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.engine import get_session


async def get_db() -> AsyncSession:
    async for session in get_session():
        yield session


# ═══════════════════════════════════════════════════════════════
# Auth context — user + tenant
# ═══════════════════════════════════════════════════════════════

@dataclass
class AuthContext:
    """Authenticated user context with tenant info."""
    user_id: str
    tenant_id: str
    role: str  # "owner" | "admin" | "member" | "viewer"


def _init_firebase():
    """Lazily initialize Firebase Admin SDK (once)."""
    import firebase_admin
    from firebase_admin import credentials

    if firebase_admin._apps:
        return  # Already initialized

    from backend.config import settings
    cred_path = settings.firebase_credentials_json
    if cred_path:
        import json
        try:
            # Try as JSON string first (for env var / Secret Manager)
            cred_data = json.loads(cred_path)
            cred = credentials.Certificate(cred_data)
        except (json.JSONDecodeError, ValueError):
            # Fall back to file path
            cred = credentials.Certificate(cred_path)
        firebase_admin.initialize_app(cred)
    else:
        # Use Application Default Credentials (Cloud Run auto-provides these)
        firebase_admin.initialize_app()


async def get_current_user_id(
    authorization: Annotated[str | None, Header()] = None,
) -> str:
    """Extract and verify auth token from Authorization header.

    Supports Firebase Auth (production) and Supabase Auth (legacy).
    For development, accepts a plain user ID if app_debug is True.
    """
    from backend.config import settings

    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    token = authorization.removeprefix("Bearer ").strip()

    if settings.is_dev and not token.startswith("ey"):
        # In dev mode, accept plain user IDs for testing
        return token

    if settings.is_dev and token.startswith("ey"):
        # In dev mode, decode JWT without signature verification
        # This allows both Firebase and Supabase tokens to work locally
        try:
            import jwt as pyjwt
            payload = pyjwt.decode(token, options={"verify_signature": False})
            # Firebase uses "user_id" or "uid", Supabase uses "sub"
            uid = payload.get("user_id") or payload.get("uid") or payload.get("sub")
            if uid:
                return uid
        except Exception:
            pass  # Fall through to normal verification

    if settings.auth_provider == "firebase":
        return _verify_firebase_token(token)
    else:
        return _verify_supabase_token(token)


SYSTEM_TENANT_ID = "default-tenant"


async def _clone_default_data(tenant_id: str, user_id: str, db: AsyncSession):
    """Clone all agents and models from the system tenant to a new user's tenant."""
    import logging
    from sqlalchemy import select
    from backend.db.models import Agent, ProviderModel, gen_uuid

    logger = logging.getLogger("kodama.auth")

    # 1. Clone ProviderModels, build old_id → new_id mapping
    result = await db.execute(
        select(ProviderModel).where(ProviderModel.tenant_id == SYSTEM_TENANT_ID)
    )
    system_models = result.scalars().all()
    model_id_map: dict[str, str] = {}  # old_id → new_id

    for m in system_models:
        new_id = gen_uuid()
        model_id_map[m.id] = new_id
        clone = ProviderModel(
            id=new_id,
            tenant_id=tenant_id,
            name=m.name,
            provider_type=m.provider_type,
            provider_name=m.provider_name,
            api_key="",
            model_name=m.model_name,
            config=m.config or {},
            is_active=m.is_active,
        )
        db.add(clone)

    logger.info(f"Cloned {len(system_models)} models to tenant {tenant_id[:8]}")

    # 2. Clone Agents, remap model references
    result = await db.execute(
        select(Agent).where(Agent.tenant_id == SYSTEM_TENANT_ID)
    )
    system_agents = result.scalars().all()

    for a in system_agents:
        new_id = gen_uuid()
        clone = Agent(
            id=new_id,
            tenant_id=tenant_id,
            created_by=user_id,
            name_zh=a.name_zh,
            name_en=a.name_en,
            description_zh=a.description_zh,
            description_en=a.description_en,
            system_prompt=a.system_prompt,
            goal=a.goal,
            asr_model_id=model_id_map.get(a.asr_model_id) if a.asr_model_id else None,
            tts_model_id=model_id_map.get(a.tts_model_id) if a.tts_model_id else None,
            nlp_model_id=model_id_map.get(a.nlp_model_id) if a.nlp_model_id else None,
            asr_provider=a.asr_provider or "",
            asr_config=a.asr_config or {},
            tts_provider=a.tts_provider or "",
            tts_config=a.tts_config or {},
            nlp_provider=a.nlp_provider or "",
            nlp_config=a.nlp_config or {},
            vad_mode=a.vad_mode or "backend",
            vad_config=a.vad_config,
            tools=a.tools or [],
            interruption_policy=a.interruption_policy or "always",
            voiceprint_enabled=a.voiceprint_enabled,
            language=a.language or "auto",
            opening_line=a.opening_line,
            test_scenario=a.test_scenario,
            user_prompt=a.user_prompt,
            version=a.version,
            status=a.status,
            folder_id=a.folder_id,
            call_control=a.call_control,
            cloned_from=a.id,  # Track source template
            role=a.role,
            task_chain=a.task_chain,
            rules=a.rules,
            optimization=a.optimization,
            is_active=a.is_active,
        )
        db.add(clone)

    logger.info(f"Cloned {len(system_agents)} agents to tenant {tenant_id[:8]}")


async def get_auth_context(
    user_id: Annotated[str, Depends(get_current_user_id)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AuthContext:
    """Resolve user's tenant membership. Auto-provisions on first login."""
    from sqlalchemy import select
    from backend.db.models import TenantMember, Tenant, User

    # Find user's tenant membership
    result = await db.execute(
        select(TenantMember).where(TenantMember.user_id == user_id).limit(1)
    )
    membership = result.scalar_one_or_none()

    if membership:
        return AuthContext(
            user_id=user_id,
            tenant_id=membership.tenant_id,
            role=membership.role,
        )

    # First login — auto-provision: create personal tenant + clone default data
    from backend.db.models import gen_uuid

    # Ensure user record exists (must flush before FK references)
    user_result = await db.execute(select(User).where(User.id == user_id))
    if not user_result.scalar_one_or_none():
        user = User(id=user_id, preferred_language="zh")
        db.add(user)
        await db.flush()  # User must exist before TenantMember FK

    # Create personal tenant
    tenant_id = gen_uuid()
    slug = f"personal-{user_id[:8]}"
    tenant = Tenant(id=tenant_id, name="个人空间", slug=slug)
    db.add(tenant)
    await db.flush()  # Tenant must exist before TenantMember FK

    # Add user as owner
    member = TenantMember(
        tenant_id=tenant_id,
        user_id=user_id,
        role="owner",
    )
    db.add(member)
    await db.flush()

    # Clone default agents + models from system tenant
    await _clone_default_data(tenant_id, user_id, db)
    await db.commit()

    return AuthContext(
        user_id=user_id,
        tenant_id=tenant_id,
        role="owner",
    )


def _verify_firebase_token(token: str) -> str:
    """Verify Firebase ID token and return uid."""
    _init_firebase()
    try:
        from firebase_admin import auth
        decoded = auth.verify_id_token(token)
        uid = decoded.get("uid")
        if not uid:
            raise ValueError("Missing 'uid' in token")
        return uid
    except Exception as e:
        error_msg = str(e)
        if "expired" in error_msg.lower():
            raise HTTPException(status_code=401, detail="Token expired")
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def _verify_supabase_token(token: str) -> str:
    """Verify Supabase JWT (legacy fallback)."""
    from backend.config import settings
    try:
        import jwt
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Missing 'sub' claim in token")
        return user_id
    except Exception as e:
        import jwt as pyjwt
        if isinstance(e, pyjwt.ExpiredSignatureError):
            raise HTTPException(status_code=401, detail="Token expired")
        if isinstance(e, pyjwt.InvalidTokenError):
            raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
        raise HTTPException(status_code=401, detail=f"Auth error: {e}")


DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUserId = Annotated[str, Depends(get_current_user_id)]
Auth = Annotated[AuthContext, Depends(get_auth_context)]
