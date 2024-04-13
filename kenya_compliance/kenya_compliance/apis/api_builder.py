import asyncio
from typing import Any, Callable, Literal
from urllib import parse

import aiohttp
import frappe
from frappe.integrations.utils import create_request_log
from frappe.model.document import Document

from ..logger import etims_logger
from ..utils import make_post_request, update_last_request_date


class EndpointsBuilder:
    def __init__(self) -> None:
        self._method: Literal["POST"] | str = "POST"
        self._url: str | None = None
        self._payload: dict | None = None
        self._headers: dict | None = None
        self._error: str | None = None
        self._success_callback_handler: Callable | None = None
        self._error_callback_handler: Callable | None = None

    @property
    def method(self) -> str:
        return self._method

    @method.setter
    def method(self, new_method: Literal["GET", "PUT", "PATCH"]) -> None:
        self._method = new_method

    @property
    def url(self) -> str | None:
        return self._url

    @url.setter
    def url(self, new_url: str) -> None:
        self._url = new_url

    @property
    def payload(self) -> dict | None:
        return self._payload

    @payload.setter
    def payload(self, new_payload: dict) -> None:
        self._payload = new_payload

    @property
    def error(self) -> str | None:
        return self._error

    @error.setter
    def error(self, new_error: str) -> None:
        self._error = new_error

    @property
    def headers(self) -> dict | None:
        return self._headers

    @headers.setter
    def headers(self, new_headers: dict) -> None:
        self._headers = new_headers

    @property
    def success_callback(self) -> Callable | None:
        return self._success_callback_handler

    @success_callback.setter
    def success_callback(self, callback: Callable) -> None:
        self._success_callback_handler = callback

    @property
    def error_callback(self) -> Callable | None:
        return self._error_callback_handler

    @error_callback.setter
    def error_callback(
        self, callback: Callable[[dict | str, str, str, str], None]
    ) -> None:
        self._error_callback_handler = callback

    def make_remote_call(
        self, doctype: Document | str | None = None, document_name: str | None = None
    ) -> Any:
        if (
            self._url is None
            or self._headers is None
            or self._success_callback_handler is None
            or self._error_callback_handler is None
        ):
            frappe.throw(
                "Please check that all required request parameters are supplied.",
                frappe.MandatoryError,
                title="Setup Error",
                is_minimizable=True,
            )

        parsed_url = parse.urlparse(self._url)
        route_path = f"/{parsed_url.path.split('/')[-1]}"

        integration_request = create_request_log(
            data=self._payload,
            is_remote_request=True,
            service_name="etims",
            request_headers=self._headers,
            url=self._url,
            reference_docname=document_name,
            reference_doctype=doctype,
        )

        try:
            response = asyncio.run(
                make_post_request(self._url, self._payload, self._headers)
            )

            if response["resultCd"] == "000":
                # Success callback handler here
                self._success_callback_handler(response)

                update_last_request_date(response["resultDt"], route_path)

            else:
                # Error callback handler here
                self._error_callback_handler(
                    response,
                    url=route_path,
                    doctype=doctype,
                    document_name=document_name,
                    integration_reqeust_name=integration_request.name,
                )

        except aiohttp.client_exceptions.ClientConnectorError as error:
            etims_logger.exception(error, exc_info=True)
            frappe.throw(
                "Connection failed",
                error,
                title="Connection Error",
            )

        except aiohttp.client_exceptions.ClientOSError as error:
            etims_logger.exception(error, exc_info=True)
            frappe.throw(
                "Connection reset by peer",
                error,
                title="Connection Error",
            )

        except asyncio.exceptions.TimeoutError as error:
            etims_logger.exception(error, exc_info=True)
            frappe.throw("Timeout Encountered", error, title="Timeout Error")