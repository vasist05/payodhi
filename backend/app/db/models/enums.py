from enum import Enum


class VesselTypeEnum(str, Enum):
    crude_tanker = "crude_tanker"
    chemical_tanker = "chemical_tanker"
    cargo = "cargo"
    container = "container"
    fishing = "fishing"
    tanker_other = "tanker_other"
    unknown = "unknown"


class SceneStatusEnum(str, Enum):
    pending = "pending"
    pending_metadata = "pending_metadata"
    processing = "processing"
    processed = "processed"
    failed = "failed"


class SpillStatusEnum(str, Enum):
    detected = "detected"
    under_review = "under_review"
    confirmed = "confirmed"
    rejected = "rejected"


class DriftStatusEnum(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"


class DossierStatusEnum(str, Enum):
    draft = "draft"
    finalized = "finalized"
    superseded = "superseded"


class VerdictEnum(str, Enum):
    prosecutable = "prosecutable"
    person_of_interest = "person_of_interest"
    insufficient_evidence = "insufficient_evidence"


class ActorTypeEnum(str, Enum):
    user = "user"
    system = "system"
    ai_agent = "ai_agent"


class AuditActionEnum(str, Enum):
    create = "create"
    update = "update"
    delete = "delete"
    read = "read"
    login = "login"
    export = "export"
    verdict_change = "verdict_change"


class JobStatusEnum(str, Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
