"""Functions for validating requests and request groups."""

import logging
from copy import deepcopy
from dataclasses import replace
from uuid import UUID

from esi_link.auth.token_manager_sqlite import CharacterTokenManagerSqlite
from esi_link.request.models import Request
from esi_link.schema.compatibility_dates_cache_sqlite import (
    CompatibilityDatesCacheSQLite,
)
from esi_link.schema.models import (
    EsiSchema,
)
from esi_link.schema.schema_cache_sqlite import SchemaCacheSqlite
from esi_link.validation.models import (
    InvalidRequest,
    ValidatedRequest,
)

logger = logging.getLogger(__name__)


def validate_request(
    request: Request,
    schema_cache: SchemaCacheSqlite,
    date_cache: CompatibilityDatesCacheSQLite,
    token_store: CharacterTokenManagerSqlite | None = None,
) -> ValidatedRequest | InvalidRequest:
    """Validates an individual request.

    If the request is valid, returns a ValidatedRequest. If the request is invalid,
    returns a FailedRequestValidation with the appropriate error messages.
    """
    in_process: ValidatedRequest | InvalidRequest = ValidatedRequest(
        request_id=request.request_id,
        actions=[],  # TODO move to validation step after we have the schema, so we can validate that the actions are valid for the requested operation_id
    )
    in_process = _validate_compatibility_date(
        request, in_process, date_cache=date_cache
    )
    in_process = _validate_request_schema(
        request, in_process, schema_cache=schema_cache
    )
    if isinstance(in_process, InvalidRequest):
        # If the schema validation failed, we don't need to do any further validation,
        # because the request is already invalid. We can just return the
        # FailedRequestValidation with the schema validation error.
        return in_process

    # Get the schema for use in the rest of the validation steps.
    cached_schema = schema_cache.get_cached_schema(
        compatibility_date=in_process.compatibility_date
    )
    in_process = _validate_operation_id(
        request, in_process, schema=cached_schema.esi_schema
    )
    if isinstance(in_process, InvalidRequest):
        # If the operation_id validation failed, we don't need to do any further validation,
        # because the request is already invalid. We can just return the FailedRequestValidation
        # with the operation_id validation error.
        return in_process
    in_process = _validate_x_compatibility_date(
        request, in_process, schema=cached_schema.esi_schema
    )
    in_process = _validate_path_parameters(
        request, in_process, schema=cached_schema.esi_schema
    )
    in_process = _validate_query_parameters(
        request, in_process, schema=cached_schema.esi_schema
    )
    in_process = _validate_body_parameters(
        request, in_process, schema=cached_schema.esi_schema
    )
    if token_store is not None:
        authorized_characters = set(token_store.available_characters)
    else:
        authorized_characters: set[int] = set()
    in_process = _validate_authentication(
        request,
        in_process,
        schema=cached_schema.esi_schema,
        authorized_characters=authorized_characters,
    )
    in_process = _validate_language(
        request, in_process, schema=cached_schema.esi_schema
    )
    in_process = _set_method(request, in_process, schema=cached_schema.esi_schema)
    in_process = _set_url_template(request, in_process, schema=cached_schema.esi_schema)
    in_process = _set_is_paged(request, in_process, schema=cached_schema.esi_schema)
    in_process = _set_is_cached(request, in_process, schema=cached_schema.esi_schema)
    in_process = _set_is_authentication_required(
        request, in_process, schema=cached_schema.esi_schema
    )

    # Last check before returning the validation result.
    return in_process


def validate_requests(
    requests: dict[UUID, Request],
    schema_cache: SchemaCacheSqlite,
    date_cache: CompatibilityDatesCacheSQLite,
    token_store: CharacterTokenManagerSqlite | None = None,
) -> tuple[dict[UUID, ValidatedRequest], dict[UUID, InvalidRequest]]:
    """Validates a group of requests.

    Returns a tuple containing a dictionary of the valid requests and a dictionary of
    the failed request validations.
    """
    validated_requests: dict[UUID, ValidatedRequest] = {}
    failed_request_validations: dict[UUID, InvalidRequest] = {}
    for request_id, request in requests.items():
        validation_result = validate_request(
            request=request,
            schema_cache=schema_cache,
            token_store=token_store,
            date_cache=date_cache,
        )
        if isinstance(validation_result, ValidatedRequest):
            validated_requests[request_id] = validation_result
        else:
            failed_request_validations[request_id] = validation_result
    return validated_requests, failed_request_validations


