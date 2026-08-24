"""Models and helpers for non-standard Popolo ``extra`` fields."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Literal,
    Optional,
    TypeVar,
)

from pydantic import BaseModel, ConfigDict, Field
from typing_extensions import Self

Language = Literal["en", "cy"]
LocalisedField = TypeVar("LocalisedField", bound=str)
ExternalExtraModel = TypeVar("ExternalExtraModel", bound=BaseModel)


class Extra(BaseModel):
    """
    Forward-compatible container for non-specification Popolo properties.
    """

    model_config = ConfigDict(extra="allow")

    def __getitem__(self, key: str) -> Any:
        """
        Get a non-standard Popolo property by key.
        """
        return getattr(self, key)

    def __setitem__(self, key: str, value: Any) -> None:
        """
        Set a non-standard Popolo property by key.
        """
        setattr(self, key, value)


class BaseExtraMixin:
    """
    Base class for mixins that provide get/set access to a Popolo ``extra`` field.

    Concrete subclasses must declare which ``Extra`` subtype backs their
    ``extra`` field, matching the field's own annotation. For example::

        class Membership(
            BaseExtraMixin,
            ...,
        ):
            extra: Optional[
                MembershipExtra
            ] = None

            _extra_class: ClassVar[
                type[Extra]
            ] = MembershipExtra

    so that ``ensure_extra`` knows to construct ``MembershipExtra``.
    """

    _extra_class: ClassVar[type[Extra]]

    if TYPE_CHECKING:
        extra: Optional[Extra]

    def ensure_extra(self) -> Extra:
        """
        Ensure ``extra`` is populated, creating the model's concrete Extra
        subtype if not already set.
        """
        if self.extra is None:
            self.extra = self._extra_class()

        return self.extra

    def get_extra(self, key: str) -> Any:
        """
        Get a non-standard Popolo property from ``extra``, or None if ``extra``
        or the property itself isn't set.
        """
        if self.extra is None:
            return None

        try:
            return self.extra[key]
        except AttributeError:
            return None

    def set_extra(self, key: str, value: Any) -> Self:
        """
        Set a non-standard Popolo property on ``extra``, creating ``extra`` first
        if not already set.
        """
        extra = self.ensure_extra()
        extra[key] = value
        return self

    def get_extra_as(
        self,
        model: type[ExternalExtraModel],
    ) -> Optional[ExternalExtraModel]:
        """
        Validate ``extra`` against a project-specific model and return an
        instance of it.
        """
        if self.extra is None:
            return None

        return model.model_validate(self.extra.model_dump())


class LocalisedLabelsExtra(Extra, Generic[LocalisedField]):
    """
    Popolo extras containing localised values, keyed by field and language.
    """

    localised_values: dict[LocalisedField, dict[Language, str]] = Field(
        default_factory=dict
    )


class LocalisedLabelsMixin(
    BaseExtraMixin,
    Generic[LocalisedField],
):
    """
    Read and update explicit localised labels with a field-value fallback.
    """

    def _localised_extra(
        self,
    ) -> Optional[LocalisedLabelsExtra[LocalisedField]]:
        """
        Return ``extra`` as a localised-labels extra, if populated.

        Concrete Extra models may freely subclass ``LocalisedLabelsExtra`` and
        add their own fields.
        """
        if self.extra is None:
            return None

        if not isinstance(self.extra, LocalisedLabelsExtra):
            raise TypeError(
                f"{self.__class__.__name__}.extra must inherit from "
                "LocalisedLabelsExtra"
            )

        return self.extra

    def _ensure_localised_extra(
        self,
    ) -> LocalisedLabelsExtra[LocalisedField]:
        """
        Ensure and return an Extra model supporting localised labels.
        """
        extra = self.ensure_extra()

        if not isinstance(extra, LocalisedLabelsExtra):
            raise TypeError(
                f"{self.__class__.__name__}.extra must inherit from "
                "LocalisedLabelsExtra"
            )

        return extra

    @property
    def _localised_values(
        self,
    ) -> dict[LocalisedField, dict[Language, str]]:
        extra = self._localised_extra()

        if extra is None:
            return {}

        return extra.localised_values

    def get_localised_value(
        self,
        field: LocalisedField,
        language: Language,
    ) -> Optional[str]:
        """
        Get a localised value for a field, falling back to the canonical value
        if not found.
        """
        if not hasattr(self, field):
            raise ValueError(f"Field {field} not found on {self.__class__.__name__}")

        extra = self._localised_extra()

        if extra is not None:
            localised_value = extra.localised_values.get(field, {}).get(language)

            if localised_value is not None:
                return localised_value

        return getattr(self, field, None)

    def set_localised_value(
        self,
        field: LocalisedField,
        language: Language,
        value: str,
    ) -> None:
        """
        Set a localised value for a field, creating or replacing an entry in
        ``extra.localised_values``.
        """
        if not hasattr(self, field):
            raise ValueError(f"Field {field} not found on {self.__class__.__name__}")

        extra = self._ensure_localised_extra()
        localised_values = extra.localised_values

        if field not in localised_values:
            localised_values[field] = {}

        localised_values[field][language] = value

        # Assignment marks a previously defaulted field as explicitly set.
        extra.localised_values = localised_values
