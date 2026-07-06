"""TypedDict definitions for the OpenAPI 3.1 subset used by EVE ESI.

These definitions intentionally model only the structures currently needed by the
ESI schema payload and project code. They are not intended to be a complete,
exhaustive representation of the full OpenAPI 3.1 specification.

Generated bny copilot on 2024-06-21 from the OpenAPI 3.1 specification and the ESI schema payload.
"""

from __future__ import annotations

from typing import Literal, Required, TypedDict

type JSONPrimitive = str | int | float | bool | None
type JSONValue = JSONPrimitive | list[JSONValue] | dict[str, JSONValue]
type HTTPMethod = Literal[
    "get", "put", "post", "delete", "options", "head", "patch", "trace"
]


class ReferenceObject(
    TypedDict("ReferenceObject", {"$ref": Required[str]}, total=False)
):
    """OpenAPI reference object."""


class ContactObject(TypedDict, total=False):
    """OpenAPI contact object."""

    name: str
    url: str
    email: str


class LicenseObject(TypedDict, total=False):
    """OpenAPI license object."""

    name: Required[str]
    identifier: str
    url: str


class InfoObject(TypedDict, total=False):
    """OpenAPI info object."""

    title: Required[str]
    summary: str
    description: str
    termsOfService: str
    contact: ContactObject
    license: LicenseObject
    version: Required[str]


class ServerVariableObject(TypedDict, total=False):
    """OpenAPI server variable object."""

    enum: list[str]
    default: Required[str]
    description: str


class ServerObject(TypedDict, total=False):
    """OpenAPI server object."""

    url: Required[str]
    description: str
    variables: dict[str, ServerVariableObject]


class TagObject(TypedDict, total=False):
    """OpenAPI tag object."""

    name: Required[str]
    description: str


class SchemaObject(TypedDict, total=False):
    """OpenAPI schema object subset used by ESI."""

    title: str
    description: str
    type: str | list[str]
    format: str
    nullable: bool
    enum: list[JSONValue]
    const: JSONValue
    default: JSONValue
    examples: list[JSONValue]
    deprecated: bool
    readOnly: bool
    writeOnly: bool

    properties: dict[str, SchemaOrReference]
    required: list[str]
    items: SchemaOrReference
    additionalProperties: bool | SchemaOrReference
    minProperties: int
    maxProperties: int

    minimum: int | float
    maximum: int | float
    exclusiveMinimum: bool | int | float
    exclusiveMaximum: bool | int | float
    multipleOf: int | float
    minLength: int
    maxLength: int
    pattern: str
    minItems: int
    maxItems: int
    uniqueItems: bool

    allOf: list[SchemaOrReference]
    anyOf: list[SchemaOrReference]
    oneOf: list[SchemaOrReference]
    not_: SchemaOrReference

    discriminator: dict[str, JSONValue]
    xml: dict[str, JSONValue]
    externalDocs: dict[str, JSONValue]
    example: JSONValue

    x_common_model: str


type SchemaOrReference = SchemaObject | ReferenceObject


class HeaderObject(TypedDict, total=False):
    """OpenAPI header object subset used by ESI."""

    description: str
    required: bool
    deprecated: bool
    allowEmptyValue: bool
    style: str
    explode: bool
    allowReserved: bool
    schema: SchemaOrReference
    example: JSONValue
    examples: dict[str, JSONValue]
    content: dict[str, MediaTypeObject]


type HeaderOrReference = HeaderObject | ReferenceObject


class ParameterObject(
    TypedDict(
        "ParameterObject",
        {
            "name": Required[str],
            "in": Required[Literal["query", "header", "path", "cookie"]],
            "description": str,
            "required": bool,
            "deprecated": bool,
            "allowEmptyValue": bool,
            "style": str,
            "explode": bool,
            "allowReserved": bool,
            "schema": SchemaOrReference,
            "example": JSONValue,
            "examples": dict[str, JSONValue],
            "content": dict[str, "MediaTypeObject"],
        },
        total=False,
    )
):
    """OpenAPI parameter object subset used by ESI."""


type ParameterOrReference = ParameterObject | ReferenceObject