def _validate_compatibility_date(
    request: Request,
    in_process: ValidatedRequest | InvalidRequest,
    *,
    date_cache: CompatibilityDatesCacheSQLite,
) -> ValidatedRequest | InvalidRequest:
    """Validates that the compatibility date provided in the request is valid.

    If no compatibility date is provided in the request, the latest schema compatibility
    date will be used.
    """
    valid_compatibility_dates = date_cache.compatibility_dates.compatibility_dates
    compatibility_date = request.compatibility_date
    if compatibility_date is None:
        compatibility_date = max(valid_compatibility_dates)
    if compatibility_date not in valid_compatibility_dates:
        fail_msg = (
            f"Requested compatibility date {compatibility_date} is not valid. "
            f"Valid compatibility dates are: {', '.join(valid_compatibility_dates)}."
        )
        if isinstance(in_process, InvalidRequest):
            fail_msgs = list(in_process.errors) + [fail_msg]
        else:
            fail_msgs = [fail_msg]
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    # Update validated fields.
    if isinstance(in_process, ValidatedRequest):
        in_process = deepcopy(in_process)
        in_process = replace(
            in_process,
            compatibility_date=compatibility_date,
        )
    return in_process


def _validate_request_schema(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema_cache: SchemaCacheSqlite,
) -> ValidatedRequest | InvalidRequest:
    """Validates that the requested schema is available in the schema manager.

    Because so many of the details of the request validation logic depend on the schema,
    we need to validate that the requested schema is available before we can do any further
    validation. If the requested schema is not available, returns a FailedRequestValidation
    with the appropriate error message.
    """
    if isinstance(inprocess_request, InvalidRequest):
        # If the compatibility date validation already failed, we don't need to check for
        # the requested schema, because the request is already invalid. We can just return
        # the FailedRequestValidation with the compatibility date validation error.
        return deepcopy(inprocess_request)
    try:
        _requested_schema = schema_cache.get_cached_schema(
            compatibility_date=inprocess_request.compatibility_date,
        )
    except Exception as e:
        fail_msg = f"Error while trying to get the requested schema from the schema cache: {str(e)}"
        if isinstance(inprocess_request, InvalidRequest):
            fail_msgs = list(inprocess_request.errors) + [fail_msg]
        else:
            fail_msgs = [fail_msg]
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    # compatibility date is valid and the requested schema is available.

    inprocess_request = deepcopy(inprocess_request)

    return inprocess_request


def _validate_x_compatibility_date(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Validates the x-compatibility-date field of the request.

    If the x-compatibility-date is invalid, returns a FailedRequestValidation with the appropriate
    error message. If the x-compatibility-date is valid, returns the inprocess_request unchanged.
    """
    try:
        operation = schema.get_operation_by_id(request.operation_id)
        if operation is None:
            raise ValueError(
                f"Operation with id {request.operation_id} not found in schema."
            )
        x_compatibility_date = operation.x_compatibility_date
    except ValueError as e:
        fail_msg = str(e)
        if isinstance(inprocess_request, InvalidRequest):
            fail_msgs = list(inprocess_request.errors) + [fail_msg]
        else:
            fail_msgs = [fail_msg]
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            x_compatibility_date=x_compatibility_date,
        )
    return inprocess_request


def _validate_operation_id(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Validates the operation_id field of the request.

    If the operation_id is invalid, returns a FailedRequestValidation with the appropriate
    error message. If the operation_id is valid, returns the inprocess_request unchanged.
    """
    available_operations = schema.operation_ids
    if request.operation_id not in available_operations:
        fail_msg = f"Requested operation_id {request.operation_id} is not available in the schema."
        if isinstance(inprocess_request, InvalidRequest):
            fail_msgs = list(inprocess_request.errors) + [fail_msg]
        else:
            fail_msgs = [fail_msg]
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            operation_id=request.operation_id,
        )
    return inprocess_request


