from datetime import datetime
from enum import Enum
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


JsonValue = (
    str | int | float | bool | None | list[Any] | dict[str, Any]
)


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OrmSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class HttpMethod(str, Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class StatusCodeAssertion(StrictSchema):
    type: Literal["status_code"]
    operator: Literal["equals"]
    expected: int


class JsonValueAssertion(StrictSchema):
    type: Literal["json_value"]
    path: str
    operator: Literal["equals"]
    expected: JsonValue


class JsonTypeAssertion(StrictSchema):
    type: Literal["json_type"]
    path: str
    operator: Literal["is"]
    expected: Literal["object", "array", "string", "number", "boolean", "null"]


AssertionSchema = Annotated[
    StatusCodeAssertion | JsonValueAssertion | JsonTypeAssertion,
    Field(discriminator="type"),
]


class ExtractorSchema(StrictSchema):
    name: str = Field(min_length=1, max_length=255)
    path: str = Field(min_length=1)


class ProjectCreate(StrictSchema):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class ProjectUpdate(ProjectCreate):
    pass


class ProjectRead(OrmSchema):
    id: int
    name: str
    description: str
    created_at: datetime
    updated_at: datetime


class SuiteCreate(StrictSchema):
    name: str = Field(min_length=1, max_length=255)
    description: str = ""


class SuiteUpdate(SuiteCreate):
    draft_revision: int = Field(ge=1)


class SuiteRead(OrmSchema):
    id: int
    project_id: int
    name: str
    description: str
    draft_revision: int
    created_at: datetime
    updated_at: datetime


class EnvironmentCreate(StrictSchema):
    name: str = Field(min_length=1, max_length=255)
    base_url: str = Field(min_length=1, max_length=2048)
    headers: dict[str, JsonValue] = Field(default_factory=dict)
    variables: dict[str, JsonValue] = Field(default_factory=dict)
    is_default: bool = False

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("base_url must be an absolute HTTP URL")
        return value.rstrip("/")


class EnvironmentUpdate(EnvironmentCreate):
    pass


class EnvironmentRead(OrmSchema):
    id: int
    name: str
    base_url: str
    headers: dict[str, JsonValue] = Field(validation_alias="headers_json")
    variables: dict[str, JsonValue] = Field(validation_alias="variables_json")
    is_default: bool
    created_at: datetime
    updated_at: datetime


class CaseCreate(StrictSchema):
    project_id: int
    name: str = Field(min_length=1, max_length=255)
    method: HttpMethod
    path: str = Field(min_length=1, max_length=2048)
    headers: dict[str, JsonValue] = Field(default_factory=dict)
    query: dict[str, JsonValue] = Field(default_factory=dict)
    body: JsonValue = None
    assertions: list[AssertionSchema] = Field(default_factory=list)
    extractors: list[ExtractorSchema] = Field(default_factory=list)
    enabled: bool = True

    @field_validator("path")
    @classmethod
    def validate_relative_path(cls, value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme or parsed.netloc or not value.startswith("/"):
            raise ValueError("case path must be relative and start with '/'")
        return value


class CaseUpdate(CaseCreate):
    pass


class CaseRead(OrmSchema):
    id: int
    project_id: int
    name: str
    method: HttpMethod
    path: str
    headers: dict[str, JsonValue] = Field(validation_alias="headers_json")
    query: dict[str, JsonValue] = Field(validation_alias="query_json")
    body: JsonValue = Field(validation_alias="body_json")
    assertions: list[AssertionSchema] = Field(validation_alias="assertions_json")
    extractors: list[ExtractorSchema] = Field(validation_alias="extractors_json")
    enabled: bool
    created_at: datetime
    updated_at: datetime


class SuiteStepCreate(StrictSchema):
    case_id: int
    before_step_id: int | None = None
    after_step_id: int | None = None
    draft_revision: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_single_anchor(self):
        if self.before_step_id is not None and self.after_step_id is not None:
            raise ValueError("only one insertion anchor may be provided")
        return self


class SuiteStepOrder(StrictSchema):
    step_ids: list[int]
    draft_revision: int = Field(ge=0)


class SuiteStepRead(OrmSchema):
    id: int
    suite_id: int
    case_id: int
    position: int
    enabled: bool
    created_at: datetime
    case: CaseRead


class SuiteStepsRead(BaseModel):
    suite: SuiteRead
    steps: list[SuiteStepRead]