class MediaTypeObject(TypedDict, total=False):
    """OpenAPI media type object subset used by ESI."""

    schema: SchemaOrReference
    example: JSONValue
    examples: dict[str, JSONValue]
    encoding: dict[str, JSONValue]


class RequestBodyObject(TypedDict, total=False):
    """OpenAPI request body object."""

    description: str
    content: Required[dict[str, MediaTypeObject]]
    required: bool


type RequestBodyOrReference = RequestBodyObject | ReferenceObject


class ResponseObject(TypedDict, total=False):
    """OpenAPI response object subset used by ESI."""

    description: Required[str]
    headers: dict[str, HeaderOrReference]
    content: dict[str, MediaTypeObject]
    links: dict[str, JSONValue]


type ResponseOrReference = ResponseObject | ReferenceObject


class OAuthFlowObject(TypedDict, total=False):
    """OpenAPI OAuth flow object."""

    authorizationUrl: str
    tokenUrl: str
    refreshUrl: str
    scopes: Required[dict[str, str]]


class OAuthFlowsObject(TypedDict, total=False):
    """OpenAPI OAuth flows object."""

    implicit: OAuthFlowObject
    password: OAuthFlowObject
    clientCredentials: OAuthFlowObject
    authorizationCode: OAuthFlowObject


class SecuritySchemeObject(
    TypedDict(
        "SecuritySchemeObject",
        {
            "type": Required[
                Literal[
                    "apiKey",
                    "http",
                    "mutualTLS",
                    "oauth2",
                    "openIdConnect",
                ]
            ],
            "description": str,
            "name": str,
            "in": Literal["query", "header", "cookie"],
            "scheme": str,
            "bearerFormat": str,
            "flows": OAuthFlowsObject,
            "openIdConnectUrl": str,
        },
        total=False,
    )
):
    """OpenAPI security scheme object subset used by ESI."""


type SecurityRequirementObject = dict[str, list[str]]


class OperationObject(
    TypedDict(
        "OperationObject",
        {
            "tags": list[str],
            "summary": str,
            "description": str,
            "operationId": str,
            "parameters": list[ParameterOrReference],
            "requestBody": RequestBodyOrReference,
            "responses": Required[dict[str, ResponseOrReference]],
            "deprecated": bool,
            "security": list[SecurityRequirementObject],
            "servers": list[ServerObject],
            "x-cache-age": int,
            "x-compatibility-date": str,
        },
        total=False,
    )
):
    """OpenAPI operation object subset used by ESI."""


class PathItemObject(TypedDict, total=False):
    """OpenAPI path item object subset used by ESI."""

    summary: str
    description: str
    get: OperationObject
    put: OperationObject
    post: OperationObject
    delete: OperationObject
    options: OperationObject
    head: OperationObject
    patch: OperationObject
    trace: OperationObject
    servers: list[ServerObject]
    parameters: list[ParameterOrReference]


class ComponentsObject(TypedDict, total=False):
    """OpenAPI components object subset used by ESI."""

    schemas: dict[str, SchemaOrReference]
    responses: dict[str, ResponseOrReference]
    parameters: dict[str, ParameterOrReference]
    requestBodies: dict[str, RequestBodyOrReference]
    headers: dict[str, HeaderOrReference]
    securitySchemes: dict[str, SecuritySchemeObject]


class OpenAPIObject(TypedDict, total=False):
    """OpenAPI root object for ESI schema payloads."""

    openapi: Required[str]
    info: Required[InfoObject]
    servers: list[ServerObject]
    paths: Required[dict[str, PathItemObject]]
    components: ComponentsObject
    security: list[SecurityRequirementObject]
    tags: list[TagObject]
    externalDocs: dict[str, JSONValue]


__all__ = [
    "ComponentsObject",
    "HeaderObject",
    "HTTPMethod",
    "InfoObject",
    "JSONPrimitive",
    "JSONValue",
    "MediaTypeObject",
    "OAuthFlowObject",
    "OAuthFlowsObject",
    "OpenAPIObject",
    "OperationObject",
    "ParameterObject",
    "PathItemObject",
    "ReferenceObject",
    "RequestBodyObject",
    "ResponseObject",
    "SchemaObject",
    "SecurityRequirementObject",
    "SecuritySchemeObject",
    "ServerObject",
    "ServerVariableObject",
    "TagObject",
]