def _validate_path_parameters(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Validates that the path parameters provided in the request are valid.

    If any path parameters are invalid, returns a FailedRequestValidation with the
    appropriate error messages. If all path parameters are valid, returns the inprocess_
    request unchanged.
    """
    operation = schema.get_operation_by_id(request.operation_id)
    assert operation is not None, (
        "operation should have been found in the operation_id validation step"
    )
    expected_path_parameters = {
        param["name"]: param for param in operation.path_parameters
    }
    given_path_parameters = deepcopy(request.path_parameters)
    # All path parameters defined in the schema must be present in the request, and
    # must be of the correct type.
    fail_msgs: list[str] = []
    for param_name, param_schema in expected_path_parameters.items():
        if param_name not in given_path_parameters:
            fail_msgs.append(f"Missing required path parameter: {param_name}")
        else:
            # TODO match case
            if param_schema["schema"]["type"] == "integer":
                if not isinstance(given_path_parameters[param_name], int):
                    fail_msgs.append(
                        f"Invalid type for path parameter {param_name}: expected integer, got {type(given_path_parameters[param_name]).__name__}"
                    )
            elif param_schema["schema"]["type"] == "string":
                if not isinstance(given_path_parameters[param_name], str):
                    fail_msgs.append(
                        f"Invalid type for path parameter {param_name}: expected string, got {type(given_path_parameters[param_name]).__name__}"
                    )
            else:
                logger.warning(f"Unexpected path parameter: {param_schema}")
    # If there are any validation errors, return a FailedRequestValidation with the error messages.
    if fail_msgs:
        if isinstance(inprocess_request, InvalidRequest):
            fail_msgs = list(inprocess_request.errors) + fail_msgs
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            path_parameters=given_path_parameters,
        )
    return inprocess_request


def _validate_query_parameters(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Validates that the query parameters provided in the request are valid."""
    operation = schema.get_operation_by_id(request.operation_id)
    assert operation is not None, (
        "operation should have been found in the operation_id validation step"
    )
    expected_query_parameters = {
        param["name"]: param for param in operation.query_parameters
    }
    given_query_parameters = deepcopy(request.query_parameters)
    # No extra query parameters that are not defined in the schema can be present in the request.
    # All query parameters defined in the schema that are required must be present in the request.
    # and all query parameters defined in the schema that are present in the request must be of the correct type.
    fail_msgs: list[str] = []
    for param_name, param_value in given_query_parameters.items():
        if param_name not in expected_query_parameters:
            fail_msgs.append(f"Unexpected query parameter: {param_name}")
        else:
            param_schema = expected_query_parameters[param_name]
            match param_schema["schema"]["type"]:
                case "integer":
                    if not isinstance(param_value, int):
                        fail_msgs.append(
                            f"Invalid type for query parameter {param_name}: expected integer, got {type(param_value).__name__}"
                        )
                case "string":
                    if not isinstance(param_value, str):
                        fail_msgs.append(
                            f"Invalid type for query parameter {param_name}: expected string, got {type(param_value).__name__}"
                        )
                case _:
                    fail_msgs.append(
                        f"UnExpected type for query parameter {param_name}: {param_schema['schema']['type']}"
                    )
    for param_name, param_schema in expected_query_parameters.items():
        if (
            param_schema.get("required", False)
            and param_name not in given_query_parameters
        ):
            fail_msgs.append(f"Missing required query parameter: {param_name}")
    # If there are any validation errors, return a FailedRequestValidation with the error messages.
    if fail_msgs:
        if isinstance(inprocess_request, InvalidRequest):
            fail_msgs = list(inprocess_request.errors) + fail_msgs
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    # If the `page` query parameter is present, pop it.
    # Pagination is handled separately in the runtime logic.
    if "page" in given_query_parameters:
        given_query_parameters.pop("page")

    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            query_parameters=given_query_parameters,
        )
    return inprocess_request


