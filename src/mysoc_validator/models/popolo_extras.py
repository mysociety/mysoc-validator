"""Models and helpers for non-standard Popolo ``extra`` fields."""

from __future__ import annotations

from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Generic,
    Literal,
    Optional,
    Protocol,
    TypeVar,
    get_args,
    get_origin,
)

from pydantic import BaseModel, ConfigDict, Field

Language = Literal["en", "cy"]
LocalisedField = TypeVar("LocalisedField", bound=str)


class Extra(BaseModel):
    """Forward-compatible container for non-specification Popolo properties."""

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


class LocalisedLabelsExtra(Extra, Generic[LocalisedField]):
    """Popolo extras containing localised values, keyed by field and language."""

    localised_values: dict[LocalisedField, dict[Language, str]] = Field(
        default_factory=dict
    )


class HasLocalisedLabels(Protocol):
    """Typing contract for models using ``LocalisedLabelsMixin``."""

    _localised_fields: ClassVar[Any]
    extra: Optional[LocalisedLabelsExtra[Any]]


if not TYPE_CHECKING:

    class HasLocalisedLabels:
        """Runtime base compatible with Pydantic's model metaclass."""


class LocalisedLabelsMixin(HasLocalisedLabels, Generic[LocalisedField]):
    """Read and update explicit localised labels with a field-value fallback."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # Python keeps the generic declarations in __orig_bases__.
        # This lets us re-capture the LocalisedField so the setter
        # can construct the matching Pydantic models for the concrete model.

        for base in getattr(cls, "__orig_bases__", ()):
            if get_origin(base) is LocalisedLabelsMixin:
                cls._localised_fields = get_args(base)[0]
                break

    @property
    def _localised_values(self) -> dict[LocalisedField, dict[Language, str]]:
        if self.extra:
            return self.extra.localised_values
        return {}

    def get_localised_value(
        self,
        field: LocalisedField,
        language: Language,
    ) -> Optional[str]:
        """
        Get a localised value for a field, falling back to the canonical value if not found.
        """
        if not hasattr(self, field):
            raise ValueError(f"Field {field} not found on {self.__class__.__name__}")

        if self.extra:
            localised_value = self._localised_values.get(field, {}).get(language)
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
        Set a localised value for a field, creating or replacing an entry in ``extra.localised_values``.
        """

        if not hasattr(self, field):
            raise ValueError(f"Field {field} not found on {self.__class__.__name__}")

        if self.extra is None:
            self.extra = LocalisedLabelsExtra[self._localised_fields]()

        localised_values = self._localised_values

        if field not in localised_values:
            localised_values[field] = {}

        localised_values[field][language] = value

        # Assignment marks a previously defaulted field as explicitly set.
        self.extra.localised_values = localised_values