def _validate_body_parameters(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Validates that the body parameters provided in the request are valid."""
    operation = schema.get_operation_by_id(request.operation_id)
    assert operation is not None, (
        "operation should have been found in the operation_id validation step"
    )
    expected_body_parameters = operation.request_body
    given_body_parameters = deepcopy(request.json_body)

    if expected_body_parameters is None and given_body_parameters is None:
        return deepcopy(inprocess_request)

    fail_msgs: list[str] = []
    if expected_body_parameters is None and given_body_parameters is not None:
        fail_msgs.append("Unexpected body parameters provided for this endpoint.")
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    assert expected_body_parameters is not None, (
        "Expected body parameters should not be None at this point, because if it were None we would have already returned above."
    )

    if given_body_parameters is None:
        is_required = expected_body_parameters.get("required", False)
        if is_required:
            fail_msgs.append("Missing required body parameters for this endpoint.")
            return InvalidRequest(
                request=request,
                errors=tuple(fail_msgs),
            )

    body_schema = (
        expected_body_parameters.get("content", {})
        .get("application/json", {})
        .get("schema", {})
    )
    # check top level type of body parameters (object, array, etc.) and validate
    # that the given body parameters are of the correct type.
    given_type = type(given_body_parameters).__name__
    match body_schema.get("type"):
        case "object":
            if given_type != "dict":
                fail_msgs.append(
                    f"Invalid type for body parameters: expected object, got {given_type}"
                )
        case "array":
            if given_type != "list":
                fail_msgs.append(
                    f"Invalid type for body parameters: expected array, got {given_type}"
                )
        # TODO examine the schema further for scalar types, and validate.

        # case "string":
        #     if given_type != "str":
        #         fail_msgs.append(
        #             f"Invalid type for body parameters: expected string, got {given_type}"
        #         )
        # case "integer":
        #     if given_type != "int":
        #         fail_msgs.append(
        #             f"Invalid type for body parameters: expected integer, got {given_type}"
        #         )
        # case "boolean":
        #     if given_type != "bool":
        #         fail_msgs.append(
        #             f"Invalid type for body parameters: expected boolean, got {given_type}"
        #         )
        # case "number":
        #     if given_type not in ("int", "float"):
        #         fail_msgs.append(
        #             f"Invalid type for body parameters: expected number, got {given_type}"
        #         )
        case _:
            raise ValueError(
                f"Unexpected or missing type for body parameters in schema: {body_schema.get('type')}"
            )

    # If there are any validation errors, return a FailedRequestValidation with the error messages.
    if fail_msgs:
        if isinstance(inprocess_request, InvalidRequest):
            fail_msgs = list(inprocess_request.errors) + fail_msgs
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            json_body=given_body_parameters,
        )
    return inprocess_request


def _validate_authentication(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
    authorized_characters: set[int],
) -> ValidatedRequest | InvalidRequest:
    """Validates that authentication is available if required for this request."""
    operation = schema.get_operation_by_id(request.operation_id)
    assert operation is not None, (
        "operation should have been found in the operation_id validation step"
    )
    if operation.is_authentication_required:
        if request.authorization_id is None:
            fail_msg = f"Authentication is required for this endpoint, but no authorization_id was provided in the request."
            if isinstance(inprocess_request, InvalidRequest):
                fail_msgs = list(inprocess_request.errors) + [fail_msg]
            else:
                fail_msgs = [fail_msg]
            return InvalidRequest(
                request=request,
                errors=tuple(fail_msgs),
            )
        elif request.authorization_id not in authorized_characters:
            fail_msg = f"Authentication is required for this endpoint, but the provided authorization_id {request.authorization_id} is not in the set of authorized characters."
            if isinstance(inprocess_request, InvalidRequest):
                fail_msgs = list(inprocess_request.errors) + [fail_msg]
            else:
                fail_msgs = [fail_msg]
            return InvalidRequest(
                request=request,
                errors=tuple(fail_msgs),
            )
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            authorization_id=request.authorization_id,
        )
    return inprocess_request


def _validate_language(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Validates the language parameter provided in the request."""
    # check that the requested language is available from the ESI.
    available_languages = schema.content_languages
    if request.language not in available_languages:
        fail_msg = (
            f"Requested language {request.language} is not available for this endpoint."
        )
        if isinstance(inprocess_request, InvalidRequest):
            fail_msgs = list(inprocess_request.errors) + [fail_msg]
        else:
            fail_msgs = [fail_msg]
        return InvalidRequest(
            request=request,
            errors=tuple(fail_msgs),
        )
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            language=request.language,
        )
    return inprocess_request


def _set_method(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Sets the HTTP method for the request."""
    operation = schema.get_operation_by_id(request.operation_id)
    assert operation is not None, (
        "operation should have been found in the operation_id validation step"
    )
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            method=operation.method,
        )
    return inprocess_request


def _set_url_template(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Sets the URL template for the request."""
    base_url = schema.base_url
    operation = schema.get_operation_by_id(request.operation_id)
    assert operation is not None, (
        "operation should have been found in the operation_id validation step"
    )
    path_url_template = base_url + operation.path
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            path_url_template=path_url_template,
        )
    return inprocess_request


def _set_is_paged(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Determines whether the request is for a paged endpoint."""
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        operation = schema.get_operation_by_id(request.operation_id)
        assert operation is not None, (
            "operation should have been found in the operation_id validation step"
        )
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            is_paged=operation.is_paged,
        )
    return inprocess_request


def _set_is_cached(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Determines whether the request is for a cached endpoint."""
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        operation = schema.get_operation_by_id(request.operation_id)
        assert operation is not None, (
            "operation should have been found in the operation_id validation step"
        )
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            is_cached=operation.is_cached,
        )
    return inprocess_request


def _set_is_authentication_required(
    request: Request,
    inprocess_request: ValidatedRequest | InvalidRequest,
    *,
    schema: EsiSchema,
) -> ValidatedRequest | InvalidRequest:
    """Determines whether the request requires authentication."""
    # Update validated fields.
    if isinstance(inprocess_request, ValidatedRequest):
        operation = schema.get_operation_by_id(request.operation_id)
        assert operation is not None, (
            "operation should have been found in the operation_id validation step"
        )
        inprocess_request = deepcopy(inprocess_request)
        inprocess_request = replace(
            inprocess_request,
            is_authentication_required=operation.is_authentication_required,
        )
    return inprocess_request
